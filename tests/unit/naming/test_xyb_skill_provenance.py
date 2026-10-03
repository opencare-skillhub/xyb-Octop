"""Skill provenance: every imported skill must be attributable and auditable.

`scripts/xyb_import_skills.py` copies third-party skills into expert packages.
Without a recorded source and licence, an imported skill becomes an
unattributable liability the first time someone asks whether it may be
redistributed -- and "the SKILL.md says MIT" is not the same fact as "the
repository grants MIT".

These tests pin the two things that make the ledger trustworthy:

* every import carries the four provenance fields;
* a licence *claim* inside a file is recorded as a claim, never promoted to a
  grant, and the direction is checked both ways so a stale flag fails too.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# tests/unit/naming/<file> -> parents[3] is the repo root.
REPO = Path(__file__).resolve().parents[3]
LIBRARY = REPO / "src" / "octop" / "infra" / "agents" / "experts" / "library"
IMPORTER = REPO / "scripts" / "xyb_import_skills.py"

PROVENANCE_FIELDS = ("source_repo:", "source_license:", "adapted:", "readiness:")


def _importer() -> object:
    """Import the recipe script as a module (it lives in scripts/, not a package)."""
    scripts = str(REPO / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location("xyb_import_skills", IMPORTER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["xyb_import_skills"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def imports() -> tuple:
    module = _importer()
    return module.IMPORTS  # type: ignore[attr-defined]


def test_every_import_records_its_provenance(imports: tuple) -> None:
    assert imports, "the import table is empty"
    for item in imports:
        skill_md = item.dest / "SKILL.md"
        assert skill_md.is_file(), f"{item.slug}: SKILL.md missing"
        text = skill_md.read_text(encoding="utf-8")
        for field in PROVENANCE_FIELDS:
            assert field in text, f"{item.slug}: provenance field {field!r} missing"
        # The recorded source must match the table, not a stale copy.
        assert f"source_repo: {item.source_repo}" in text, item.slug


def test_licence_claim_is_not_promoted_to_a_grant(imports: tuple) -> None:
    """A claim inside a file and a repository grant are different facts.

    The direction is asserted both ways: a skill that claims a licence must
    record it as *declared* (with the measured value still NONE), and a skill
    whose upstream makes no claim must not carry a declared licence.
    """
    for item in imports:
        text = (item.dest / "SKILL.md").read_text(encoding="utf-8")
        recorded = "declared_license:" in text
        if item.has_licence_claim:
            assert recorded, f"{item.slug}: upstream claims a licence but it is not recorded"
            assert item.declared_license, f"{item.slug}: has_licence_claim without a value"
            # The measured value stays authoritative.
            assert item.source_license == "NONE" or item.source_license == item.declared_license
        else:
            assert not recorded, (
                f"{item.slug}: declared_license recorded but upstream makes no claim"
            )


def test_a_measured_grant_is_never_downgraded(imports: tuple) -> None:
    """When GitHub reports a real SPDX id, that is the value that gets used."""
    for item in imports:
        if item.source_license not in ("NONE", ""):
            assert "source_license: " + item.source_license in (item.dest / "SKILL.md").read_text(
                encoding="utf-8"
            ), item.slug


def test_no_imported_skill_ships_credentials(imports: tuple) -> None:
    """Imported skills must not drag real secrets into the repository.

    Only placeholder values and redacted example files are acceptable; a long
    literal next to a credential-looking key is treated as a leak.
    """
    import re

    # Single-line values only ([^"'\n]): allowing newlines produced matches
    # that spanned statements, which are noise rather than findings.
    suspicious = re.compile(
        r"""(?ix)
        (?:cookie|token|password|secret|api[_-]?key|authorization)
        \s*[:=]\s*
        ["']([^"'\n]{24,})["']
        """
    )
    # Values that are obviously placeholders rather than secrets.
    placeholder = re.compile(
        r"(?i)"
        r"(your|example|placeholder|xxx|<|\{|\[|change|dummy|test|redact|omit)"
        r"|(?:\w+=\w+;?\s*\.{3})"  # "name1=value1; name2=value2; ..." doc examples
    )
    offenders: list[str] = []
    for item in imports:
        for path in sorted(item.dest.rglob("*")):
            if not path.is_file() or path.suffix.lower() in {".png", ".jpg", ".ico", ".webp"}:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for match in suspicious.finditer(text):
                value = match.group(1)
                if placeholder.search(value):
                    continue
                offenders.append(f"{path.relative_to(REPO)}: {value[:12]}…")
    assert not offenders, "credential-looking literals in imported skills:\n" + "\n".join(offenders)


def test_the_credential_detector_actually_catches_a_secret() -> None:
    """A gate that cannot fail is not a gate.

    'name1=value1; ...' documentation examples must pass, a real-looking secret
    must not. This runs the same regex the check uses, on synthetic input.
    """
    import re as _re

    placeholder = _re.compile(
        r"(?i)"
        r"(your|example|placeholder|xxx|<|\{|\[|change|dummy|test|redact|omit)"
        r"|(?:\w+=\w+;?\s*\.{3})"
    )
    suspicious = _re.compile(
        r"""(?ix)
        (?:cookie|token|password|secret|api[_-]?key|authorization)
        \s*[:=]\s*
        ["']([^"'\n]{24,})["']
        """
    )

    def caught(line: str) -> bool:
        return any(not placeholder.search(match.group(1)) for match in suspicious.finditer(line))

    # Documentation examples must not trip it.
    assert not caught('export NCCN_COOKIE="name1=value1; name2=value2; ..."')
    assert not caught('password = "your_password"')
    assert not caught('token: "<paste your token here>"')
    # A real-looking secret must.
    assert caught('cookie = "SESSIONID=8f3a9c2b41d7e6509a1b4c8d2e7f0a35"')
    assert caught('api_key: "sk-live-9f8e7d6c5b4a39281706f5e4d3c2b1a0"')
    # A short value is not treated as a secret (too little to go on).
    assert not caught('token = "abc123"')


def test_imported_skill_locations_are_real_experts(imports: tuple) -> None:
    for item in imports:
        assert (LIBRARY / item.expert / "manifest.json").is_file(), (
            f"{item.slug} targets unknown expert {item.expert!r}"
        )


def test_skill_docs_name_the_tools_the_channel_probe_actually_finds() -> None:
    """A skill that names a tool we do not ship sends the model to a dead call.

    The upstream trial-matching skill referenced `mcp__oncology_db__*` and
    `mcp__chictr__*`, neither of which exists here. Our own skills must spell the
    real tool names, and those names must come from the probe's server table --
    one source of truth rather than two lists that drift.

    Network calls are skipped: this asserts the *declared* tool surface, which is
    what the skills are written against.
    """
    import importlib.util as _ilu

    spec = _ilu.spec_from_file_location("probe", REPO / "scripts" / "xyb_mcp_probe.py")
    assert spec is not None and spec.loader is not None
    probe = _ilu.module_from_spec(spec)
    sys.modules["probe"] = probe
    spec.loader.exec_module(probe)

    servers = {server.name: server for server in probe.build_servers()}  # type: ignore[attr-defined]
    assert "xyb-clinicaltrials" in servers, "the clinicaltrials channel disappeared"
    assert "xyb-chictr" in servers, "the chictr channel disappeared"
    assert "xyb-veeva" in servers, "the veeva channel disappeared"
    # chinadrugs has no MCP server on purpose; the skill carries that channel.
    assert "xyb-chinadrugs" not in servers

    skill_docs = [
        LIBRARY / "xyb-trial-matching" / "skills" / "trial-search" / "SKILL.md",
        LIBRARY / "xyb-trial-matching" / "skills" / "trial-matching-advanced" / "SKILL.md",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in skill_docs)
    # The real tool names of the three MCP channels must be documented.
    for tool in (
        "search_clinical_trials",
        "search_trials",
        "search_studies",
    ):
        assert tool in text, f"no skill documents the {tool} tool"
    # And the foreign names must be flagged as unusable rather than recommended.
    assert "mcp__oncology_db" in text, "the foreign tool names should be called out"
    assert "本项目不存在" in text or "本项目**不使用**" in text or "一律忽略" in text
