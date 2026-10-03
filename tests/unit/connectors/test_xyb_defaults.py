"""XYB default MCP seeding — plan purity, add-only merge, and preconditions."""

from __future__ import annotations

from pathlib import Path

import pytest

from octop.infra.connectors.custom_mcp import validate_servers_map
from octop.infra.connectors.xyb_defaults import (
    CHANNELS,
    build_seed_plan,
    build_server_specs,
    channel_of,
    merged_servers,
)


def _built_veeva(tmp_path: Path) -> Path:
    """Create a fake built ctv-mcp-server checkout and point the env at it."""
    entry = tmp_path / "ctv-mcp-server" / "dist" / "index.js"
    entry.parent.mkdir(parents=True)
    entry.write_text("// fake entrypoint\n", encoding="utf-8")
    return entry


#: Channels served by an MCP endpoint. chinadrugs is deliberately absent: it is a
#: session-cookie CLI skill on the trial-matching expert, not an MCP server, and
#: seeding a server for it produced a permanent false FAIL in the probe.
MCP_CHANNELS: tuple[str, ...] = ("clinicaltrials", "chictr", "veeva")


def test_every_mcp_channel_has_a_server() -> None:
    carried = {spec.channel for spec in build_server_specs()}
    for channel in MCP_CHANNELS:
        assert channel in carried, f"channel {channel!r} has no server spec"
    # All four channels are still part of the product; three are MCP-backed.
    assert set(CHANNELS) >= set(MCP_CHANNELS)
    assert "chinadrugs" in CHANNELS


def test_chinadrugs_is_not_seeded_as_an_mcp_server() -> None:
    """It has no MCP server upstream; only the skill carries that channel."""
    names = {spec.name for spec in build_server_specs()}
    assert "xyb-chinadrugs" not in names


def test_metaso_pins_its_binary_because_the_package_ships_two() -> None:
    """``npx -y <pkg>`` cannot choose a bin when a package ships several.

    metaso-search-mcp@1.1.2 ships two (``metaso-mcp``, ``metaso-mcp-config``) and
    **neither** is named after the package, so the bare form exits with
    "could not determine executable to run" — which the probe surfaces only as
    the opaque "server closed stdout before replying". Pinning ``-p`` + binary
    is what makes it start.
    """
    specs = {spec.name: spec.spec for spec in build_server_specs()}
    args = specs["xyb-metaso"]["args"]

    assert args[:3] == ["-y", "-p", "metaso-search-mcp@1.1.2"]
    assert args[3] == "metaso-mcp"


def test_server_names_are_valid_and_unique() -> None:
    specs = build_server_specs()
    names = [spec.name for spec in specs]
    assert len(names) == len(set(names)), "duplicate server names"
    # The same validator the connector service applies on save.
    validate_servers_map({spec.name: {"transport": "stdio", "command": "true"} for spec in specs})


def test_plan_adds_every_ready_server(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    entry = _built_veeva(tmp_path)
    monkeypatch.setenv("XYB_VEEVA_DIR", str(entry.parents[1]))
    monkeypatch.setenv("METASO_API_KEY", "test-key")

    plan = build_seed_plan({})

    assert not plan.skipped, [s.reason for s in plan.skipped]
    expected = {spec.name for spec in build_server_specs()}
    assert {step.name for step in plan.added} == expected


def test_plan_is_add_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """An existing server is never overwritten, whatever its contents."""
    entry = _built_veeva(tmp_path)
    monkeypatch.setenv("XYB_VEEVA_DIR", str(entry.parents[1]))
    monkeypatch.setenv("METASO_API_KEY", "test-key")
    operator_spec = {"transport": "stdio", "command": "my-own-command", "enabled": False}

    plan = build_seed_plan({"xyb-chictr": operator_spec})

    kept = {step.name for step in plan.kept}
    assert "xyb-chictr" in kept
    assert "xyb-chictr" not in plan.to_add
    merged = merged_servers({"xyb-chictr": operator_spec}, plan)
    assert merged["xyb-chictr"] == operator_spec, "operator config was overwritten"


def test_missing_env_var_skips_not_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    entry = _built_veeva(tmp_path)
    monkeypatch.setenv("XYB_VEEVA_DIR", str(entry.parents[1]))
    monkeypatch.delenv("METASO_API_KEY", raising=False)

    plan = build_seed_plan({})

    skipped = {step.name: step for step in plan.skipped}
    assert "xyb-metaso" in skipped
    assert "METASO_API_KEY" in skipped["xyb-metaso"].reason
    assert "xyb-metaso" not in plan.to_add


def test_unbuilt_local_server_is_reported_not_written(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A missing local entrypoint must not become a command that cannot start."""
    monkeypatch.setenv("XYB_VEEVA_DIR", str(tmp_path / "does-not-exist"))

    plan = build_seed_plan({})

    unbuilt = {step.name: step.action for step in plan.skipped}
    assert unbuilt.get("xyb-veeva") == "unbuilt"
    assert "xyb-veeva" not in plan.to_add


def test_plan_never_installs_dependencies() -> None:
    """The module writes configuration only; no package manager may be invoked.

    Checked against the parsed AST rather than the raw text so that prose in the
    module docstring explaining this rule does not trip the test.
    """
    import ast

    source_path = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "octop"
        / "infra"
        / "connectors"
        / "xyb_defaults.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    assert "subprocess" not in imported, "seeding must not shell out"
    assert "shutil" not in imported, "seeding must not copy or install anything"

    # Reading os.environ is fine; invoking a shell through os is not.
    called: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                called.add(func.attr)
    for forbidden in (
        "system",
        "popen",
        "spawn",
        "execv",
        "execvp",
        "check_call",
        "check_output",
    ):
        assert forbidden not in called, f"seeding must not shell out: calls {forbidden}()"


def test_merged_servers_preserves_unrelated_entries(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    entry = _built_veeva(tmp_path)
    monkeypatch.setenv("XYB_VEEVA_DIR", str(entry.parents[1]))
    monkeypatch.setenv("METASO_API_KEY", "test-key")
    existing = {"my-own-mcp": {"transport": "stdio", "command": "mine"}}

    merged = merged_servers(existing, build_seed_plan(existing))

    assert merged["my-own-mcp"] == existing["my-own-mcp"]


def test_only_seeds_named_servers(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    entry = _built_veeva(tmp_path)
    monkeypatch.setenv("XYB_VEEVA_DIR", str(entry.parents[1]))

    plan = build_seed_plan({}, only=("xyb-clinicaltrials",))

    assert {step.name for step in plan.steps} == {"xyb-clinicaltrials"}


def test_channel_of_maps_our_servers_only() -> None:
    assert channel_of("xyb-chictr") == "chictr"
    assert channel_of("someone-elses-server") is None


def test_added_specs_are_accepted_by_the_real_validator(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The plan must produce specs the connector service would actually save."""
    entry = _built_veeva(tmp_path)
    monkeypatch.setenv("XYB_VEEVA_DIR", str(entry.parents[1]))
    monkeypatch.setenv("METASO_API_KEY", "test-key")

    servers = build_seed_plan({}).to_add
    normalized = validate_servers_map(servers)

    assert set(normalized) == set(servers)
    for name, spec in normalized.items():
        assert spec["enabled"] is True, name
        assert spec["default_open"] is True, name
