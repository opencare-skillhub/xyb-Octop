"""``octop xyb init-mcp`` — end-to-end wiring through the offline CLI."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from octop.cli.main import cli


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    return tmp_path


@pytest.fixture
def built_veeva(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    entry = tmp_path / "ctv-mcp-server" / "dist" / "index.js"
    entry.parent.mkdir(parents=True)
    entry.write_text("// fake entrypoint\n", encoding="utf-8")
    monkeypatch.setenv("XYB_VEEVA_DIR", str(entry.parents[1]))
    monkeypatch.setenv("METASO_API_KEY", "test-key")
    return entry


def _bootstrap() -> None:
    result = CliRunner().invoke(
        cli,
        ["init", "--admin-username", "alice", "--admin-password", "TestPass12", "--yes"],
    )
    assert result.exit_code == 0, result.output


def _stored_servers() -> dict:
    from octop.cli.support.db import open_cli_services
    from octop.infra.connectors.service import ConnectorService

    with open_cli_services() as services:
        service = ConnectorService(
            repo=services.repos.connector_repo,
            secret_repo=services.secret_repo,
            settings_repo=services.settings_repo,
            config=services.config,
        )
        return service.get_custom_servers(1)


def test_init_mcp_writes_servers_and_is_idempotent(fake_home: Path, built_veeva: Path) -> None:
    _bootstrap()
    runner = CliRunner()

    first = runner.invoke(cli, ["xyb", "init-mcp", "--user", "alice"])
    assert first.exit_code == 0, first.output
    servers = _stored_servers()
    assert servers, "nothing was written"
    assert all(spec["enabled"] is True for spec in servers.values())
    assert "xyb-clinicaltrials" in servers
    assert servers["xyb-veeva"]["args"][0].endswith("index.js")

    # Second run must not duplicate or rewrite anything.
    before = _stored_servers()
    second = runner.invoke(cli, ["xyb", "init-mcp", "--user", "alice"])
    assert second.exit_code == 0, second.output
    assert _stored_servers() == before
    assert "已新增 0 个" in second.output


def test_init_mcp_dry_run_writes_nothing(fake_home: Path, built_veeva: Path) -> None:
    _bootstrap()

    result = CliRunner().invoke(cli, ["xyb", "init-mcp", "--user", "alice", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert _stored_servers() == {}
    assert "dry-run" in result.output


def test_init_mcp_preserves_an_operator_edited_server(fake_home: Path, built_veeva: Path) -> None:
    """A server the operator already configured must survive the seeding."""
    _bootstrap()
    from octop.cli.support.db import open_cli_services
    from octop.infra.connectors.service import ConnectorService

    with open_cli_services() as services:
        service = ConnectorService(
            repo=services.repos.connector_repo,
            secret_repo=services.secret_repo,
            settings_repo=services.settings_repo,
            config=services.config,
        )
        service.put_custom_servers(
            1,
            {
                "xyb-chictr": {
                    "transport": "stdio",
                    "command": "my-own-chictr",
                    "enabled": False,
                }
            },
        )

    result = CliRunner().invoke(cli, ["xyb", "init-mcp", "--user", "alice"])
    assert result.exit_code == 0, result.output

    servers = _stored_servers()
    assert servers["xyb-chictr"]["command"] == "my-own-chictr"
    assert servers["xyb-chictr"]["enabled"] is False
    # The other channels were still added around it.
    assert "xyb-clinicaltrials" in servers


def test_init_mcp_requires_an_acting_user(fake_home: Path, built_veeva: Path) -> None:
    _bootstrap()

    result = CliRunner().invoke(cli, ["xyb", "init-mcp"])

    assert result.exit_code != 0
    assert "no acting user" in result.output.lower()


def test_init_mcp_only_seeds_the_named_server(fake_home: Path, built_veeva: Path) -> None:
    _bootstrap()

    result = CliRunner().invoke(
        cli, ["xyb", "init-mcp", "--user", "alice", "--only", "xyb-clinicaltrials"]
    )

    assert result.exit_code == 0, result.output
    assert set(_stored_servers()) == {"xyb-clinicaltrials"}


def test_init_mdt_lists_plan_without_creating(fake_home: Path) -> None:
    """--dry-run must not create agents; it only reports the plan."""
    _bootstrap()

    result = CliRunner().invoke(cli, ["xyb", "init-mdt", "--user", "alice", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "将创建" in result.output
    assert "会诊团队" in result.output
    # No agent rows were created beyond the bootstrap default.
    from octop.cli.support.db import open_cli_services

    with open_cli_services() as services:
        assert services.repos.agent_repo.list_by_user(1) == []


def test_default_mdt_members_are_the_expected_roster() -> None:
    """The roster is asserted exactly, so a role cannot be dropped silently.

    An adversarial review found `xyb-mdt-intervention` missing from this tuple
    while a `<= 12` bound still passed. Requirement FR-4.1 lists it as A-group
    role #5, so the assertion names every member.
    """
    from octop.cli.commands.xyb import DEFAULT_MDT_MEMBERS

    assert DEFAULT_MDT_MEMBERS == (
        "xyb-mdt-surgery",
        "xyb-mdt-oncology",
        "xyb-mdt-imaging",
        "xyb-mdt-pathology",
        "xyb-mdt-intervention",
        "xyb-mdt-radiation",
        "xyb-mdt-nutrition",
        "xyb-mdt-psych",
        "xyb-mdt-palliative",
        "xyb-genomics",
        "xyb-trial-matching",
    )
    # Acute-complication perspectives are reached directly, not via the team.
    assert not any(member.startswith("xyb-acute-") for member in DEFAULT_MDT_MEMBERS)


def test_default_mdt_members_all_exist_in_the_library() -> None:
    """Every roster entry must have a real expert package, or init-mdt fails halfway."""
    from octop.cli.commands.xyb import DEFAULT_MDT_MEMBERS

    library = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "octop"
        / "infra"
        / "agents"
        / "experts"
        / "library"
    )
    missing = [
        expert
        for expert in DEFAULT_MDT_MEMBERS
        if not (library / expert / "manifest.json").is_file()
    ]
    assert not missing, f"roster references experts with no package: {missing}"
    # A consultation that fans out to everything defeats the cost rule.
    assert len(DEFAULT_MDT_MEMBERS) <= 12


def test_orchestration_rules_carry_the_medical_flow() -> None:
    """The seeded rules must contain the clauses the design doc requires."""
    from octop.cli.commands.xyb import _ORCHESTRATION_RULES

    for required in (
        "12356",  # crisis hotline
        "不派工",  # crisis path does not dispatch
        "分歧点",  # disagreements must be surfaced
        "综合各位专家意见",  # explicitly forbidden phrasing
        "2–4",  # bounded fan-out
        "未提供",  # missing data is named, not guessed
    ):
        assert required in _ORCHESTRATION_RULES, f"rules lack: {required}"
