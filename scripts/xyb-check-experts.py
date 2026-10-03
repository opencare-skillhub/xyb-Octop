#!/usr/bin/env python3
"""XYB expert-package validator (stdlib only).

Two things are checked for every ``xyb-`` expert template under
``src/octop/infra/agents/experts/library/``:

1. **Structure** — the package will actually load. ``manifest.json`` must parse
   as an object, ``id`` must match the directory name, both locales must have a
   label and description, and everything referenced must exist on disk.
2. **Guardrails** — the medical red lines are present. An expert whose SOUL.md
   is missing the prohibition clauses is a safety defect, not a style nit, so
   this is a hard failure (FR-4.2.3).

Background facts this validator relies on (verified in the upstream source):

* ``catalog.py`` discovers a library entry iff the directory holds a
  ``manifest.json`` that parses as a JSON object; every field is optional.
  Requiring them here is therefore *our* contract, not upstream's.
* ``discover_seed_paths`` uploads every file in the package verbatim, so a stray
  file becomes workspace content. Nothing in this validator needs to care, but
  it is why the package must stay tidy.
* ``kind`` is **not** a manifest field. A team host is created through
  ``POST /api/teams`` and seeded from the fixed
  ``infra/agents/teams/template``. Adding ``"kind": "team"`` here would be
  silently ignored, so it is reported as an error.

Usage::

    python3 scripts/xyb-check-experts.py                # validate all xyb-* experts
    python3 scripts/xyb-check-experts.py --all          # include upstream experts
    python3 scripts/xyb-check-experts.py xyb-mdt-imaging
    python3 scripts/xyb-check-experts.py --json

Exit code 0 when every selected expert passes, 1 otherwise, 2 on bad usage.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LIBRARY = REPO / "src" / "octop" / "infra" / "agents" / "experts" / "library"
PREFIX = "xyb-"

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

#: Clause patterns every medical expert's SOUL.md must satisfy.
#: Each entry is (check id, human title, regex).
GUARDRAILS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "G1",
        "refuses diagnosis / prescribing",
        re.compile(r"(不出诊断|不给处方|不做诊断|不提供诊断|不下诊断)"),
    ),
    (
        "G2",
        "refuses hospital / doctor ranking or recommendation",
        re.compile(r"(不推荐医院|不做.{0,6}排名|不排名|不做医院|不推荐医生)"),
    ),
    (
        "G3",
        "refuses survival prediction",
        re.compile(r"(不预测生存|不判断生存|不做生存|不推测生存|生存期.{0,4}不)"),
    ),
    (
        "G4",
        "forbids the 'expert says' framing (viewpoint, not consultation)",
        re.compile(r"(视角|角度)"),
    ),
    (
        "G5",
        "requires the question list as the deliverable",
        re.compile(r"(可以问|向.{0,8}医生提问|问题清单|该问)"),
    ),
    (
        "G6",
        "requires pointing out missing information rather than guessing",
        re.compile(r"(摘要未提供|未提供就|缺失就说|资料不足|信息缺失|不要补全|不得推断)"),
    ),
)


@dataclass
class Finding:
    expert: str
    check: str
    ok: bool
    detail: str = ""


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)

    def add(self, expert: str, check: str, ok: bool, detail: str = "") -> None:
        self.findings.append(Finding(expert, check, ok, detail))

    @property
    def failed(self) -> list[Finding]:
        return [f for f in self.findings if not f.ok]


def _coerce_label(value: object) -> tuple[str, str] | None:
    """Mirror ``catalog._coerce_label``: accept a map or a bare string."""
    if isinstance(value, str):
        return (value, value) if value.strip() else None
    if isinstance(value, dict):
        zh = str(value.get("zh", "") or "").strip()
        en = str(value.get("en", "") or "").strip()
        if not zh and not en:
            return None
        return (zh or en, en or zh)
    return None


def _role_extra_bans(expert_id: str) -> tuple[tuple[str, str], ...] | None:
    """Return the role's own prohibited actions, or None when it has none.

    The role table is imported rather than re-parsed: the ban strings are written
    as implicitly concatenated literals, which an ``ast.Constant`` walk reads as
    fragments and then fails to match against the rendered SOUL.md.
    """
    scripts_dir = str(REPO / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    try:
        from xyb_soul_data import SOUL_DATA  # noqa: PLC0415
    except ImportError:
        return None
    role = SOUL_DATA.get(expert_id)
    if role is None:
        return None
    return tuple(role.extra_bans)


def validate_expert(expert_dir: Path, report: Report) -> None:
    name = expert_dir.name
    manifest_path = expert_dir / "manifest.json"

    if not manifest_path.is_file():
        report.add(name, "S1", False, "manifest.json is missing")
        return

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        report.add(name, "S1", False, f"manifest.json is not valid JSON: {exc}")
        return

    if not isinstance(data, dict):
        report.add(name, "S1", False, "manifest.json must be a JSON object")
        return
    report.add(name, "S1", True)

    # ---------------------------------------------------------------- identity
    manifest_id = str(data.get("id") or name)
    report.add(
        name,
        "S2",
        manifest_id == name,
        f"manifest id {manifest_id!r} != directory name {name!r}",
    )
    report.add(
        name,
        "S3",
        bool(ID_RE.match(name)),
        f"directory name {name!r} is not a lowercase slug",
    )

    if "kind" in data:
        report.add(
            name,
            "S4",
            False,
            "'kind' is not an expert-manifest field (teams are created via POST /api/teams)",
        )
    else:
        report.add(name, "S4", True)

    # ------------------------------------------------------------- localisation
    label = _coerce_label(data.get("label"))
    report.add(
        name,
        "S5",
        label is not None and bool(label[0]) and bool(label[1]),
        f"label must supply zh and en, got {data.get('label')!r}",
    )
    description = _coerce_label(data.get("description"))
    report.add(
        name,
        "S6",
        description is not None and bool(description[0]) and bool(description[1]),
        f"description must supply zh and en, got {data.get('description')!r}",
    )
    welcome = _coerce_label(data.get("welcome_message"))
    report.add(
        name,
        "S7",
        welcome is not None and bool(welcome[0]) and bool(welcome[1]),
        f"welcome_message must supply zh and en, got {data.get('welcome_message')!r}",
    )

    icon_name = data.get("icon_name")
    report.add(
        name,
        "S8",
        isinstance(icon_name, str) and bool(icon_name.strip()),
        f"icon_name is required for the patient UI, got {icon_name!r}",
    )
    color = data.get("color")
    report.add(
        name,
        "S9",
        isinstance(color, str) and bool(re.fullmatch(r"#[0-9A-Fa-f]{6}", color or "")),
        f"color must be a #RRGGBB hex string, got {color!r}",
    )

    # ------------------------------------------------------------------- files
    prompt_files = data.get("prompt_files")
    if not isinstance(prompt_files, list) or not prompt_files:
        report.add(
            name, "S10", False, f"prompt_files must be a non-empty list, got {prompt_files!r}"
        )
    else:
        missing = [str(rel) for rel in prompt_files if not (expert_dir / str(rel)).is_file()]
        report.add(
            name,
            "S10",
            not missing,
            f"prompt_files not found on disk: {', '.join(missing)}",
        )

    # ------------------------------------------------------------- quick_prompts
    quick = data.get("quick_prompts")
    if quick is None:
        report.add(name, "S11", True, "no quick_prompts (optional)")
    elif not isinstance(quick, list):
        report.add(name, "S11", False, f"quick_prompts must be a list, got {type(quick).__name__}")
    else:
        problems: list[str] = []
        for index, item in enumerate(quick):
            if not isinstance(item, dict):
                problems.append(f"[{index}] is not an object")
                continue
            for key in ("title", "description", "prompt"):
                if _coerce_label(item.get(key)) is None:
                    problems.append(f"[{index}].{key} is missing or empty")
        report.add(
            name,
            "S11",
            not problems,
            "; ".join(problems[:4]),
        )

    # ------------------------------------------------------------ task_examples
    examples = data.get("task_examples")
    if examples is None:
        report.add(name, "S12", False, "task_examples is required for the empty state")
    else:
        problem = ""
        if isinstance(examples, list):
            if not examples:
                problem = "task_examples list is empty"
        elif isinstance(examples, dict):
            zh = examples.get("zh")
            en = examples.get("en")
            if not isinstance(zh, list) or not zh:
                problem = "task_examples.zh must be a non-empty list"
            elif not isinstance(en, list) or not en:
                problem = "task_examples.en must be a non-empty list"
        else:
            problem = (
                f"task_examples must be a list or {{zh,en}} map, got {type(examples).__name__}"
            )
        report.add(name, "S12", not problem, problem)

    # -------------------------------------------------------------- guardrails
    if name.startswith(PREFIX):
        soul = expert_dir / "SOUL.md"
        # G1-G6 above are supplied by the shared template, so on their own they
        # pass for ANY generated SOUL.md. G8 is the check that can actually fail:
        # each role must carry its own extra prohibitions.
        expected_bans = _role_extra_bans(name)
        if expected_bans is None:
            report.add(name, "G8", False, "no role data found for this expert")
        else:
            text_for_bans = soul.read_text(encoding="utf-8", errors="replace") if soul.is_file() else ""
            missing_bans = [bad for bad, _good in expected_bans if bad not in text_for_bans]
            report.add(
                name,
                "G8",
                not missing_bans,
                "; ".join(f"SOUL.md lacks role ban: {bad}" for bad in missing_bans[:4]),
            )
        if not soul.is_file():
            report.add(name, "G0", False, "SOUL.md is missing (guardrails cannot be checked)")
        else:
            text = soul.read_text(encoding="utf-8", errors="replace")
            for cid, title, pattern in GUARDRAILS:
                found = bool(pattern.search(text))
                report.add(name, cid, found, "" if found else f"SOUL.md lacks: {title}")
        report.add(
            name,
            "G7",
            (expert_dir / "AGENTS.md").is_file(),
            "AGENTS.md is missing (operating procedure + intent routing)",
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("names", nargs="*", help="expert directory names (default: all xyb-*)")
    parser.add_argument("--all", action="store_true", help="validate upstream experts too")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args()

    if not LIBRARY.is_dir():
        print(f"expert library not found: {LIBRARY}", file=sys.stderr)
        return 2

    if args.names:
        selected = [LIBRARY / n for n in args.names]
        missing = [p.name for p in selected if not p.is_dir()]
        if missing:
            print(f"unknown expert(s): {', '.join(missing)}", file=sys.stderr)
            return 2
    else:
        selected = sorted(
            p for p in LIBRARY.iterdir() if p.is_dir() and (args.all or p.name.startswith(PREFIX))
        )

    if not selected:
        print("no experts selected", file=sys.stderr)
        return 1

    report = Report()
    for expert_dir in selected:
        validate_expert(expert_dir, report)

    if args.json:
        by_expert: dict[str, list[dict]] = {}
        for finding in report.findings:
            by_expert.setdefault(finding.expert, []).append(
                {"check": finding.check, "ok": finding.ok, "detail": finding.detail}
            )
        print(
            json.dumps(
                {
                    "ok": not report.failed,
                    "experts_checked": len(selected),
                    "checks": len(report.findings),
                    "failed": len(report.failed),
                    "by_expert": by_expert,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        current = ""
        for finding in report.findings:
            if finding.expert != current:
                current = finding.expert
                print(f"\n{current}")
            if finding.ok and not finding.detail:
                continue
            mark = "PASS" if finding.ok else "FAIL"
            line = f"  [{mark}] {finding.check:<4}"
            if finding.detail and not finding.ok:
                line += f" {finding.detail}"
            print(line)
        print()
        print(f"experts={len(selected)} checks={len(report.findings)} failed={len(report.failed)}")

    return 0 if not report.failed else 1


if __name__ == "__main__":
    sys.exit(main())
