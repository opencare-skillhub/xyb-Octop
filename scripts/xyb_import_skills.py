#!/usr/bin/env python3
"""Import external skills into an xiaoyibao expert package, with provenance.

Every imported skill gets a fixed header recording where it came from, its
measured licence, when it was adapted and how far it actually works here
(``readiness``). That header is the point of this script: an imported skill
without provenance becomes an unattributable liability the first time someone
asks whether it may be redistributed.

Two things the script deliberately does **not** do:

* it does not copy a whole upstream repository (some of them carry thousands of
  fixture images); each import lists the paths it wants;
* it does not claim the skill is ready. ``readiness`` is an explicit argument in
  the import table, so "the file is here" never silently becomes "the feature
  works".

Usage::

    python3 scripts/xyb_import_skills.py --list
    python3 scripts/xyb_import_skills.py                 # run every import
    python3 scripts/xyb_import_skills.py --only hads-screening
    python3 scripts/xyb_import_skills.py --check         # verify headers/paths
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LIBRARY = REPO / "src" / "octop" / "infra" / "agents" / "experts" / "library"

#: Where the upstream checkouts live on this machine, by repository name.
#: Override the whole map with XYB_SKILL_SOURCES to import on another host.
DEFAULT_SOURCES: dict[str, str] = {
    "skill-HADS-accessment": "~/Downloads/skill-hads-assessment",
    "chictr-trials-collector": "~/Downloads/chictr-trials-collector",
    "clinicaltrials-intel-skill": "~/Downloads/clinicaltrials-intel-skill",
    "nccn-guideline-downloader": "/tmp/xyb-nccn-src",
    "Medical-Record-Organizer": "~/Downloads/patient-record-organizer",
    "chinadurgtrials": "/tmp/xyb-chinadrugs-src",
    "clinical-trial-matching": "/tmp/xyb-trialmatch-src",
    "xyb_dicom_download_skills": "/tmp/xyb-dicom-src",
    "xyb-humanizer": "/tmp/xyb-humanizer-src",
    "agent-taste-seed-system": "/tmp/xyb-taste-src",
    "xyb-wechat-article-transcription": "/tmp/xyb-wechat-src",
    "aura_health_profile": "/tmp/xyb-profile-src",
    "pdf-translate": "/tmp/xyb-pdf-src",
}

#: Files that never belong in an expert package, whatever the import asks for.
#: Upstream test files carry the author's absolute home paths and ship no
#: behaviour; a test that cannot run here is dead weight in the workspace.
EXCLUDED_FILES = frozenset(
    {
        "scripts/test_render_from_case_data.py",
        "scripts/v2/v1_file_notes.md",
    }
)

#: OS/editor droppings that carry nothing and clutter every workspace.
EXCLUDED_NAMES = frozenset({".DS_Store", "Thumbs.db", "desktop.ini", ".gitkeep"})

#: Never copied, at any depth.
EXCLUDED_DIRS = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "dist",
        "build",
        ".pytest_cache",
        ".mypy_cache",
    }
)


@dataclass(frozen=True)
class Import:
    """One skill moving from an upstream checkout into an expert package."""

    slug: str
    source_repo: str
    #: SPDX id as measured with `gh api repos/<owner>/<repo> --jq .license.spdx_id`.
    #: "NONE" is written explicitly, never left blank.
    source_license: str
    expert: str
    #: Paths inside the source checkout to bring across.
    include: tuple[str, ...]
    readiness: str
    #: What was changed relative to upstream, in one sentence.
    adapted: str = ""
    #: SPDX id merely *declared* inside a file (e.g. `license: MIT` in SKILL.md)
    #: when the repository has no LICENSE file. Recorded separately on purpose:
    #: a declaration is not a licence grant we can rely on for redistribution.
    declared_license: str = ""
    #: True when upstream carries a licence claim in a file even though the
    #: repository has no LICENSE. Then `declared_license` must be filled in.
    #: False for a repository that makes no licence claim at all.
    has_licence_claim: bool = False
    #: Repo-relative path holding the skill body when upstream has no SKILL.md
    #: (e.g. a repo that documents its skill in TASTE.md). Empty means SKILL.md.
    body_from: str = ""
    #: Files rewritten after copying (e.g. to remove a public-deployment step).
    rewrite: dict[str, tuple[tuple[str, str], ...]] = field(default_factory=dict)
    #: Markdown inserted directly under the frontmatter, before the upstream
    #: body. Used to scope an upstream skill without rewriting its wording.
    preamble: str = ""
    #: Frontmatter name/description overrides.
    name: str = ""
    description: str = ""
    emoji: str = ""
    label_zh: str = ""
    label_en: str = ""
    summary_zh: str = ""
    summary_en: str = ""

    @property
    def dest(self) -> Path:
        return LIBRARY / self.expert / "skills" / self.slug


IMPORTS: tuple[Import, ...] = (
    Import(
        slug="distress-screening",
        source_repo="opencare-skillhub/skill-HADS-accessment",
        source_license="NONE",
        expert="xyb-mdt-psych",
        include=("SKILL.md", "references", "assets", "scripts"),
        readiness="受限（仅本机版；公网发布路径已移除）",
        name="distress-screening",
        description=(
            "当患者情绪困扰需要结构化初筛时使用。提供 HADS（医院焦虑抑郁量表）的"
            "条目说明、计分规则与结果解读框架，**全部在本机完成，不上传、不发布公网**。"
            "Must use for structured distress screening; local-only, never published."
        ),
        emoji="📋",
        label_zh="情绪困扰初筛（HADS）",
        label_en="Distress Screening (HADS)",
        summary_zh="本机完成 HADS 初筛、计分与解读；不发布公网、不上传数据。",
        summary_en="Local-only HADS screening, scoring and interpretation.",
        adapted=(
            "限定为仅本机执行：上游的「发布到公网问卷平台」路径在本项目中屏蔽，"
            "改为本地 HTML 或对话内作答；并明确量表结果不能作为诊断，"
            "只用于提示是否需要专业评估。"
        ),
        preamble=(
            "> ## 本项目的使用范围（优先级高于本文其余内容）\n"
            ">\n"
            "> 上游技能支持把问卷**发布到公网平台**收集作答。**本项目不使用该路径。**\n"
            "> 需求明确要求问卷保持本机版（见 `XYB-REQUIREMENTS.md` §八），因此：\n"
            ">\n"
            "> - 问卷只在本机生成与作答，**不上传、不发布、不用第三方托管**；\n"
            "> - 不收集姓名、手机号、身份证号、住院号；作答记录只留本机；\n"
            "> - 量表结果是**初筛**，不构成心理或精神科诊断；\n"
            "> - 出现自伤或自杀念头时，按本专家 `SOUL.md` 的危机信号流程处理，"
            "优先级高于本技能。\n"
            ">\n"
            "> 下文是上游原始说明，其中涉及公网发布的部分仅作背景了解，本项目不执行。\n"
        ),
        rewrite={},
    ),
    Import(
        slug="chictr-collect",
        source_repo="opencare-skillhub/chictr-trials-collector",
        source_license="Apache-2.0",
        expert="xyb-trial-matching",
        include=("SKILL.md", "references", "src", "package.json", "README.md", "LICENSE"),
        readiness="需配置（Node 依赖需自行安装；优先走已配置的 chictr MCP 通道）",
        name="chictr-collect",
        description=(
            "当需要从中国临床试验注册中心（ChiCTR）按关键词、注册号或年份采集试验"
            "并导出结构化记录时使用。优先走平台已配置的 chictr MCP 通道；本技能保留"
            "采集流程与字段说明作为方法与降级路径。"
            "Use for ChiCTR collection when the MCP channel is unavailable."
        ),
        emoji="🇨🇳",
        label_zh="ChiCTR 试验采集",
        label_en="ChiCTR Collection",
        summary_zh="ChiCTR 检索与结构化导出；优先用 MCP 通道，本技能作方法与降级。",
        summary_en="ChiCTR search and structured export; MCP first, this as fallback.",
    ),
    Import(
        slug="pdf-translate",
        source_repo="opencare-skillhub/pdf-translate",
        source_license="NONE",
        expert="xyb-mdt-radiation",
        include=("SKILL.md", "README.md", "references", "scripts"),
        readiness="需安装依赖（首次运行 setup.sh 会用 uv 安装 pdf2zh_next，约 1GB 级模型资产）；未安装时只给安装步骤",
        name="pdf-translate",
        description=(
            "当患者或家属拿到**英文 PDF 资料**（期刊论文、国外指南、说明书、试验方案）"
            "需要中文对照时使用。在本机把 PDF 译成中英对照版本，便于与医生讨论。"
            "**只做翻译，不做摘要判断**；机器翻译有误差，关键结论仍以原文为准。"
            "Use to translate English PDFs into bilingual Chinese for discussion."
        ),
        emoji="🌐",
        label_zh="PDF 中英对照翻译",
        label_en="PDF Bilingual Translation",
        summary_zh="把英文 PDF 译成中英对照本机版本；只翻译不判读。",
        summary_en="Translate an English PDF into a bilingual local copy.",
        adapted=(
            "只导入技能与包装脚本（5 个文件）；`pdf2zh_next` 与其模型资产属**首次运行按需安装**，"
            "不随仓库分发。正文顶部声明：未安装时只给安装步骤、**只翻译不判读**、"
            "机器翻译需以原文核对。"
        ),
        preamble=(
            "> ## 使用范围（优先级高于本文其余内容）\n"
            ">\n"
            "> - **只做翻译，不做判读。** 产出是中英对照文本；资料说了什么、对病情意味着什么，"
            "由对应 MDT 视角按 `SOUL.md` 骨架分析，且不替代医生。\n"
            "> - **机器翻译会出错**，尤其是剂量、分期、统计口径与否定句。关键结论必须回原文核对，"
            "输出里要写明这一条。\n"
            "> - 依赖 `pdf2zh_next`（含约 1GB 级模型资产），由 `scripts/setup.sh` 用 `uv` 在**本机**安装。"
            "**未安装时只给安装步骤，不要假装已开始翻译。**\n"
            "> - 资料只在本机处理；涉及患者身份信息时先过 `xyb-record-desensitize`。\n"
            "> - 上传受版权保护的全文时，提醒用户自行确认使用范围。\n"
        ),
    ),
    Import(
        slug="lab-to-profile",
        source_repo="opencare-skillhub/aura_health_profile",
        source_license="MIT-0",
        expert="xyb-mdt-oncology",
        include=("SKILL.md", "LICENSE", "README.md", "requirements.txt", "assets", "references", "scripts"),
        readiness="需配置（依赖阿里云百炼 Qwen/Wan；未配置时只走本地模板，不假装已生成）",
        name="lab-to-profile",
        description=(
            "当患者希望把散乱的化验单与病历整理成**可长期更新的健康档案**、复诊简报或趋势时使用。"
            "产出结构化档案与一页纸复诊简报，便于复诊时交给医生。"
            "需阿里云百炼 key；**未配置时明确说明只产出本地模板**，不要假装已生成。"
            "Use to turn scattered labs and notes into an updatable health profile and visit brief."
        ),
        emoji="🗃️",
        label_zh="化验单到健康档案",
        label_en="Labs to Health Profile",
        summary_zh="把散乱化验单整理成可更新档案与一页纸复诊简报。",
        summary_en="Turn scattered labs into an updatable profile and a visit brief.",
        adapted=(
            "只导入英文侧正文与模板（`SKILL.md`/`assets`/`references`/`scripts`/`requirements.txt`）；"
            "不带入中文重复副本（`*_CN.md`）、`ONBOARD*`/`PUBLISHING*`/`CHANGELOG*` 等仓库运维文档。"
            "正文顶部加范围声明：需百炼 key、未配置时的降级路径、数据不出机、"
            "**趋势不等于疗效判断**。"
        ),
        preamble=(
            "> ## 未配置时的行为（优先级高于本文其余内容）\n"
            ">\n"
            "> - 本技能依赖**阿里云百炼**（Qwen / Wan）。**未配置 key 时，只走本地模板产出空白档案**，"
            "并明确告知用户「模型能力未启用」，不要假装已经生成分析结果。\n"
            "> - 资料只在本机处理；不把化验单上传到本项目之外的任何服务。\n"
            "> - **趋势不等于疗效**：指标变化只能陈述「数值怎么变」，"
            "不能据此判断治疗有效或无效——那是主管医生的判断。\n"
            "> - 需要患者身份信息时先过 `xyb-record-desensitize`；档案里不写姓名、住院号、身份证号。\n"
            "> - 涉及症状与用药的问题，转交对应 MDT 视角，并遵守 `xyb-medical-disclaimer`。\n"
        ),
    ),
    Import(
        slug="wechat-article",
        source_repo="opencare-skillhub/xyb-wechat-article-transcription",
        source_license="Apache-2.0",
        expert="xyb-community-ops",
        body_from="skills/SKILL.md",
        include=("LICENSE", "README.md", "skills"),
        readiness="可直接使用（改写与排版在本机完成；发表到公众号需自备凭据，本项目不含任何密钥）",
        name="wechat-article",
        description=(
            "当要把一篇公众号文章改写成小胰宝风格的公众号 HTML，或需要按模板排版输出时使用。"
            "覆盖「取原文 → 改写 → 套模板 → 存成本地 HTML」整条链路；模板可指定，默认按技能说明。"
            "**只产出本地 HTML**，不代替运营发布，也不含任何公众号密钥。"
            "Use to rewrite an article into Xiaoyibao-style WeChat HTML locally."
        ),
        emoji="📰",
        label_zh="公众号文章改写排版",
        label_en="WeChat Article Rewrite",
        summary_zh="取原文→改写→套模板→存本地 HTML；不含任何发布密钥。",
        summary_en="Transcribe, rewrite and template an article into local WeChat HTML.",
        adapted=(
            "上游把技能放在 `skills/` 子目录，导入器用 `body_from` 显式指定正文来源，"
            "不会写出占位 SKILL.md。带入了全部排版模板与渲染脚本。"
            "正文顶部加范围声明：**只产出本地 HTML**、不含发布凭据、"
            "医学内容仍受证据与免责约束。"
        ),
        preamble=(
            "> ## 使用范围（优先级高于本文其余内容）\n"
            ">\n"
            "> - 本技能**只产出本地 HTML 文件**。发布到公众号由运营人员自行操作，"
            "本项目**不含**任何公众号密钥、AppSecret 或 cookie。\n"
            "> - 改写医学内容时受 `xyb-evidence-guard` / `xyb-medical-disclaimer` 约束；"
            "去 AI 腔走 `humanizer`，且**不得改动证据等级或结论强度**。\n"
            "> - 涉及病友故事、患者照片与影像时，先过 `xyb-record-desensitize`："
            "**不得使用可识别到个人的素材**。\n"
            "> - 排版配色应与小胰宝品牌一致（基色薄荷绿 `#2F8F80`）；"
            "上游提供多种主题模板，选用时注意与品牌协调。\n"
        ),
    ),
    Import(
        slug="humanizer",
        source_repo="opencare-skillhub/xyb-humanizer",
        source_license="NONE",
        expert="xyb-community-ops",
        include=("SKILL.md", "README.md", "CHANGELOG.md"),
        readiness="可直接使用（纯写作方法层，无外部依赖）",
        name="humanizer",
        description=(
            "当要把小胰宝的科普稿、患者教育、社区文章或专家观点整理**去掉 AI 腔**时使用。"
            "保留事实、证据等级与作者判断，去掉模板化与机械节奏；"
            "**不得**用恐吓、灾难化、羞耻或虚假紧迫感换取注意力，也不用于规避 AI 检测。"
            "Use to remove AI-flavoured prose from patient-facing writing without distorting facts."
        ),
        emoji="🪶",
        label_zh="去 AI 腔",
        label_en="De-AI Prose",
        summary_zh="去掉科普与社区文章的 AI 腔，保留事实与证据等级。",
        summary_en="Remove AI-flavoured prose, keep the facts and evidence grades.",
        adapted=(
            "只导入方法层（`SKILL.md` / `README.md` / `CHANGELOG.md`）；"
            "上游 `evals/`（基准数据与盲评提示）不带入。"
            "正文顶部加范围声明：**必须保留证据等级与不确定性**，"
            "不得为了提高可读性而强化结论；不得用恐吓或虚假紧迫感。"
        ),
        preamble=(
            "> ## 改写的硬边界（优先级高于本文其余内容）\n"
            ">\n"
            "> - **事实与证据等级不动**：可以改语气、节奏、句式；**不可以**改结论强度、"
            "去掉不确定性表述、或把「可能」写成「会」。\n"
            "> - **不得恐吓**：禁止用灾难化、羞耻、虚假紧迫感换取注意力，这在本项目属于违规。\n"
            "> - 涉及医学内容的改写，仍须遵守 `xyb-evidence-guard` 与 `xyb-medical-disclaimer`。\n"
            "> - 本技能**不用于规避 AI 检测或伪造作者身份**。\n"
        ),
    ),
    Import(
        slug="aesthetic-brain",
        source_repo="opencare-skillhub/agent-taste-seed-system",
        source_license="NONE",
        expert="xyb-community-ops",
        body_from="TASTE.md",
        include=("TASTE.md", "AGENT-INJECTION.md", "README.md", "references"),
        readiness="可直接使用（设计取向参考库，无外部依赖）",
        name="aesthetic-brain",
        description=(
            "当社区运营要做配图、版式、封面或视觉取向判断时使用。提供一套**有来源的审美参照**"
            "（艺术史流派与视觉种子），把「好看」拆成可讨论的具体取向，避免套模板。"
            "**只管视觉取向，不生成医学结论**。"
            "Use for visual direction and layout judgement in community content."
        ),
        emoji="🎨",
        label_zh="审美参照库",
        label_en="Visual Direction Reference",
        summary_zh="艺术史流派与视觉种子，把「好看」变成可讨论的具体取向。",
        summary_en="Art-history schools as concrete visual direction references.",
        adapted=(
            "上游没有 `SKILL.md`，技能正文在 `TASTE.md`（导入器以 `body_from` 显式指定，"
            "不会写出占位正文）。只导入正文与 `references/`（艺术史章节与视觉种子），"
            "**不导入** `deploy/` 的安装脚本（面向 Claude Code / OpenClaw 的部署文件与本平台无关）。"
        ),
        preamble=(
            "> ## 适用范围（优先级高于本文其余内容）\n"
            ">\n"
            "> - 本技能只给**视觉取向与版式判断**，不产出医学内容、不做诊断建议。\n"
            "> - 与本项目的品牌一致：小胰宝的配色以**薄荷绿**为基色（见 `dashboard/src/styles/`），"
            "视觉建议不得与已定品牌色冲突。\n"
            "> - 涉及患者形象、病友故事与影像素材时，先过 `xyb-record-desensitize`："
            "**不得使用可识别到个人的素材**。\n"
        ),
    ),
    Import(
        slug="dicom-download",
        source_repo="opencare-skillhub/xyb_dicom_download_skills",
        source_license="Apache-2.0",
        expert="xyb-mdt-imaging",
        include=(
            "SKILL.md",
            "README.md",
            "LICENSE",
            "CONTRIBUTING.md",
            "pyproject.toml",
            "dicom_download.toml.example",
            "urls.txt.example",
            "common_utils.py",
            "main.py",
            "multi_download.py",
            "references",
        ),
        readiness="需配置（需要患者本人的医院门户账号与检查链接；依赖 Playwright，浏览器缓存见 .cache/xyb-playwright）",
        name="dicom-download",
        description=(
            "当患者要把自己在医院影像平台上的 CT / MRI 原始影像（DICOM）取回本地时使用。"
            "脚本用 **Playwright 在本机**驱动医院门户，账号与影像都只留在本机；"
            "**只做取回**，不做影像判读，也不绕开医院授权。"
            "Use to fetch a patient's own DICOM studies from hospital portals, locally."
        ),
        emoji="🩻",
        label_zh="影像资料取回（DICOM）",
        label_en="DICOM Study Download",
        summary_zh="用本人账号把医院影像平台的原始 DICOM 取回本机；只取回不判读。",
        summary_en="Fetch your own DICOM studies from hospital portals; retrieval only.",
        adapted=(
            "只导入脚本与文档（17 个文件）；上游 `uv.lock` 与生成的下载产物不带入。"
            "正文顶部加范围声明：需患者本人账号、影像与账号不出机、**不做影像判读**、"
            "不绕开授权、不收费（资料本就属于患者）。上游已有的伦理与安全表述保留。"
        ),
        preamble=(
            "> ## 本项目的使用范围（优先级高于本文其余内容）\n"
            ">\n"
            "> - **只做取回，不做判读。** 本技能把 DICOM 取回本机；影像怎么看、说明什么，"
            "由影像科视角按 `imaging-report-reading` 另行处理，且不替代放射科医生。\n"
            "> - **需要患者本人账号**：用你自己的医院门户账号登录。账号、检查链接与影像"
            "**只留在本机**，不上传、不转发、不进日志。\n"
            "> - **不绕开任何授权或访问控制**，不尝试下载不属于本人或未授权共享的影像。\n"
            "> - **不收费**：患者取回自己的影像资料不应产生费用；如遇平台要求付费，"
            "如实说明并建议走医院正式流程。\n"
            "> - 依赖 Playwright。浏览器缓存在 `<repo>/.cache/xyb-playwright`；"
            "未安装时如实告知，不要假装已开始下载。\n"
            "> - 与本视角的「不使用浏览器工具」约定不冲突：这里是**本机脚本**在跑，"
            "不是让 agent 去浏览网页。\n"
        ),
    ),
    Import(
        slug="trial-matching-advanced",
        source_repo="opencare-skillhub/clinical-trial-matching",
        source_license="NONE",
        declared_license="MIT",
        has_licence_claim=True,
        expert="xyb-trial-matching",
        include=("SKILL.md", "README.md", "references"),
        readiness="需改写（上游用自己的检索通道；本项目改为调用已配置的四通道工具，不新增依赖）",
        name="trial-matching-advanced",
        description=(
            "当需要的不是「列出试验」而是**逐条判断符合性**时使用：把患者条件与每个试验的"
            "入排标准逐项对照，输出通过/待确认/不符合及原因，并给出该向研究团队确认的问题。"
            "**不给入组结论**，也不在没有真实登记号时编造编号。"
            "Use for item-by-item eligibility analysis against real registry records."
        ),
        emoji="🔬",
        label_zh="入排逐条对照",
        label_en="Eligibility Item Analysis",
        summary_zh="把患者条件与试验入排逐条对照，标注通过/待确认/不符合及原因。",
        summary_en="Compare the patient against each eligibility criterion, item by item.",
        adapted=(
            "上游自带检索通道与自有资料；本项目**不引入新的数据源**，改为要求先经 "
            "`trial-search` 用四通道工具取得真实登记记录，再对记录做逐条对照。"
            "另：上游仓库**没有 LICENSE 文件**（实测 `spdx_id` = NONE），仅在 "
            "`SKILL.md` 内声明 `license: MIT`；两者都已记入溯源头，"
            "该声明不足以作为对外分发的许可依据，补许可前按 NONE 处理。"
        ),
        preamble=(
            "> ## 与 `trial-search` 的分工（优先级高于本文其余内容）\n"
            ">\n"
            "> 本技能**只做逐条对照**，不自己检索。顺序固定：\n"
            ">\n"
            "> 1. 先用 `trial-search` 通过四通道工具取得**真实登记记录**；\n"
            "> 2. 再用本技能把患者条件与每条记录的入排标准逐项对照；\n"
            "> 3. 输出「通过 / 待确认 / 不符合」三态与原因，**不给入组结论**。\n"
            ">\n"
            "> - **没有真实登记号（NCT / CTR / ChiCTR / Veeva UTN）的记录一律不得出现在结果里**；"
            "宁可说「本次未取得可核验记录」。\n"
            "> - 上游正文里提到的自有检索接口在本项目**不使用**；一律走平台已配置的四通道工具。\n"
            "> - 通道故障（索引为空 / 会话失效 / 验证拦截）必须如实说明，不得当成「没有匹配试验」。\n"
            ">\n"
            "> ### 工具名对照（上游名字在本项目不可用）\n"
            ">\n"
            "> | 上游正文写的 | 本项目实际可用的 |\n"
            "> |---|---|\n"
            "> | `mcp__oncology_db__search_trials` | 通道 `clinicaltrials`（工具 `search_clinical_trials`） |\n"
            "> | `mcp__chictr__search_trials` | 通道 `chictr`（工具 `search_trials`） |\n"
            "> | —（上游没有） | 通道 `veeva`（工具 `search_studies`） |\n"
            "> | —（上游没有） | 中国药物临床试验登记平台：走 `chinadrugs-collect` 技能，不是工具 |\n"
            ">\n"
            "> 正文 `## References` 里列的 `chictr-search-guide.md` / `egfr-tki-resistance.md` / "
            "`kras-g12c-landscape.md` 本次**未随包导入**（与胰腺癌场景无关或已有专门技能），"
            "看到这些文件名时不要去找文件。\n"
        ),
    ),
    Import(
        slug="chinadrugs-collect",
        source_repo="opencare-skillhub/chinadurgtrials",
        source_license="NONE",
        expert="xyb-trial-matching",
        include=("SKILL.md", "README.md", "references", "scripts"),
        readiness="需配置（需要患者本人的浏览器会话 Cookie；未配置时只给获取步骤）",
        name="chinadrugs-collect",
        description=(
            "当需要检索**中国药物临床试验登记与信息公示平台**（chinadrugtrials.org.cn）的"
            "登记记录时使用。该通道不是 MCP：它由本技能用**你本人的浏览器会话**驱动，"
            "记录落本机。未配置会话时明确告知不可用，**不绕过、不猜测结果**。"
            "Use for the China drug trial registry via your own browser session."
        ),
        emoji="🇨🇳",
        label_zh="中国药物临床试验登记平台",
        label_en="China Drug Trial Registry",
        summary_zh="用本人浏览器会话检索中国药物临床试验登记平台；记录落本机。",
        summary_en="Search the China drug trial registry with your own browser session.",
        adapted=(
            "按实际形态接入：该通道**不是 MCP 服务**（上游没有 server.py），"
            "而是 CLI + 会话 Cookie 的技能，因此不再作为 MCP 播种，改为导入本技能。"
            "只导入脚本与流程，**不导入任何凭据**（config 模板随包，真实值本机填写）。"
        ),
        preamble=(
            "> ## 通道定位与凭据（优先级高于本文其余内容）\n"
            ">\n"
            "> - 中国药物临床试验登记与信息公示平台这一通道**不是 MCP 服务**，"
            "由本技能用**你本人的浏览器会话**检索；这与另外三个 MCP 通道的实现方式不同。\n"
            "> - 会话 Cookie 只落在你本机（`~/.xyb-chinadrugtrials/config.json`，权限 0600），"
            "不进仓库、不回显、不进日志。\n"
            "> - **未配置会话时，如实说这一通道本次不可用**，不要把它说成「没有相关试验」"
            "（见 `trial-search` 技能的故障四态）。\n"
            "> - 不绕过站点的任何验证或访问控制。\n"
        ),
    ),
    Import(
        slug="record-organizer",
        source_repo="opencare-skillhub/Medical-Record-Organizer",
        source_license="NONE",
        expert="xyb-mdt-surgery",
        include=(
            "SKILL.md",
            "README.md",
            "requirements.txt",
            "references",
            "scripts",
        ),
        readiness="需安装依赖（PyMuPDF / python-docx / openpyxl / Jinja2）；OCR 与 ASR 需另配外部服务",
        name="record-organizer",
        description=(
            "当患者要给一堆零散资料（化验单照片、PDF 报告、出院小结、基因报告）做整理、"
            "分类归档或生成结构化病例档案时使用。**全程在本机处理，不上传、不发布**；"
            "产出结构化档案与时间线，供各 MDT 视角读取。"
            "Use to organise scattered medical records into a structured local case file."
        ),
        emoji="🗂️",
        label_zh="病案整理归档",
        label_en="Medical Record Organizer",
        summary_zh="把零散化验单/报告/出院小结整理成结构化病例档案，全程本机。",
        summary_en="Turn scattered records into one structured local case file.",
        adapted=(
            "作为患者向病案整理能力导入，只取方法与脚本（`SKILL.md`/`references`/`scripts`/"
            "`requirements.txt`），**不导入**上游用于演示的 `output*/`（约 1000 个生成文件，"
            "使仓库膨胀到 141MB）。在正文顶部加范围声明：数据不出机、不发布公网、"
            "不替代医生诊断，并注明部分环节需要外部 OCR/ASR 凭据。"
        ),
        preamble=(
            "> ## 本项目的使用范围（优先级高于本文其余内容）\n"
            ">\n"
            "> - **全部在本机处理**：资料不上传、不发布、不写入任何公网服务。\n"
            "> - 产出是**结构化档案与时间线**，供各 MDT 视角读取；它**不是诊断**，\n"
            ">   也不替代医生对报告的判读。\n"
            "> - 依赖需在本机安装（见 `requirements.txt`）；OCR 与语音转写需要另配外部服务，\n"
            ">   **未配置时明确告知用户该环节不可用**，不要假装已完成识别。\n"
            "> - 归档前建议先脱敏（姓名、住院号、身份证号、电话），平台自带脱敏技能可配合使用。\n"
        ),
    ),
    Import(
        slug="nccn-download",
        source_repo="opencare-skillhub/nccn-guideline-downloader",
        source_license="Apache-2.0",
        expert="xyb-community-ops",
        include=(
            "SKILL.md",
            "README.md",
            "LICENSE",
            "references",
            "scripts",
            "assets/config.json.template",
        ),
        readiness="需配置（需要本人 NCCN 账号会话；未配置时只给获取步骤）",
        name="nccn-download",
        description=(
            "当需要按主题、语言与癌种下载 NCCN 指南与患者手册时使用。"
            "只提供**下载流程与脚本**；需要本人 NCCN 账号会话，且**不分发任何指南 PDF**"
            "（指南正文受版权保护）。"
            "Use to download NCCN guidelines/patient manuals with the user's own account."
        ),
        emoji="📘",
        label_zh="NCCN 指南下载",
        label_en="NCCN Guideline Download",
        summary_zh="按主题/语言/癌种下载 NCCN 指南；需本人账号；只发流程不发 PDF。",
        summary_en="Download NCCN guidelines with your own account; process only, no PDFs.",
        adapted=(
            "只导入脚本与流程说明，**不导入任何凭据文件**（上游 cookie/config 模板随包，"
            "真实值一律由用户本机填写）；并在正文顶部明确『只分发下载器，不分发指南正文』。"
        ),
        preamble=(
            "> ## 版权与凭据（优先级高于本文其余内容）\n"
            ">\n"
            "> - 本技能**只提供下载流程与脚本**。NCCN 指南与患者手册正文受版权保护，"
            "**不得随本项目分发、不得上传到任何公开知识库**。\n"
            "> - 需要你**本人**的 NCCN 账号会话才能下载；凭据只落在你本机，"
            "不进仓库、不回显、不进日志。\n"
            "> - 未配置账号时，只给出获取步骤，不假装能下载。\n"
        ),
    ),
    Import(
        slug="trial-intel-push",
        source_repo="opencare-skillhub/clinicaltrials-intel-skill",
        source_license="Apache-2.0",
        expert="xyb-community-ops",
        include=("SKILL.md", "references", "docs", "LICENSE"),
        readiness="方法论层（推送渠道需自备凭据；本项目不含任何生产密钥）",
        name="trial-intel-push",
        description=(
            "当社区运营需要把临床试验更新整理成可推送的情报简报时使用。"
            "覆盖采集→清洗→摘要→多通道推送的流程设计与字段规范；"
            "**不包含任何推送凭据**，未配置渠道时只产出简报正文。"
            "Use when turning trial updates into a push-ready community brief."
        ),
        emoji="📣",
        label_zh="试验情报简报",
        label_en="Trial Intel Brief",
        summary_zh="试验更新→清洗→简报的流程与规范；凭据自备，未配置只出正文。",
        summary_en="Trial-update to push-ready brief pipeline; bring your own credentials.",
    ),
)


def sources() -> dict[str, Path]:
    raw = os.environ.get("XYB_SKILL_SOURCES")
    mapping = json.loads(raw) if raw else DEFAULT_SOURCES
    return {name: Path(value).expanduser() for name, value in mapping.items()}


def _frontmatter_block(item: Import) -> str:
    return "\n".join(
        [
            "---",
            f"name: {item.name or item.slug}",
            f"description: {item.description or item.slug}",
            "metadata:",
            "  octop:",
            f'    emoji: "{item.emoji}"',
            "    label:",
            f'      zh: "{item.label_zh}"',
            f'      en: "{item.label_en}"',
            "    summary:",
            f'      zh: "{item.summary_zh}"',
            f'      en: "{item.summary_en}"',
            f"source_repo: {item.source_repo}",
            f"source_license: {item.source_license}",
            *(
                [f"declared_license: {item.declared_license}"]
                if item.declared_license
                else []
            ),
            f"adapted: {ADAPTED_DATE}",
            f"readiness: {item.readiness}",
            "---",
            "",
        ]
    )


ADAPTED_DATE = "2026-10-02"

FRONTMATTER_RE = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n", re.DOTALL)


def _strip_frontmatter(text: str) -> str:
    match = FRONTMATTER_RE.match(text)
    return text[match.end() :] if match else text


def _copy_tree(src: Path, dest: Path, include: tuple[str, ...]) -> list[str]:
    """Copy only the listed paths, skipping build artefacts. Returns copied rels."""
    copied: list[str] = []
    for entry in include:
        source = src / entry
        if not source.exists():
            continue
        if source.is_file():
            target = dest / entry
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            copied.append(entry)
            continue
        for path in sorted(source.rglob("*")):
            if not path.is_file():
                continue
            if EXCLUDED_DIRS & set(path.parts):
                continue
            rel = path.relative_to(src)
            if rel.as_posix() in EXCLUDED_FILES or path.name in EXCLUDED_NAMES:
                continue
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            copied.append(rel.as_posix())
    return copied


def _apply_rewrites(dest: Path, rewrite: dict[str, tuple[tuple[str, str], ...]]) -> None:
    for rel, pairs in rewrite.items():
        path = dest / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for before, after in pairs:
            text = text.replace(before, after)
        path.write_text(text, encoding="utf-8")


def run_import(item: Import, src_root: Path, *, check: bool) -> int:
    """Import one skill. Returns the number of changed files."""
    if not src_root.is_dir():
        print(f"  SKIP {item.slug}: source checkout not found at {src_root}", file=sys.stderr)
        return 0

    dest = item.dest
    if check:
        if not (dest / "SKILL.md").is_file():
            print(f"  MISSING {dest.relative_to(REPO)}", file=sys.stderr)
            return 1
        text = (dest / "SKILL.md").read_text(encoding="utf-8")
        problems = [
            f"missing {key}"
            for key in ("source_repo:", "source_license:", "adapted:", "readiness:")
            if key not in text
        ]
        # A repository with no LICENSE file but a licence claim inside it must
        # carry both values, so nobody later mistakes the claim for a grant.
        # Checked in both directions: a claim that was not recorded is as much a
        # defect as a recorded claim that upstream does not make.
        recorded = "declared_license:" in text
        if item.has_licence_claim and not recorded:
            problems.append("upstream declares a licence but declared_license is missing")
        if recorded and not item.has_licence_claim:
            problems.append("declared_license recorded but upstream makes no licence claim")
        if problems:
            print(f"  HEADER {item.slug}: {', '.join(problems)}", file=sys.stderr)
            return 1
        return 0

    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    copied = _copy_tree(src_root, dest, item.include)

    skill_md = dest / "SKILL.md"
    body_source = dest / item.body_from if item.body_from else skill_md
    if body_source.is_file():
        body = _strip_frontmatter(body_source.read_text(encoding="utf-8"))
    elif skill_md.is_file():
        body = _strip_frontmatter(skill_md.read_text(encoding="utf-8"))
    else:
        # Fail loudly rather than shipping a placeholder: an empty skill body
        # looks installed and does nothing.
        print(
            f"  BODY {item.slug}: no body found "
            f"({item.body_from or 'SKILL.md'} absent); refusing to write a stub",
            file=sys.stderr,
        )
        shutil.rmtree(dest, ignore_errors=True)
        return 1
    preamble = f"{item.preamble}\n" if item.preamble else ""
    skill_md.write_text(_frontmatter_block(item) + preamble + body, encoding="utf-8")

    _apply_rewrites(dest, item.rewrite)
    print(f"  {item.slug} -> {dest.relative_to(REPO)} ({len(copied)} files)")
    return len(copied)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--list", action="store_true", help="show the import table")
    parser.add_argument("--only", action="append", default=[], help="import only this slug")
    parser.add_argument("--check", action="store_true", help="verify imports and headers")
    args = parser.parse_args()

    if args.list:
        for item in IMPORTS:
            print(f"{item.slug:<20} {item.expert:<20} {item.source_license:<12} {item.readiness}")
        return 0

    table = [item for item in IMPORTS if not args.only or item.slug in args.only]
    if args.only:
        known = {item.slug for item in IMPORTS}
        unknown = [slug for slug in args.only if slug not in known]
        if unknown:
            print(f"unknown skill(s): {', '.join(unknown)}", file=sys.stderr)
            print(f"known: {', '.join(sorted(known))}", file=sys.stderr)
            return 2

    src = sources()
    failures = 0
    total = 0
    for item in table:
        root = src.get(item.source_repo.split("/")[-1])
        if root is None:
            print(f"  SKIP {item.slug}: no source mapping for {item.source_repo}", file=sys.stderr)
            continue
        result = run_import(item, root, check=args.check)
        if args.check:
            # run_import returns 1 for a missing/broken provenance header; that
            # must count as a failure, otherwise the gate is vacuous.
            failures += result
        else:
            total += result

    if args.check:
        if failures:
            print(f"\n{failures} import(s) incomplete", file=sys.stderr)
            return 1
        print(f"checked {len(table)} import(s)")
        return 0

    print(f"\nimported {len(table)} skill(s), {total} file(s) copied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
