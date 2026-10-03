# 小胰宝 Octop 设计文档

**版本** v1.0 · 2026-10-01
**对应需求** `XYB-REQUIREMENTS.md` v1.0
**配套测试** `XYB-TEST-PLAN.md` v1.0（命名替换的验收门禁：`scripts/xyb_name_audit.py`）
**上游基线** `opencare-skillhub/xyb-Octop` @ `e473dd3`（1.0.2b5）
**状态** P0–P5 已实施，待验收（见下方实施状态表）

---

## 〇、实施状态（2026-10-02 更新）

| 阶段 | 内容 | 状态 | 关键验证证据 |
|---|---|---|---|
| **P0 · 地基** | 改动追踪 + 校验脚本骨架 | ✅ 完成 | `XYB-UPSTREAM-DIFF.md`、`XYB-SKILL-LICENSE.md`、6 个 `xyb-*` 校验脚本 |
| **P1 · 临床四通道** | MCP 播种 + 四通道冒烟 | ✅ 完成 | **5 个 MCP 真实握手通过**（veeva 12 工具 / chictr 9 / clinicaltrials 3 / pubmed 5 / dayi 2），1 个因缺 key 优雅跳过，**0 失败**；四通道 **3 可用**（clinicaltrials / chictr / veeva），chinadrugs 需本人会话；`octop xyb init-mcp` 幂等 |
| **P2 · MDT 专家** | 17 个专家模板 + **5 个护栏技能** | ✅ 完成 | `xyb-check-experts.py` → `experts=17 checks=340 failed=0`（含 G8 角色专属禁令校验）；内置技能 **6** 个（含 5 护栏：证据 / 反幻觉 / 术语 / 免责 / **脱敏**） |
| **P3 · 品牌 UI** | 改名 + logo + 中文 + 薄荷绿配色 + 插件默认 | ✅ 完成 | `xyb-check-branding.sh` → `failed=0`（范围已含全部 dashboard `.tsx`）；`xyb-brand.py --check` → 通过；**真实浏览器**验证菜单为薄荷浅绿 `#EAF6F3`、品牌色 `#2F8F80`；娱乐类插件默认关闭（12 个 + 8 个测试） |
| **P4 · 技能入库** | 分批落地技能 | ✅ **完成**（22 个技能：13 导入 + 4 自研 + 5 内置护栏，达设计目标） | **13 个技能带溯源头入库**（`distress-screening` / `chictr-collect` / `chinadrugs-collect` / `trial-intel-push` / `nccn-download` / `record-organizer` / `trial-matching-advanced` / `dicom-download` / `humanizer` / `aesthetic-brain` / `wechat-article` / `lab-to-profile` / `pdf-translate`），另有 4 个自研角色技能（含共享的 `case-summary` / `trial-search` / `imaging-report-reading` / `genomic-report-reading` / `surgical-resectability`）；其余列为待办（见 §十一） |
| **P5 · 主持团队** | `kind=team` 编排 + 端到端 | ✅ 完成（方案变更） | `octop xyb init-mdt` 实跑：**11 名专家实例 + 1 个 `kind=team` 主持人**；已存在团队会**增补成员并重新播种编排规则**（实跑 3 人 → 11 人），三次执行幂等 |

### 与设计文档的四处偏离（均已留痕）

4. **chinadrugs 不是 MCP。** 设计文档 §4.2 把它列为 MCP 服务，实现时才发现上游
   `chinadurgtrials` **没有 `server.py`**：它是一个用**会话 Cookie** 驱动的 CLI 技能。
   按 MCP 播种会写入一条永远起不来的命令（探针因此长期误报 FAIL）。现已改为
   **技能入库**（`chinadrugs-collect`，落在试验专员），四通道中三个由 MCP 承载、
   一个由技能承载。


1. **`kind=team` 不是专家 manifest 字段。** 设计文档 §5.5 假设在专家库里放一个 `kind=team` 的专家包即可。实测 `catalog.py` 完全不读 `kind`（`grep` 零命中），团队只能通过 `AgentCreateSpec(kind="team", member_ids=[...])` 创建，而成员必须是**真实存在的 agent id**。因此主持团队改为由 `octop xyb init-mdt` 命令创建，而不是一个专家模板。见 `XYB-UPSTREAM-DIFF.md` C-1。
2. **不改上游团队模板。** 见 `XYB-UPSTREAM-DIFF.md` C-1 的方案变更说明：上游团队模板被所有团队共用，医学协议改为写进实例工作区。
3. **AC-1 收窄为「产物名 ASCII」。** 界面按产品决定显示中文「小胰宝」，因此 `I14/I15` 只门禁包名、脚本名、产物名与商店标识；界面展示名改由 `I5`/`I6` 断言为中文。见 `XYB-TEST-PLAN.md` §1。

### 环境级阻塞（非代码问题，已记录）

| 项 | 现象 | 处置 |
|---|---|---|
| ~~chictr MCP 握手~~ **已解决** | 该包 `postinstall` 执行 `playwright install chromium`，而 macOS 默认缓存 `~/Library/Caches/ms-playwright` 被 TCC 锁住（`__dirlock` 无法删除），安装中止、包半装、stdio 无输出 | **改用自有浏览器缓存**：`PLAYWRIGHT_BROWSERS_PATH=<repo>/.cache/xyb-playwright npx playwright@1.49.1 install chromium`。探针默认使用该路径，引导脚本会检测并提示。实测 chictr 握手通过（9 工具） |
| `clinicaltrials` 直连 | 本机 Python 报 `CERTIFICATE_VERIFY_FAILED`（curl 与 Node 均正常），是 TLS 中间代理的 CA 未进 Python 信任库 | 探针区分「本地信任问题」与「远端不可达」，并在直连受阻时回退到 MCP 通道如实报告；可用 `XYB_HTTP_CA_BUNDLE` 指定代理 CA 恢复直连检查 |
| chinadrugs 通道 | 需要患者本人浏览器会话，本机未配置 | 探针按 `NO_SESSION` 报告并给出配置路径，不误报 0 条 |



---

## 一、设计总览

### 1.1 一句话架构

**能用数据解决的，不写代码；必须写代码的，改动点集中、可枚举、可回滚。**

三种改动类型，按优先级排序：

| 类型 | 含义 | 占比（目标） | 例子 |
|---|---|---|---|
| **加数据** | 往既有扫描目录放文件，零代码改动 | ~70% | 16 个专家包、22 个技能、品牌资源 |
| **加配置** | 写配置/清单，少量代码读取 | ~20% | 5 个 MCP 服务声明、默认插件开关 |
| **改代码** | 改 Python / React | ~10% | 品牌串替换、MCP 首次播种、logo 渲染 |

### 1.2 扩展点映射总表

| 需求 | 承载点 | 类型 | 上游文件是否被改 |
|---|---|---|---|
| FR-1 品牌 | `dashboard/index.html`、`public/manifest.json`、`public/*logo*`、`locales/*.json`、`pyproject.toml` | 改代码（替换）+ 加资源 | ✅ 改 |
| FR-2 技能（通用护栏） | `src/octop/infra/agents/builtin_skills/xyb-*/` | 加数据 | ❌ 不改 |
| FR-2 技能（角色专属） | `experts/library/<id>/skills/` | 加数据 | ❌ 不改 |
| FR-3 MCP | `src/octop/infra/connectors/xyb_defaults.py`（新增）+ CLI | 加代码（新增文件） | ❌ 不改既有文件 |
| FR-4 专家 | `experts/library/xyb-*/` | 加数据 | ❌ 不改 |
| FR-4 主持团队 | `experts/library/xyb-mdt-chair/` + `.octop/manifest.json`（`kind=team`） | 加数据 | ❌ 不改 |
| FR-5 四通道 | MCP 声明 + `experts/library/xyb-trial-matching/skills/` | 加数据 + 加配置 | ❌ 不改 |
| FR-6 脱敏 | maskdesk 接入（技能/插件） | 加数据 | ❌ 不改 |

> **关键判断**：上游 `experts/catalog.py`、`builtin_skills/`、`plugins/bundled/` 都是**目录扫描**机制——往目录里放文件即生效。这是本项目能做到"少改代码"的根本原因。

---

## 二、UI 品牌改造设计（FR-1）

### 2.1 改动清单

| # | 文件 | 改动 | 依据 |
|---|---|---|---|
| 1 | `dashboard/index.html` | `<title>`、`apple-mobile-web-app-title` → 小胰宝 | 实测 L29/L32 |
| 2 | `dashboard/public/manifest.json` | `name` / `short_name` → 小胰宝 | 实测 L3/L4 |
| 3 | `dashboard/public/logo_horizontal_{dark,white}.png` | 换新 logo（横版） | 侧栏使用 |
| 4 | `dashboard/public/logo_vertical_{dark,white}.svg` | 换新 logo（竖版） | 登录/启动页使用 |
| 5 | `dashboard/public/pwa-192.png`、`pwa-512.png` | 由 logo 重生成 | PWA 图标 |
| 6 | `dashboard/public/apple-touch-icon.png`、`favico.svg` | 由 logo 重生成 | 收藏/桌面图标 |
| 7 | `dashboard/src/locales/zh.json` / `en.json` | 品牌词替换 + 小胰宝专有词 | i18n |
| 8 | `src/octop/i18n/{zh,en}.json` | 后端品牌词 | i18n |
| 9 | `pyproject.toml`、`dashboard/package.json` | 包名 → `xiaoyibao-octop` | 命名 |
| 10 | `README.md` / `README_CN.md` | 中文小胰宝说明（新写，不改上游内容语义） | 文档 |
| 11 | `EXPERTS` 表情/吉祥物资源 | 保留上游 mascot 或替换（待决 §9.8） | 待定 |

### 2.2 logo 处理

给定 logo：
```
https://picgo-1302991947.cos.ap-guangzhou.myqcloud.com/images/Pop%20Mart%20Character%20Front%20View%20(2).png
```

处理流程：

1. 下载原图到 `dashboard/public/brand/logo-source.png`（保留原图，便于日后重生成）
2. 用 Python（Pillow）派生：
   - `logo_horizontal_white.png` / `logo_horizontal_dark.png`（横向，含文字）
   - `logo_vertical_white.svg` / `logo_vertical_dark.svg`（竖向；SVG 用路径描摹或直接嵌入 PNG 引用）
   - `pwa-192.png` / `pwa-512.png`（方形，圆角可选）
   - `apple-touch-icon.png`（180×180）
   - `favico.svg` / `favicon.ico`
3. 生成脚本落地为 `scripts/xyb-brand-assets.py`，**幂等可重跑**（换 logo 只改一处 URL）

> 若 logo 含白底不适合深色模式，深色版需描边或改用纯图形版——在 P3 阶段用截图对照确认。

### 2.3 品牌残留核查

新增 `scripts/xyb-check-branding.sh`：

- 全仓搜索 `Octop` / `octop`（排除 `.git`、`node_modules`、`target`、`uv.lock`、以及白名单：上游 API 路径 `/api/internal/mcp`、`octop.infra.*` 包名、`~/.octop/` 数据目录）
- 输出残留清单，**白名单外条数应为 0** 才通过

> **技术约束**：Python 包名 `octop` 与数据目录 `~/.octop/` **不建议改名**——改名会波及 1122 个 `.py` 的 import 与全部用户数据路径，收益仅为"包名好看"。**决定：只改产品展示名与 UI 名称，包名与数据目录保持 `octop`。** 这一条要写进 `XYB-UPSTREAM-DIFF.md`。

### 2.4 患者向默认配置

| 项 | 处理 |
|---|---|
| 默认专家库 | 保留上游 19 个 + 新增 **17** 个小胰宝专家包（库扫描自动带上；主持人不是专家包，见 §5.5 偏离说明） |
| 娱乐/工程类 bundled 插件 | `tetris`、`fun-facts`、`sports-scores`、`market-quotes`、`bilibili-anime` 等默认**关闭**（改 `plugins/seed.py` 的默认开关，或首次运行时写状态） |
| 默认语言 | `zh` |
| 首屏引导 | 使用小胰宝欢迎语；不暴露工程入口（导航结构不动，D3） |

---

## 三、技能体系设计（FR-2）

### 3.1 三条承载路径（关键设计）

Octop 有三处可放技能，选择依据是**"谁能用到"**：

| 路径 | 生效范围 | 适合放什么 | 本项目用量 |
|---|---|---|---|
| `infra/agents/builtin_skills/xyb-*/` | **每个**专家的工区（`_builtin_skills`） | 通用硬约束：信源分级、反幻觉自检、术语科普、免责声明、**病历脱敏** | **5 个** |
| `experts/library/<id>/skills/<name>/` | 该专家实例 | 角色专属技能 | **约 18 个** |
| 技能包（DB 安装） | 按需安装到单专家 | 外部技能（可整包停用） | 备选 |

> **为什么不全部塞 `builtin_skills/`**：22 个技能进每个专家工区，会让所有专家的上下文与磁盘都背着一堆无关技能。通用硬约束才配进 `builtin_skills/`。

### 3.2 通用硬约束技能（4 个，进 `builtin_skills/`）

| 技能名 | 作用 | 来源 |
|---|---|---|
| `xyb-evidence-guard` | 信源分级 A/B/C/D + 「低证据模式」（高可信来源 <2 条时只输出讨论要点） | 移植自 `clinical-learning-subscription` 的 `source-verify` + `output-format` 设计 |
| `xyb-anti-hallucination` | 反幻觉守则：未披露就写未披露、跨试验/跨人群不可外推、不预测生存期 | 移植自 PI Desktop `XYB-ASSISTANTS.md` §4 + `xiaoyibao提示词_复核自检版` 思路 |
| `xyb-term-glossary` | 术语一行约 20 字通俗解释 | 同上 |
| `xyb-medical-disclaimer` | 统一免责声明 + 「不替代医生诊断」标识 + 全程简体中文、禁过程句 | 同上 |

这 4 个是**全套专家的公共地基**——把它们放进 `builtin_skills/`，等于给 17 个专家自动装上了统一的护栏，不必在每个专家的 SOUL.md 里重复抄一遍（SOUL.md 只写该角色特有的红线）。

### 3.3 角色专属技能（约 18 个）

#### 批 1 · 医学解读（患者向，6）

| 技能 | 源仓库 | 许可（实测） | 落点专家 | 适配方式 |
|---|---|---|---|---|
| `record-organizer` | `Medical-Record-Organizer` | ⚠️ NONE | **单点放置于 `xyb-mdt-surgery`**（原计划「全部 MDT」） | 包约 700KB；分发到 17 个专家会多出约 12MB 与数百个文件。患者上传资料时由该视角完成整理，其他视角按需索取结果；放置由 `tests/unit/naming/` 固定为有意决定 |
| `trial-matching-advanced` | `clinical-trial-matching` | ⚠️ NONE | `xyb-trial-matching` | 入排分析；检索改指四通道工具 |
| `distress-screening` | `skill-HADS-accessment` | ⚠️ NONE | `xyb-mdt-psych` | HADS 量表；**只本机，不发公网** |
| `tumor-marker-trend` | `graphify-xiaoyibao` | **AGPL-3.0** ⚠️ | `xyb-mdt-oncology` | 标志物趋势；传染性单独标注（待决 §9.2） |
| `lab-to-profile` | `aura_health_profile` | MIT-0 | `xyb-mdt-oncology` | 化验单→档案；**需阿里云百炼 key**，未配则降级为方法论 |
| `pdf-translate` | `pdf-translate` | ⚠️ NONE | 全部 MDT | 英文文献翻译（pdf2zh） |

#### 批 2 · 临床试验查询（4）

| 技能 | 源仓库 | 许可 | 落点专家 | 适配方式 |
|---|---|---|---|---|
| `target-trial-analysis` | `clinicaltrials-query-analysis` | Apache-2.0 | `xyb-trial-matching` | 靶点专题检索与报告流水线 |
| `trial-intel-push` | `clinicaltrials-intel-skill` | Apache-2.0 | `xyb-community-ops` | 采集-清洗-多通道推送 |
| `chictr-collect` | `chictr-trials-collector` | Apache-2.0 | `xyb-trial-matching` | 与 chictr MCP 衔接 |
| `chinadrugs-collect` | `chinadurgtrials` | ⚠️ NONE | `xyb-trial-matching` | 与 chinadrugs 通道衔接 |

#### 批 3 · 社区运营/内容（7）

| 技能 | 源仓库 | 许可 | 落点专家 |
|---|---|---|---|
| `wechat-article` | `xyb-wechat-article-generator` | ⚠️ NONE | `xyb-community-ops` |
| `humanizer` | `xyb-humanizer` | ⚠️ NONE（已有独立 git，PUBLIC） | `xyb-community-ops` |
| `whitepaper` | `xyb-whitepaper-writer` | ⚠️ NONE | `xyb-community-ops` |
| `url-to-wechat-html` | `xyb-wechat-article-transcription` | Apache-2.0 | `xyb-community-ops` |
| `wechat-news-board` | `pancrepal-wechat-news-board` | ⚠️ NONE | `xyb-community-ops` |
| `pdac-dailynews` | `pancreatic-cancer-dailynews-skill` | ⚠️ NONE | `xyb-community-ops` |
| `rag-content` | `RAG-content-processor` | Apache-2.0 | `xyb-community-ops` |

#### 批 4 · 研究/写作（3）

| 技能 | 源仓库 | 许可 | 落点专家 |
|---|---|---|---|
| `research-writer` | `awesome_research_writter_xiaoyibao` | MIT | `xyb-community-ops` |
| `psych-article-writer` | `inkstone-studio` | Apache-2.0 | `xyb-mdt-psych` + `xyb-community-ops` |
| `aesthetic-brain` | `agent-taste-seed-system` | ⚠️ NONE | `xyb-community-ops`（**你点名要求**） |

#### 批 5 · 影像/指南（2）

| 技能 | 源仓库 | 许可 | 落点专家 |
|---|---|---|---|
| `dicom-download` | `xyb_dicom_download_skills` | Apache-2.0 | `xyb-mdt-imaging` |
| `nccn-download` | `nccn-guideline-downloader` | Apache-2.0 ⚠️ 版权 | `xyb-community-ops` + MDT |

#### 附加 · 病历脱敏（maskdesk）

| 能力 | 源仓库 | 许可 | 承载 |
|---|---|---|---|
| 病历脱敏 | `maskdesk`（**仅参考规则集**） | Apache-2.0 | ✅ 已落地为内置技能 `xyb-record-desensitize`（方法论层，注入全部 17 个专家）。**未搬运 maskdesk 代码**：它是 Electron 桌面应用，不能作为技能装包。如需图形化圈选界面，再单独评估插件形态 |

> maskdesk 是本地优先的**脱敏工作台应用**，不是 MCP。设计为技能（方法层）+ 若需交互界面再包插件。**它解决一个真问题**：患者把病历贴给 AI 前先脱敏。

### 3.4 技能文档固定头

```yaml
---
name: <技能名>
description: <触发条件，精炼——专家靠它决定是否加载>
metadata:
  octop:
    emoji: "..."
    label:
      zh: "<中文名>"
      en: "<English>"
    summary:
      zh: "<一句话>"
source_repo: opencare-skillhub/<repo>
source_license: <SPDX 实测值>      # NONE 必须显式写出，不许留空
adapted: 2026-10-01
readiness: 可用 | 需配置密钥 | 方法论层 | 受限（注明）
---
```

**`readiness` 是关键字段**：如实标注这个技能在小胰宝里**能到什么程度**，避免"技能在列表里 = 功能已就绪"的错觉。

### 3.5 脚本依赖改写规则（硬性）

上游正文里「执行 `scripts/xxx.py`」这类指令，三选一：

| 出路 | 适用 | 写法 |
|---|---|---|
| **转方法论** | 整理/分析类 | 把脚本的判断逻辑改写成步骤，让专家用对话完成 |
| **指向已有工具** | 检索类 | 改指四通道 MCP 工具（如 `search_trials`） |
| **明确降级** | 依赖外部 key/环境 | 写「需本机具备 X；未满足时只做方法引导，不假装能跑」 |

**绝不保留无法执行的承诺。** 与 PI Desktop 同一条原则，但注意差异：**Octop 有终端，多数脚本能真跑**——所以这里的"可用"比例远高于 PI Desktop，改写时不要滥用"方法论层"降级。

### 3.6 许可台账

产出 `XYB-SKILL-LICENSE.md`，逐技能记录：

| 字段 | 说明 |
|---|---|
| 技能名 / 源仓库 | |
| `spdx_id` 实测值 | `gh api repos/... --jq .license.spdx_id` 的输出 |
| 可否再分发 | 有明确许可 = 可；NONE = **不可，除非补 LICENSE** |
| 传染性 | AGPL-3.0 需标注（若入库） |
| 已做的适配 | 改写了哪些指令 |

**实测汇总（2026-10-01）**

| 许可 | 数量 | 代表仓库 |
|---|---|---|
| Apache-2.0 | 8 | `clinicaltrials-query-analysis`、`chictr-trials-collector`、`maskdesk` |
| MIT / MIT-0 | 3 | `awesome_research_writter_xiaoyibao`、`aura_health_profile` |
| **AGPL-3.0** | 1 | `graphify-xiaoyibao` |
| **NONE ⚠️** | 12 | `Medical-Record-Organizer`、`clinical-trial-matching`、`skill-HADS-accessment`、`xyb-humanizer`、`agent-taste-seed-system` 等 |

> 12 个无许可仓库**都在你自己的组织下**，实际操作上你是权利人；但对外分发时说不清楚。**建议统一补 Apache-2.0（同组织已有先例）**——列为 NFR-3 与待决 §9.3。

---

## 四、MCP 与四大临床通道设计（FR-3 / FR-5）

### 4.1 配置形态

Octop 的自定义 MCP 存于**用户级 connector 文档**（`kind=custom-mcp`），经 `PUT /api/connectors/custom-mcp` 写入，支持 `stdio` 与 `streamable_http`。上游**没有预置播种**机制（已实测确认），所以新增：

```
src/octop/infra/connectors/xyb_defaults.py     # 新增：5 个 MCP 服务规格 + 幂等播种
src/octop/cli/commands/xyb.py                  # 新增：octop xyb init-mcp 命令
scripts/xyb-bootstrap.sh                       # 新增：一键引导（幂等）
```

**播种规则**（幂等，重复执行不重复写）：

| 规则 | 说明 |
|---|---|
| 只补不覆盖 | 已存在的同名 server 不覆盖，避免冲掉用户改过的配置 |
| 缺 key 则跳过并提示 | pubmed/metaso 需要 key；无 key 时**不写**，并输出获取方式 |
| 不代装依赖 | 不自动 `npm install`；只写配置 + 给出安装提示 |
| 支持 dry-run | `--dry-run` 打印将要写入的内容，不动状态 |

### 4.2 五个 MCP 服务规格

| server 名 | 通道 | 承载 | 配置要点 |
|---|---|---|---|
| `xyb-chictr` | **chictr** | `npx -y chictr-mcp-server@2.0.2` | **锁 2.0.2**（旧版参数不兼容，PI Desktop 已实测踩坑）；首次需 Playwright Chromium |
| `xyb-veeva` | **veeva** | 本地源码 → `python -m ctv_mcp_server` | **必须先建索引**；随仓库内置 |
| `xyb-chinadrugs` | **chinadrugs** | 采集器 + 本地服务 | 需患者本人浏览器会话 Cookie，落 `~/.xyb-chinadrugtrials/config.json`（0600） |
| `xyb-pubmed` | 文献（辅助） | `npx -y mcp-pubmed-llm-server@3.0.0` | 可选 `PUBMED_API_KEY` / `EMAIL`；无 key 亦可用（限速） |
| `xyb-metaso` | 通用检索（辅助） | `npx -y metaso-search-mcp@1.1.2` | 需 `METASO_API_KEY`；无 key 跳过 |
| `xyb-dayi` | 用药/疾病（辅助） | `npx -y @xiaoyibao_2025/dayi-mcp-server@0.1.7` | 无 key；日大医平台检索 |
| `xyb-clinicaltrials` | **clinicaltrials** | `npx -y xiaoyibao-clinical-trials@1.0.0` | 无 key；ClinicalTrials.gov API v2 |

### 4.3 通道能力抽象

对专家暴露的**不是散装工具名**，而是按通道组织的入口：

| 通道 | 关键工具 | 前置条件 |
|---|---|---|
| clinicaltrials | 关键词/疾病/地区检索 + 详情（含 PI、联系人、入排） | 无 |
| chinadrugs | 登记号/适应症/药物/申办方检索 + 详情归档 | **本人会话 Cookie** |
| chictr | `search_trials`（`keyword`/`registration_number`/`year`/`max_results` 全可选）+ `get_trial_detail` | 首次拉包 + 可能人工验证 |
| veeva | `search_studies` / `get_study_detail` / `create_watchlist` / `run_watchlist` / `get_change_digest` | **先建索引** |

### 4.4 故障四态（硬性）

**这是本设计最容易被做错、也最要紧的一处。** 检索失败绝不能被表述成"没有相关试验"。

| 态 | 表现 | 对患者的话术 |
|---|---|---|
| **索引为空** | veeva 返回 `INDEX_EMPTY` | 「本地还没建库，需要先导入一次数据」——**不是**「没有相关研究」 |
| **会话失效** | chinadrugs 返回反爬挑战页 | 「会话过期了，需要重新提供浏览器会话」——**不是**「0 条结果」 |
| **验证拦截** | chictr 返回 `CHALLENGED` | 引导本人完成站点验证（**不绕过**）；用户不在场就如实说查不到 |
| **确实 0 条** | 正常响应且结果为空 | 「这四个通道里目前没检索到匹配的试验，可以换个关键词/放宽条件」 |

实现方式：在 `xyb-trial-matching` 专家的技能文档里写死这套判定，并要求输出前自检。

### 4.5 版本漂移防护

| 风险 | 处置 |
|---|---|
| `@latest` 拉到不兼容版本 | 一律锁具体版本 |
| 全局旧版覆盖 | 用 `npx -y <pkg>@<version>`，不用全局命令 |
| CTV 旧库 schema（缺 `start_date` 列） | 首次引导时检测 `user_version`/列数，不符则提示重建；根治需在上游补 schema 迁移 |
| npm 包被撤 | 播种时校验可拉取；失败给明确提示，不静默 |

> **CTV 的 `CREATE TABLE IF NOT EXISTS` 隐患**：PI Desktop 已实测——旧表不会被新 schema 覆盖，且项目内无迁移机制，导致查询报 `no such column: start_date`。本项目在首启检测里加一条显式检查。

---

## 五、MDT 专家体系设计（FR-4）

### 5.1 名册（17 个专家模板 + 1 个主持团队）

| 组 | 数量 | 专家 |
|---|---|---|
| A · 肿瘤核心 MDT | 9 | surgery / oncology / imaging / pathology / intervention / radiation / nutrition / psych / palliative |
| B · 精准与试验 | 2 | genomics / trial-matching |
| C · 并发症与急症 | 5 | acute-gi-bleeding / acute-obstruction / acute-biliary / acute-infection / acute-hematology |
| D · 社区运营 | 1 | community-ops |
| 主持 | 1 | **mdt-chair**（`kind=team`） |

命名统一前缀 `xyb-`，id 与目录名一致。

### 5.2 专家包结构（以影像科为例）

```
experts/library/xyb-mdt-imaging/
├── manifest.json          # id/label{zh,en}/description/welcome_message/icon_name/color/
│                          # prompt_files[SOUL,AGENTS,BOOTSTRAP]/quick_prompts/task_examples
├── SOUL.md                # 影像视角人格 + 该角色特有红线
├── AGENTS.md              # 操作规程 + 意图路由
├── BOOTSTRAP.md           # 首次会话引导（含病情摘要采集提示）
├── USER.md                # 档案摘要（只读，脚本生成）
├── agents/
│   └── imaging-summary-organizer.md   # 子代理：整理影像报告字段
├── skills/
│   ├── imaging-report-reading/SKILL.md    # 影像报告字段解读
│   └── dicom-download/SKILL.md            # 批 5 技能
└── references/
    └── imaging-source-routes.yaml         # 信源路由（复用 upstream 写法）
```

### 5.3 专家输出骨架（统一）

每个 MDT 专家的输出结构**固定**，这是"问题清单而非结论"的落地方式：

```
【<角色>视角】
一、判断 <本专科核心问题> 的前提（现有 / 缺失）
二、本专科判断时看什么维度
三、可以问<科室>医生的具体问题 3–5 条
四、依据与不确定性（共识 / 有争议 / 数据缺失）
五、提醒
```

结尾固定一句：「以上是从<科室>角度整理的问题与维度，**不是<方案>建议，也不能替代<科室>医生的判断**。」

### 5.4 红线落地映射

需求 §七 的十条红线与 FR-4.2.1–4.2.8 的八条护栏，按下表落到具体文件：

| 红线 | 落点 |
|---|---|
| 不出诊断/处方（1）、不排名（2） | 每个专家 `SOUL.md` 的「你不做什么」段 |
| 未披露就写未披露（3）、统计边界（4）、不预测生存期（5）、早期数据标层级（6）、注册节点 vs 结果（7） | `builtin_skills/xyb-anti-hallucination/SKILL.md`（全局生效） |
| 出处可溯、信源分级 | `builtin_skills/xyb-evidence-guard/SKILL.md` |
| 术语科普（9）、免责声明（10） | `builtin_skills/xyb-term-glossary` + `xyb-medical-disclaimer` |
| 不煽情（8） | 每个专家 `SOUL.md` 的措辞要求段 |
| 视角非专家（FR-4.2.1） | 输出骨架首行 `【XX视角】` 硬格式 |
| 危机信号优先（FR-4.2.7） | 仅 `xyb-mdt-psych/SOUL.md` + 主持人 `AGENTS.md` 的例外条款 |
| 安宁疗护先澄清（FR-4.2.8） | 仅 `xyb-mdt-palliative/SOUL.md` 首段 |

### 5.5 主持团队（`xyb-mdt-chair`）

复用 Octop 原生 AgentTeams：主持人 `kind=team`，工具集仅 `agent_list` + 异步 `ask_agent` + 记忆 + 时间，**不挂文件系统/浏览器/搜索/MCP/技能**。上游模板已确立「协调人不是执行人」「不得原样转发用户原话」，与本定位天然吻合。

需要补的只有**医学编排规则**（写进主持人的 `AGENTS.md`）：

| 步骤 | 规则 |
|---|---|
| 1 · 危机信号筛查 | 出现自伤/自杀念头、绝望感、情绪失控 → **不走 MDT**，直接陪伴回应 + 给 12356；不派发 |
| 2 · 齐料 | 按 MDT 需要检查案情摘要完整性；缺关键项先问（缺影像分期、缺 PS 评分、缺既往治疗线） |
| 3 · 选视角 | 按问题选 **2–4 个**视角；仅当用户明确要求"从头到尾理一遍"才全开 |
| 4 · 派工 | 每个视角一份**改写后**的任务说明书（含目标、约束、交付格式、相关材料切片），禁止广播原话 |
| 5 · 汇总 | 分视角罗列 + **单独一段「各视角分歧点及其原因」** + 汇总问题清单 |
| 6 · 禁止 | 不得写"综合各位专家意见，建议……"（等于会诊结论）；不得复述成员全文；不得编造成员没说过的结论 |

**成本约束**：全开 = 16 次模型调用。所以第 3 步的"按需选 2–4 个"是硬要求。

### 5.6 与 PI Desktop 的差异（必须说明）

| 维度 | PI Desktop | 本项目 |
|---|---|---|
| 承载 | **子代理**（`~/.agents/subagents/`），只读 `Read` 工具，不可 1:1 对话 | **专家**，可 1:1 对话、有独立工作区与记忆，可组团队 |
| 数量上限 | 16（含内置 5 个工程角色） | 无硬上限（模板是数据，不占实例） |
| 患者能否单独找「影像视角」 | 不能（只能通过主持人派发） | **能**（这正是 D1 选择专家的理由） |
| 工具权限 | 一律 `[Read]` | 按角色给（如影像专家可给 DICOM 下载工具）——**需逐角色审慎配置** |

> **风险提示**：专家比子代理"更强"，也因此**更需要约束**。每个专家的 `tools` 与 `AGENTS.md` 都要逐个人工审——给医学角色加写权限或联网权限前，先问"这个角色真的需要它吗"。PI Desktop 用 `[Read]` 一刀切的做法在这里不适用，替代方案是**按角色白名单**，并在 P4 阶段逐角色过一遍。

---

## 六、数据与隐私设计（FR-6）

| 机制 | 实现 |
|---|---|
| 多用户隔离 | 复用 Octop 原生 JWT + 每专家独立工作区 + 独立 checkpoint |
| 最小化采集 | 专家 `BOOTSTRAP.md` 明确只收必要项，可用昵称；不索取姓名/手机号/身份证/病历号 |
| 脱敏前置 | maskdesk 通路：PDF/DOCX/MD → Markdown → 圈选建规则 → 打包导出；数据不出机 |
| 凭据本机化 | 会话 Cookie / API key 落 `~/.xyb-*/config.json`（0600）；不进仓库、不回显、不进日志 |
| 不回显原则 | 凭据写入只回字段名，不回值（对齐 PI Desktop 的 `update_cookie` 做法） |
| 不公网发布 | 问卷类能力保持本机 |

**档案脚本模式**（沿用 `clinical-learning-subscription` 的成熟做法）：

- `USER.md` 由脚本生成、**只读**，禁止手编
- 登记/清除/进度变更**必须走脚本**；脚本失败则停止并报告，不手改状态
- 手改会造成档案与实际状态不一致，且会被下次渲染覆盖

---

## 七、新增文件树总览

```
xyb-octop/
├── XYB-REQUIREMENTS.md              # 需求文档（本仓）
├── XYB-DESIGN.md                    # 设计文档（本仓）
├── XYB-UPSTREAM-DIFF.md             # 上游改动清单（NFR-2）
├── XYB-SKILL-LICENSE.md             # 技能许可台账（FR-2.7）
├── XYB-MDT.md                       # MDT 体系说明
├── XYB-TRIAL-CHANNELS.md            # 四通道说明
│
├── src/octop/infra/agents/
│   ├── builtin_skills/              # +5 通用护栏技能
│   │   ├── xyb-evidence-guard/
│   │   ├── xyb-anti-hallucination/
│   │   ├── xyb-term-glossary/
│   │   └── xyb-medical-disclaimer/
│   └── experts/library/             # +18 专家模板
│       ├── xyb-mdt-{surgery,oncology,imaging,pathology,intervention,
│       │            radiation,nutrition,psych,palliative}/
│       ├── xyb-{genomics,trial-matching}/
│       ├── xyb-acute-{gi-bleeding,obstruction,biliary,infection,hematology}/
│       ├── xyb-community-ops/
│       └── xyb-mdt-chair/           # kind=team
│
├── src/octop/infra/connectors/xyb_defaults.py    # +MCP 播种
├── src/octop/cli/commands/xyb.py                 # +octop xyb 子命令
│
├── scripts/
│   ├── xyb-bootstrap.sh             # 一键引导（幂等）
│   ├── xyb-brand-assets.py          # logo 派生
│   ├── xyb-check-branding.sh        # 品牌残留核查
│   ├── xyb-check-mcp.sh             # 5 个 MCP 握手验证
│   ├── xyb-check-channels.sh        # 四通道冒烟
│   └── xyb-check-experts.py         # 专家包校验（结构 + 护栏完整性）
│
└── dashboard/public/brand/          # logo 源图 + 派生资源
```

---

## 八、开发分解

六个阶段，每阶段**独立可验收**，且顺序保证"先能跑、再好看、再好用"。

| 阶段 | 内容 | 交付物 | 验收 |
|---|---|---|---|
| **P0 · 地基** | 建立改动追踪与校验脚本骨架 | `XYB-UPSTREAM-DIFF.md`、5 个 `xyb-check-*.sh/py` | 脚本可运行，基线 diff 为空 |
| **P1 · 临床四通道** | 5 个 MCP 播种 + 四通道冒烟 | `xyb_defaults.py`、`octop xyb init-mcp`、`xyb-bootstrap.sh` | 5 次握手成功；四通道各跑一次真实检索 |
| **P2 · MDT 专家** | 17 个专家模板 + 5 个护栏技能 | 专家包文件树 | `xyb-check-experts.py` 通过；3 个专家可 1:1 对话；越界提问全部拒绝 |
| **P3 · 品牌 UI** | 改名 + logo + 中文 + 默认配置 | logo 资源、i18n 补词、脚手架 | 品牌残留 0 条；UI 截图对照通过 |
| **P4 · 技能入库** | 分批落地约 22 个技能 | 技能文件 + 许可台账 | 每批抽查可加载可执行；台账完整 |
| **P5 · 主持团队与联调** | `xyb-mdt-chair` 编排 + 端到端 | 团队模板、编排规则 | 一次含 3 视角的会诊，产出含「分歧点」段 |

**P1 先做的理由**：四通道是**能力地基**——MDT 专家（P2）与试验专员都要用它；先打通，后面的专家才有真东西可调。

**可并行**：P3（UI）与 P2（专家）无依赖，可并行。P4 依赖 P2 的落点专家确定。

---

## 九、测试与验证策略

| 层 | 方式 | 脚本 |
|---|---|---|
| MCP 连通 | `initialize` + `tools/list` 真实 JSON-RPC 握手，核对工具数与 `serverInfo.version` | `xyb-check-mcp.sh` |
| 四通道 | 各跑一次真实检索，留原始输出 | `xyb-check-channels.sh` |
| 专家包 | 结构校验（manifest 必需字段、prompt_files 存在、id 合法）+ 护栏完整性（每个专家必含禁止条款） | `xyb-check-experts.py` |
| 护栏 | 对每个专家做 3 类越界提问（要处方 / 要排名 / 要生存期），断言全部正确拒绝 | `xyb-check-guardrails.py` |
| 品牌 | 全仓残留扫描（白名单外 0 条） | `xyb-check-branding.sh` |
| UI | 关键页面截图对照（改前/改后） | 人工 + 截图 |
| 上游差异 | `git diff` 基线对比，产出清单 | `xyb-upstream-diff.sh` |

**回归底线**：上游自带测试（`tests/`，`conftest.py` + `pytest`）必须保持通过。改动 UI 后跑 `dashboard` 的 `vitest`。

---

## 十、待确认事项

| # | 事项 | 我方建议 |
|---|---|---|
| 1 | 17 个专家模板是否偏多 | 建议保留（模板不占实例）；若要收敛，C 组 5 个急症可合为 1 个 |
| 2 | `graphify-xiaoyibao`（AGPL-3.0）是否入库 | 建议入库 + 单独标注传染性 + 落到发布流程（同 PI Desktop 决定） |
| 3 | 12 个无 LICENSE 仓库是否补齐 | **建议补 Apache-2.0**（对外分发前必须） |
| 4 | 成果推回哪个仓库 | 建议推回 `opencare-skillhub/xyb-Octop`（保持同源） |
| 5 | 部署形态 | 影响 `.env` 与 DB 建议（单机 SQLite / 团队 PostgreSQL） |
| 6 | CTV 索引是否重建 | 需动 `~/.ctv-mcp/`，建议先备份再重建 |
| 7 | 是否引入九段病情采集表作标准输入 | 建议引入（MDT 需要稳定输入，否则齐料步无法判"缺什么"） |
| 8 | 专家头像资源 | 17 个专家是否各配一张 |
| 9 | 包名是否改名 | **建议不改**（改 `octop` 包名会波及 1122 个 `.py` 与全部用户数据路径，收益仅"好看"） |

---

## 十一、P4 待办清单（技能入库未完成部分）

设计文档 §3.3 列出约 22 个技能。已完成 **13 个外部技能导入** + 4 个自研角色技能 + 5 个内置护栏技能 = **22 个**，**已达设计目标**。下表只剩 1 个候选，其阻塞不在代码侧。
入库时请照 `scripts/xyb_import_skills.py` 的导入表补一行（带 `source_repo` / `source_license` /
`adapted` / `readiness`），不要手工复制文件。

| 优先级 | 技能 | 源仓库 | 许可（实测） | 落点专家 | 为什么还没入库 |
|---|---|---|---|---|---|
| 中 | `tumor-marker-trend` | `graphify-xiaoyibao` | **AGPL-3.0** | `xyb-mdt-oncology` | 强 copyleft，入库前需先定对外分发口径（见 `XYB-SKILL-LICENSE.md` §四） |

**验收口径**：每入库一个，`python3 scripts/xyb_import_skills.py --check` 必须仍通过，
且 `XYB-SKILL-LICENSE.md` 的「已入库技能」表新增一行。
