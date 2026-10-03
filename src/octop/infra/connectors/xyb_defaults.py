"""XYB default MCP servers for the xiaoyibao distribution.

Upstream Octop ships **no** MCP seeding at all: the only writer of a
``kind='custom-mcp'`` connector row is the user-facing
``PUT /api/connectors/custom-mcp``. This module adds the missing bootstrap for
the clinical channels the patient-facing experts depend on.

Four clinical channels, carried by seven servers
------------------------------------------------

==============  ==============================================================
clinicaltrials  ClinicalTrials.gov API v2 (npm, public)
chinadrugs      China drug trial registry (NOT an MCP: a session-cookie CLI
                skill imported on the trial-matching expert)
chictr          China clinical trial registry (npm, may hit a captcha)
veeva           Veeva CTV (local stdio, needs a local index built first)
==============  ==============================================================

Three further servers are supporting capability, not channels: PubMed for
literature, Metaso for general search, and Dayi for drug/disease lookup.

Seeding rules (all four are deliberate)
---------------------------------------

1. **Add-only, never overwrite.** An existing server with the same name is left
   exactly as the operator configured it. This is why the merge happens here
   instead of calling ``put_custom_servers`` with a fresh map, which would
   replace the whole document.
2. **A missing key skips, it does not fail.** Servers marked ``requires_env``
   are not written when the variable is unset; the report says which variable
   to set. Writing a config that cannot start would turn a clear "not
   configured" into an opaque runtime error.
3. **No dependency installation.** The module writes configuration and reports
   what is missing. It never runs ``npm install`` behind the operator's back.
4. **Dry-run first.** ``build_seed_plan`` is pure: it takes the current servers
   and returns what *would* change, so ``--dry-run`` and the real run share one
   code path.

The veeva server is a local source checkout rather than an npm package (it is
not published). Its location resolves from ``XYB_VEEVA_DIR`` and falls back to
``~/Downloads/ctv-mcp-server``; when the built entrypoint is absent the server
is reported as unbuilt rather than written as a broken command.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Channels exposed to experts, in the order the dashboard should show them.
CHANNELS: tuple[str, ...] = ("clinicaltrials", "chinadrugs", "chictr", "veeva")


@dataclass(frozen=True)
class ServerSpec:
    """One MCP server we know how to configure."""

    name: str
    #: Which clinical channel (or supporting capability) this server carries.
    channel: str
    display_name: str
    #: The JSON spec written into the connector document.
    spec: dict[str, Any]
    #: Env vars that must all be present before the server is written.
    requires_env: tuple[str, ...] = ()
    #: Extra precondition description shown when the server is not written.
    precondition: str = ""
    #: Whether the server should be attached to a turn without an explicit pick.
    default_open: bool = True
    #: One-line operator hint, printed when the server is skipped or unbuilt.
    hint: str = ""


def _npx(package: str, binary: str | None = None) -> dict[str, Any]:
    """An npx-launched stdio spec.

    ``binary`` is needed when a package ships more than one bin, or when its
    only bin is not named after the package: ``npx -y <pkg>`` then has no way to
    choose and dies with "could not determine executable to run", which surfaces
    as an opaque "server closed stdout before replying".
    """
    args = ["-y", "-p", package, binary] if binary else ["-y", package]
    return {"transport": "stdio", "command": "npx", "args": args}


def _veeva_dir() -> Path:
    configured = os.environ.get("XYB_VEEVA_DIR")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / "Downloads" / "ctv-mcp-server"


def _stdio(command: str, *args: str) -> dict[str, Any]:
    """A stdio spec.

    The harness has no working-directory field, so callers must pass absolute
    paths for anything they reference on disk.
    """
    return {"transport": "stdio", "command": command, "args": list(args)}


def build_server_specs() -> list[ServerSpec]:
    """Return every server this distribution knows how to configure.

    Paths are resolved at call time so a test can point the environment at a
    temporary directory.
    """
    veeva_dir = _veeva_dir()
    veeva_entry = veeva_dir / "dist" / "index.js"

    return [
        ServerSpec(
            name="xyb-clinicaltrials",
            channel="clinicaltrials",
            display_name="小胰宝 · 临床查询（ClinicalTrials.gov）",
            spec=_npx("xiaoyibao-clinical-trials@1.0.0"),
            hint="公开数据源，无需凭据",
        ),
        ServerSpec(
            name="xyb-chictr",
            channel="chictr",
            display_name="小胰宝 · 中国临床试验注册中心",
            # 2.0.2 is pinned on purpose: older versions take incompatible
            # parameters, and the site may ask for human verification.
            spec=_npx("chictr-mcp-server@2.0.2"),
            precondition="首次运行需下载 npm 包与 Playwright Chromium（约 570MB）",
            hint="站点可能要求人工验证；如遇验证请本人完成，本工具不绕过",
        ),
        ServerSpec(
            name="xyb-veeva",
            channel="veeva",
            display_name="小胰宝 · Veeva CTV 临床查询",
            spec=_stdio("node", str(veeva_entry)),
            precondition=(
                f"需要本地 ctv-mcp-server 源码并已构建（{veeva_entry}）"
                if not veeva_entry.is_file()
                else "索引未建时检索会返回 INDEX_EMPTY，需先 import_csv_export 或 sync_sitemap"
            ),
            hint="用 XYB_VEEVA_DIR 指向本地 ctv-mcp-server 目录",
        ),
        # chinadrugs is not seeded as an MCP server: upstream ships it as a CLI
        # skill that drives the registry with the patient's own browser session
        # (imported as `chinadrugs-collect` on the trial-matching expert). Only
        # three channels are MCP-backed: clinicaltrials, chictr and veeva.
        ServerSpec(
            name="xyb-pubmed",
            channel="literature",
            display_name="小胰宝 · PubMed 文献检索",
            spec=_npx("mcp-pubmed-llm-server@3.0.0"),
            hint="无 key 亦可使用（有限速）；PUBMED_API_KEY 可提高额度",
        ),
        ServerSpec(
            name="xyb-metaso",
            channel="search",
            display_name="小胰宝 · 秘塔通用检索",
            spec=_npx("metaso-search-mcp@1.1.2", binary="metaso-mcp"),
            requires_env=("METASO_API_KEY",),
            hint="需先配置 METASO_API_KEY；未配置时不写入",
        ),
        ServerSpec(
            name="xyb-dayi",
            channel="drug-search",
            display_name="小胰宝 · 日大医用药与疾病查询",
            spec=_npx("@xiaoyibao_2025/dayi-mcp-server@0.1.7"),
            hint="公开检索，无需凭据",
        ),
    ]


@dataclass
class SeedStep:
    """The decision made for one server."""

    name: str
    channel: str
    action: str  # "add" | "keep" | "skip" | "unbuilt"
    reason: str = ""
    spec: dict[str, Any] = field(default_factory=dict)


@dataclass
class SeedPlan:
    """Everything the seeder decided, ready for display or application."""

    steps: list[SeedStep] = field(default_factory=list)

    @property
    def to_add(self) -> dict[str, Any]:
        """The merged ``servers`` map to write back, or ``{}`` for no change."""
        if not self.added:
            return {}
        return {step.name: step.spec for step in self.added}

    @property
    def added(self) -> list[SeedStep]:
        return [s for s in self.steps if s.action == "add"]

    @property
    def kept(self) -> list[SeedStep]:
        return [s for s in self.steps if s.action == "keep"]

    @property
    def skipped(self) -> list[SeedStep]:
        return [s for s in self.steps if s.action in {"skip", "unbuilt"}]


def build_seed_plan(
    existing: dict[str, Any] | None = None,
    *,
    env: dict[str, str] | None = None,
    only: tuple[str, ...] | None = None,
) -> SeedPlan:
    """Decide, without writing anything, what the seeder would do.

    Pure apart from reading the filesystem for the veeva entrypoint: given the
    same inputs it always returns the same plan, which is what makes
    ``--dry-run`` trustworthy.
    """
    environ = os.environ if env is None else env
    present = existing or {}
    plan = SeedPlan()

    for spec in build_server_specs():
        if only is not None and spec.name not in only:
            continue

        if spec.name in present:
            plan.steps.append(
                SeedStep(
                    name=spec.name,
                    channel=spec.channel,
                    action="keep",
                    reason="已存在同名配置，保持不动",
                )
            )
            continue

        missing = [var for var in spec.requires_env if not environ.get(var)]
        if missing:
            plan.steps.append(
                SeedStep(
                    name=spec.name,
                    channel=spec.channel,
                    action="skip",
                    reason=f"缺少环境变量 {', '.join(missing)}",
                )
            )
            continue

        # A local stdio server whose entrypoint does not exist would be written
        # as a command that fails at startup. Report it instead of pretending.
        if spec.name == "xyb-veeva":
            command = str(spec.spec.get("command", ""))
            args = spec.spec.get("args") or []
            entry = Path(str(args[0])) if command == "node" and args else None
            if entry is not None and not entry.is_file():
                plan.steps.append(
                    SeedStep(
                        name=spec.name,
                        channel=spec.channel,
                        action="unbuilt",
                        reason=f"本地入口不存在：{entry}",
                    )
                )
                continue

        payload = dict(spec.spec)
        payload["display_name"] = spec.display_name
        payload["enabled"] = True
        if spec.default_open:
            payload["default_open"] = True
        plan.steps.append(
            SeedStep(
                name=spec.name,
                channel=spec.channel,
                action="add",
                spec=payload,
            )
        )
    return plan


def merged_servers(existing: dict[str, Any] | None, plan: SeedPlan) -> dict[str, Any]:
    """Existing servers plus the additions from ``plan``.

    Add-only: a name already present is never replaced, so an operator who
    edited or disabled a server keeps their change.
    """
    merged: dict[str, Any] = dict(existing or {})
    merged.update(plan.to_add)
    return merged


def channel_of(server_name: str) -> str | None:
    """Map a configured server name back to its channel, if we own it."""
    for spec in build_server_specs():
        if spec.name == server_name:
            return spec.channel
    return None
