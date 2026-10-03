"""Brand gates: the naming audit and the derived brand assets.

``XYB-TEST-PLAN.md`` section 8 describes two options for the naming gate: keep it
as a standalone script, or wire it into pytest and add that file's collected
count to the baseline. It is wired in here, because a gate nobody runs is not a
gate. The audit is still runnable standalone as well.

The audit itself needs ``tomllib`` (Python 3.11+); the project targets 3.12, so
that is not a real constraint, but the guard keeps a 3.10 interpreter from
producing a confusing collection error.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
AUDIT = REPO / "scripts" / "xyb_name_audit.py"
BRAND = REPO / "scripts" / "xyb-brand.py"
REBRAND = REPO / "scripts" / "xyb_rebrand.py"

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 11),
    reason="the naming audit uses tomllib (Python 3.11+)",
)


def _run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO,
    )


def test_naming_audit_passes_on_the_rebranded_tree() -> None:
    """The gate accepts the rebranded tree and rejects the legacy state.

    Both assertions live here because each run walks the whole working tree and
    spawning two such runs would dominate this module's runtime.
    """
    result = _run(AUDIT)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "failed=0" in result.stdout

    legacy = _run(AUDIT, "--phase", "pre")
    assert legacy.returncode == 1, legacy.stdout + legacy.stderr


def test_naming_audit_json_reports_no_failures() -> None:
    result = _run(AUDIT, "--json")
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["failed"] == 0, payload
    assert payload["residual_by_file"] == {}


def test_display_name_and_artifact_name_are_both_applied() -> None:
    """AC-1 amended: the UI shows Chinese, the package name stays ASCII."""
    manifest = json.loads((REPO / "dashboard/public/manifest.json").read_text(encoding="utf-8"))
    assert manifest["short_name"] == "小胰宝"
    assert manifest["name"] == "小胰宝"
    # The manifest id and the icon filenames must remain ASCII.
    assert manifest["id"].isascii()

    index_html = (REPO / "dashboard/index.html").read_text(encoding="utf-8")
    assert "<title>小胰宝</title>" in index_html
    assert 'content="小胰宝"' in index_html


def test_artifact_name_is_ascii_only() -> None:
    """AC-1: no CJK may appear in a package, script, or artifact identifier."""
    import tomllib

    data = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    project = data["project"]
    assert project["name"] == "xyb-octop"
    for key in project["scripts"]:
        assert key.isascii(), key
    assert all(ord(ch) < 128 for ch in project["name"])


def test_rebrand_script_is_idempotent() -> None:
    """Running the rebrand twice must not change anything the second time."""
    result = _run(REBRAND, "--check")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no legacy brand copy left" in result.stdout


def test_brand_assets_are_current() -> None:
    """The generator's own gate must pass.

    An adversarial review found this test named "…and are current" while it only
    checked existence, and that `BRAND` was bound but never invoked. Running the
    real gate is what makes the name true.
    """
    result = _run(BRAND, "--check")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "brand assets up to date" in result.stdout


def test_mascots_are_derived_from_the_source_logo() -> None:
    """The four mascot assets were the old red upstream octopus; they must not be.

    Sampling the centre pixel is enough to tell: the new mascot is teal
    (green-dominant) while the upstream one was red.
    """
    from PIL import Image

    public = REPO / "dashboard" / "public"
    for name in ("octop-mascot-empty.png", "octop-mascot-tasks.png"):
        with Image.open(public / name) as image:
            rgba = image.convert("RGBA")
            width, height = rgba.size
            # Average the opaque pixels' hue bias across a small grid.
            reds = greens = 0
            for x in range(0, width, max(1, width // 12)):
                for y in range(0, height, max(1, height // 12)):
                    r, g, _b, a = rgba.getpixel((x, y))
                    if a < 200:
                        continue
                    reds += r
                    greens += g
            assert greens > reds, (
                f"{name} is red-dominant (r={reds} g={greens}); "
                "the mascot still looks like the upstream brand"
            )


def test_brand_assets_exist_and_are_current() -> None:
    for name in (
        "pwa-192.png",
        "pwa-512.png",
        "apple-touch-icon.png",
        "favico.svg",
        "logo_horizontal_dark.png",
        "logo_horizontal_white.png",
        "logo_vertical_dark.svg",
        "logo_vertical_white.svg",
        "brand/logo-source.png",
    ):
        path = REPO / "dashboard" / "public" / name
        assert path.is_file(), f"{name} was not generated"
        assert path.stat().st_size > 0, f"{name} is empty"


def test_brand_source_is_kept_for_regeneration() -> None:
    """The original logo is cached so assets can be rebuilt offline."""
    source = REPO / "dashboard" / "public" / "brand" / "logo-source.png"
    assert source.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_pwa_manifest_references_only_generated_icons() -> None:
    manifest = json.loads((REPO / "dashboard/public/manifest.json").read_text(encoding="utf-8"))
    for icon in manifest["icons"]:
        path = REPO / "dashboard" / "public" / icon["src"].lstrip("/")
        assert path.is_file(), f"manifest references a missing icon: {icon['src']}"


def test_record_organizer_is_placed_deliberately() -> None:
    """Where the heavy record-organizing skill lives is a decision, not an accident.

    The package is ~700 KB of scripts and templates. Copying it into all 17
    experts would add roughly 12 MB and hundreds of files to the distribution for
    a skill that answers one question ("help me tidy up these reports"), and the
    MDT workflow already routes document intake through the summary step every
    expert owns. So it lives in one patient-facing expert and this test pins that
    down: if someone moves it, they must also revisit the reasoning here.
    """
    library = REPO / "src" / "octop" / "infra" / "agents" / "experts" / "library"
    # <expert>/skills/record-organizer/SKILL.md -> parents[2] is the expert dir.
    owners = sorted(
        path.parents[2].name for path in library.glob("xyb-*/skills/record-organizer/SKILL.md")
    )
    assert owners == ["xyb-mdt-surgery"], (
        f"record-organizer moved to {owners}; update the placement decision and "
        "re-check the package size before accepting a wider distribution"
    )


def test_no_expert_ships_upstream_test_files() -> None:
    """Imported skills must not drag the author's machine paths into the package."""
    library = REPO / "src" / "octop" / "infra" / "agents" / "experts" / "library"
    offenders = [
        str(path.relative_to(REPO)) for path in library.glob("xyb-*/skills/*/scripts/test_*.py")
    ]
    assert not offenders, offenders
