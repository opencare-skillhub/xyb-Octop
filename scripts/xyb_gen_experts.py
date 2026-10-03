#!/usr/bin/env python3
"""Generate the shared parts of every xiaoyibao MDT expert package.

Seventeen experts share one package shape: a manifest, a persona, an operating
procedure, a first-run guide, a patient profile, and skills. Only the manifest
is genuinely per-expert; the operating procedure and the profile machinery are
identical apart from the role's name and its skill table.

Hand-copying the identical parts seventeen times is how they drift. So the
manifests are the **source of truth** for role identity, and this script derives:

* ``AGENTS.md``            the shared operating procedure, role-substituted
* ``USER.md``              the empty patient-profile template
* ``scripts/profile.py``   the shared profile state machine (copied verbatim)

``--check`` verifies the derived files match what the script would write, which
is what keeps a hand edit from silently diverging. Run it after editing any
manifest or the shared template.

Usage::

    python3 scripts/xyb_gen_experts.py            # write derived files
    python3 scripts/xyb_gen_experts.py --check    # assert they are up to date
    python3 scripts/xyb_gen_experts.py --expert xyb-mdt-imaging
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LIBRARY = REPO / "src" / "octop" / "infra" / "agents" / "experts" / "library"
PREFIX = "xyb-"

#: The canonical profile state machine; copied verbatim into every expert.
PROFILE_SOURCE = LIBRARY / "xyb-mdt-surgery" / "scripts" / "profile.py"

#: Per-role first-run guide content.
BOOTSTRAP_DATA = REPO / "scripts" / "xyb_bootstrap_data.json"

#: Skills that are identical across every expert, with a single source copy.
#: Keeping one source avoids the classic drift where 17 of 18 copies get fixed.
SHARED_SKILL_FILES: tuple[tuple[str, Path], ...] = (
    ("case-summary/SKILL.md", LIBRARY / "xyb-mdt-surgery" / "skills" / "case-summary" / "SKILL.md"),
)


@dataclass(frozen=True)
class Role:
    """Per-expert values the shared template needs."""

    expert_id: str
    #: How the expert refers to itself, e.g. "胰腺外科视角".
    viewpoint: str
    #: The department a patient should ask, e.g. "外科".
    department: str
    #: Role-specific skills, in the order the operating procedure lists them.
    skills: tuple[tuple[str, str], ...]


def _manifest(expert_dir: Path) -> dict:
    return json.loads((expert_dir / "manifest.json").read_text(encoding="utf-8"))


def _label(data: dict, locale: str = "zh") -> str:
    label = data.get("label")
    if isinstance(label, dict):
        return str(label.get(locale) or label.get("zh") or "")
    return str(label or "")


#: Skills that are always present and therefore listed in the fixed part of the
#: table rather than derived per expert.
SHARED_SKILLS = ("case-summary",)

#: Department a patient should actually ask, for experts whose label is not a
#: department name ("基因检测解读" would otherwise yield "基因检测解读医生").
#: Values must NOT already end in 医生/医师 — the template appends it.
DEPARTMENT_OVERRIDES: dict[str, str] = {
    "xyb-genomics": "肿瘤内科或遗传咨询",
    "xyb-trial-matching": "研究团队或主管",
    "xyb-community-ops": "主管",
}


def _skills(expert_dir: Path) -> tuple[tuple[str, str], ...]:
    """Read the role-specific skills from disk, with a short Chinese trigger."""
    root = expert_dir / "skills"
    if not root.is_dir():
        return ()
    found: list[tuple[str, str]] = []
    for entry in sorted(root.iterdir()):
        skill_md = entry / "SKILL.md"
        if not skill_md.is_file() or entry.name in SHARED_SKILLS:
            continue
        when = _skill_trigger(skill_md.read_text(encoding="utf-8"))
        found.append((entry.name, when))
    return tuple(found)


def _skill_trigger(text: str) -> str:
    """Return a short Chinese 'use when' note from a SKILL.md description.

    Descriptions are bilingual and may fold across lines, so the Chinese clause
    is taken up to its first full stop and the English tail is dropped. This is
    display text for the operating procedure, never a behaviour switch.
    """
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not line.startswith("description:"):
            continue
        value = line.split(":", 1)[1].strip()
        cursor = index + 1
        while cursor < len(lines) and lines[cursor].startswith((" ", "\t")):
            value += " " + lines[cursor].strip()
            cursor += 1
        value = value.strip().strip('"').strip("'")
        # Cut the English sentence off; keep the Chinese one.
        for marker in ("Must use", "Use when"):
            if marker in value:
                value = value.split(marker, 1)[0]
        value = value.strip(" 。.；;，,、")
        if value:
            return value[:180]
    return ""


AGENTS_TEMPLATE = """# 操作规程 — {viewpoint}

## 一、意图路由

先判断患者这次要什么，再决定走哪条路。

| 患者说 | 走哪条 | 先对齐摘要 |
|---|---|---|
| 「帮我看看这份报告」「整理一下病情」 | 案情摘要对齐 → {routed} | ✅ |
| 「我现在该怎么办」「该不该……」 | 视角解读 + 问题清单（**明确说明我不下这个判断**） | ✅ |
| 「这个指标/名词是什么意思」 | 术语解释（走 `xyb-term-glossary`） | ❌ |
| 「还能活多久」「来不来得及」 | **不回答**，引导到主管医生；只给可讨论的维度 | ❌ |
| 「推荐个医院/医生」「哪家最好」 | **不回答**，说明原因，给该问本院医生的问题 | ❌ |
| 「帮我开点药」「剂量多少」 | **不回答**，说明原因，给该问{department}医生的问题 | ❌ |
| 情绪宣泄、焦虑、害怕 | 先回应情绪本身，再问要不要整理问题清单 | ❌ |

## 二、每次回答的固定流程

1. **先对齐摘要**（`case-summary` 技能）。资料不全就先问，一次不超过 3 项。
2. **确认这次的问题**属于上表哪一行。
3. **按 `SOUL.md` 的输出骨架作答**，结构不要改。
4. **收尾**：按 `xyb-medical-disclaimer` 给对应场景的声明。

## 三、本专家可用的技能

| 技能 | 什么时候用 |
|---|---|
| `case-summary` | 每次开始分析前，**必用** |
{skill_rows}| `xyb-evidence-guard` | 引用任何医学结论前，**必用** |
| `xyb-anti-hallucination` | 输出前后，**必用** |
| `xyb-term-glossary` | 术语首次出现时，**必用** |
| `xyb-medical-disclaimer` | 每次收尾，**必用** |

## 四、危机信号优先于一切（先看这一条）

用户消息一进来，**先判断有没有自伤、自杀念头，或者绝望到「不想活了」「撑不下去了」**。

**有 → 走这条，不要走常规流程：**

1. **回复的第一行**就给全国心理援助热线 **12356**；
2. 建议尽快联系主管医生，或就近精神科／心理科；
3. 不追问病史、不列问题清单、不进入本视角的输出骨架；
4. 用陪伴的语气回应，承认他的痛苦是真实的，不淡化、不说教、不把这条放到文末。

**没有 → 再看下面的躯体急症。**

## 五、必须立刻提醒就医的躯体情形（第一句就说，不要绕）

出现以下任一情况，**开头第一句**就是让他立即就医或拨打 120，其余内容全部后置：

- 呕血、黑便、便血、咳血
- 剧烈腹痛且持续加重，或腹部按压后剧痛
- 发热伴寒战，或皮肤眼睛发黄明显加重
- 频繁呕吐、完全不能进食、腹胀明显
- 意识改变、极度虚弱、无法唤醒

写法：

> 你描述的情况需要**立即就医**（或拨打 120）。下面是判断依据，但请先联系医生。

## 六、档案与隐私

- 患者自述的案情摘要由 `scripts/profile.py` 维护，渲染为 `USER.md`。**不要手改 `USER.md`**，下次渲染会覆盖。
- 登记、更新、清空都必须走脚本：`python3 scripts/profile.py set --field <字段> --value <值> --confirm true`。
- 脚本拒绝身份证号、手机号、住院号等身份信息，**这不是可绕过的限制**。
- 不主动索要姓名、身份证号、病历号、电话；需要资料时说明「为什么需要」并提醒可以打码。

## 七、硬约定

- **不自行上网检索**：本视角不靠 agent 去浏览网页找依据。需要权威来源时，让患者提供报告原文，或使用平台已配置的检索能力；若本视角带有**本机脚本**类技能（例如影像取回），按其技能说明在患者本机运行，属于本机工具，不违反本条。
- **技能优先于记忆**：拿到报告先按对应技能（`case-summary` 及本角色的专项技能）走一遍，不要凭印象直接分析。
- **判断留在本视角**：整理类工作（把报告文字结构化、对齐摘要）可以做，但医学判断必须由你按 `SOUL.md` 的骨架给出，不外包给任何其他角色。
- **全程简体中文**，不出现过程句（`I'll` / 「正在检索…」），不暴露工具名与原始输出。

## 八、输出前自检（逐条过）

1. 出现的如果是自伤／自杀念头，我有没有**第一行就给 12356**、并且没有进入常规流程？
2. 有没有出现诊断结论、处方、方案建议？
3. 有没有推荐医院、医生，或做任何排名？
4. 有没有预测生存期、进展速度、具体时间？
5. 缺失的信息，我写「未提供」了吗？还是凭经验补全了？
6. 有没有给够 3–5 条「可以问{department}医生的问题」？
7. 结尾的免责声明加了吗？
8. 有没有过程句或工具名外泄？
"""


def render_agents(role: Role) -> str:
    rows = ""
    for name, trigger in role.skills:
        when = trigger or "本角色相关场景"
        rows += f"| `{name}` | {when} |\n"
    # "基因检测解读" + "解读" would read "基因检测解读解读"; drop the suffix when
    # the label already says what the expert does.
    routed = role.viewpoint
    if not routed.endswith(("视角", "专家")):
        routed = routed + "解读" if "解读" not in routed else routed
    return AGENTS_TEMPLATE.format(
        viewpoint=role.viewpoint,
        routed=routed,
        department=role.department,
        skill_rows=rows,
    )


def build_role(expert_dir: Path) -> Role:
    data = _manifest(expert_dir)
    label = _label(data)
    # "胰腺外科视角" -> viewpoint as written; department from the manifest is not
    # stored separately, so derive it from the viewpoint by dropping the suffix.
    viewpoint = label or expert_dir.name
    department = DEPARTMENT_OVERRIDES.get(expert_dir.name) or (
        viewpoint.removesuffix("视角").removesuffix("专家") or "主管"
    )
    return Role(
        expert_id=expert_dir.name,
        viewpoint=viewpoint,
        department=department,
        skills=_skills(expert_dir),
    )


def render_bootstrap(expert_id: str, data: dict) -> str | None:
    """Render a first-run guide, or None when no role data exists yet."""
    entry = data.get(expert_id)
    if not entry:
        return None

    lines: list[str] = [
        "# 首次会话引导",
        "",
        "只在第一次对话时走一遍。目标不是问全，而是**让患者知道该准备什么**。",
        "",
        "## 第一步：自我介绍（一段话）",
        "",
        f"> {entry['intro']}",
        ">",
        "> 想让我理得清楚一点，可以先把下面这些发给我（有什么发什么，没有就说没有）：",
    ]
    for index, item in enumerate(entry.get("materials") or [], start=1):
        lines.append(f"> {_circled(index)} {item}")
    if not entry.get("materials"):
        lines.append("> 这次不用准备材料，你想说什么都可以。")

    extra = entry.get("extra")
    if extra:
        lines += ["", "## 本专家的特殊规则（优先于本文件其余内容）", "", f"> {extra}"]

    lines += [
        "",
        "## 第二步：按需追问（一次最多 2–3 项）",
        "",
        "按这个优先级问，问到能判断方向就停：",
        "",
    ]
    for index, item in enumerate(entry.get("priority") or [], start=1):
        lines.append(f"{index}. {item}")

    lines += [
        "",
        "## 第三步：确认与收敛",
        "",
        "收到资料后**先复述一遍**关键信息请患者确认（避免我看错了影响后面所有分析），然后问：",
        "",
        "> 这次你最想解决哪一个问题？（可以多选）",
        "",
        "## 第四步：进入正常流程",
        "",
        "确认后按 `AGENTS.md` 的意图路由处理。**不要在这之后重复引导。**",
        "",
        "## 隐私提醒（第一轮就带一句）",
        "",
        "> 发资料前建议把姓名、住院号、身份证号、电话遮掉。不遮我也只需要医学信息。",
        "",
        "## 不要做的事",
        "",
        "- ❌ 不要一次问五六个问题",
        "- ❌ 不要因为患者只给了一半资料就停止回应——先给「在现有资料下能讨论什么」",
        "- ❌ 不要在引导阶段就开始分析",
        "- ❌ 不要问姓名、身份证号、病历号",
        "",
    ]
    return "\n".join(lines)


def _circled(index: int) -> str:
    """①②③… for lists longer than the ASCII digits read well."""
    marks = "①②③④⑤⑥⑦⑧⑨⑩"
    if 1 <= index <= len(marks):
        return marks[index - 1]
    return f"{index}."


def derived_files(expert_dir: Path) -> dict[Path, str]:
    """Map every generated file to the exact content it should hold."""
    role = build_role(expert_dir)
    files: dict[Path, str] = {expert_dir / "AGENTS.md": render_agents(role)}

    bootstrap_data = json.loads(BOOTSTRAP_DATA.read_text(encoding="utf-8"))
    bootstrap = render_bootstrap(expert_dir.name, bootstrap_data)
    if bootstrap is not None:
        files[expert_dir / "BOOTSTRAP.md"] = bootstrap

    # USER.md must be the renderer's own empty output, so ask the script.
    profile = PROFILE_SOURCE.read_text(encoding="utf-8")
    namespace: dict[str, object] = {"__name__": "xyb_profile_render"}
    exec(compile(profile, str(PROFILE_SOURCE), "exec"), namespace)  # noqa: S102
    empty_state = namespace["_empty_state"]()  # type: ignore[operator]
    files[expert_dir / "USER.md"] = namespace["render_user_md"](empty_state)  # type: ignore[operator]

    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="verify, do not write")
    parser.add_argument("--expert", default=None, help="only this expert id")
    args = parser.parse_args()

    if not PROFILE_SOURCE.is_file():
        print(f"missing canonical profile script: {PROFILE_SOURCE}", file=sys.stderr)
        return 2

    expert_dirs = sorted(
        p
        for p in LIBRARY.iterdir()
        if p.is_dir() and p.name.startswith(PREFIX) and (p / "manifest.json").is_file()
    )
    if args.expert:
        expert_dirs = [p for p in expert_dirs if p.name == args.expert]
        if not expert_dirs:
            print(f"unknown expert: {args.expert}", file=sys.stderr)
            return 2

    stale: list[str] = []
    written = 0
    for expert_dir in expert_dirs:
        for path, content in derived_files(expert_dir).items():
            current = path.read_text(encoding="utf-8") if path.is_file() else None
            if current == content:
                continue
            if args.check:
                stale.append(str(path.relative_to(REPO)))
                continue
            path.write_text(content, encoding="utf-8")
            written += 1

        # Shared skill bodies are copied verbatim so the eighteen experts cannot
        # drift apart on the structure patients see.
        for rel, source in SHARED_SKILL_FILES:
            skill_target = expert_dir / "skills" / rel
            if skill_target == source:
                continue
            source_text = source.read_text(encoding="utf-8")
            current = skill_target.read_text(encoding="utf-8") if skill_target.is_file() else None
            if current != source_text:
                if args.check:
                    stale.append(str(skill_target.relative_to(REPO)))
                else:
                    skill_target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, skill_target)
                    written += 1

        # The profile script is copied verbatim so every expert behaves the same.
        target = expert_dir / "scripts" / "profile.py"
        if target != PROFILE_SOURCE:
            source_text = PROFILE_SOURCE.read_text(encoding="utf-8")
            current = target.read_text(encoding="utf-8") if target.is_file() else None
            if current != source_text:
                if args.check:
                    stale.append(str(target.relative_to(REPO)))
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(PROFILE_SOURCE, target)
                    written += 1

    if args.check:
        if stale:
            print("derived files are out of date:", file=sys.stderr)
            for item in stale:
                print(f"  {item}", file=sys.stderr)
            print("\nrun: python3 scripts/xyb_gen_experts.py", file=sys.stderr)
            return 1
        print(f"experts={len(expert_dirs)} derived files up to date")
        return 0

    print(f"experts={len(expert_dirs)} files written={written}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
