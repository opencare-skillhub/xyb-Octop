"""``octop xyb`` — xiaoyibao distribution maintenance commands."""

from __future__ import annotations

import json as _json
import sys
from typing import Any

import click

from octop.cli.support.ctx import json_output_enabled
from octop.infra.agents.manager import AgentCreateSpec
from octop.infra.errors import ErrorCode

#: Expert templates instantiated as MDT team members. This is the A group of
#: XYB-REQUIREMENTS.md section FR-4.1 (nine roles, intervention included) plus
#: genomics and the trial specialist.
#:
#: The acute-complication perspectives are excluded on purpose: they are meant to
#: be consulted directly, and a consultation that fans out to sixteen experts
#: costs sixteen model calls (see XYB-DESIGN.md section 5.5). A test asserts the
#: exact roster so a role cannot be dropped silently -- intervention was missing
#: until an adversarial review caught it.
DEFAULT_MDT_MEMBERS: tuple[str, ...] = (
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

MDT_TEAM_WELCOME = (
    "这是小胰宝 MDT 会诊。我会按你的问题挑选 2–4 个相关视角分别梳理，"
    "再把各视角的问题清单和**分歧点**并列给你。我只做编排，不给会诊结论。"
)


@click.group("xyb")
def xyb() -> None:
    """Xiaoyibao distribution setup (clinical channels, brand checks)."""


def _resolve_user_id(as_user: str | None, services: Any) -> int:
    from octop.cli.support.db import resolve_cli_user_id

    user_id = resolve_cli_user_id(as_user, services=services)
    if user_id is None:
        raise click.ClickException(
            "no acting user: pass --user <name> or run `octop config set-user <name>`"
        )
    return user_id


def _connector_service(services: Any) -> Any:
    """Build the same ConnectorService the API layer builds.

    ``SharedServices`` deliberately exposes only repositories, so a CLI command
    that needs connector behaviour composes the service the same way
    ``api/routers/connectors.py`` does.
    """
    from octop.infra.connectors.service import ConnectorService

    return ConnectorService(
        repo=services.repos.connector_repo,
        secret_repo=services.secret_repo,
        settings_repo=services.settings_repo,
        config=services.config,
    )


@xyb.command("init-mcp")
@click.option("--user", "as_user", default=None, help="Acting user (defaults to the pinned user).")
@click.option("--dry-run", is_flag=True, help="Print the plan without writing anything.")
@click.option(
    "--only",
    "only_names",
    multiple=True,
    help="Seed only these server names (repeatable).",
)
def init_mcp(as_user: str | None, dry_run: bool, only_names: tuple[str, ...]) -> None:
    """Seed the xiaoyibao default MCP servers for one user.

    Add-only and idempotent: a server that already exists is left untouched, and
    a server whose prerequisite is missing is reported rather than written.
    """
    from octop.cli.support.db import open_cli_services
    from octop.infra.connectors.xyb_defaults import (
        build_seed_plan,
        merged_servers,
    )
    from octop.infra.errors import OctopError

    only = tuple(only_names) if only_names else None

    try:
        with open_cli_services() as services:
            user_id = _resolve_user_id(as_user, services)
            connector_service = _connector_service(services)
            existing = connector_service.get_custom_servers(user_id)

            plan = build_seed_plan(existing, only=only)

            if dry_run:
                _print_plan(plan, dry_run=True)
                return

            if not plan.added:
                _print_plan(plan, dry_run=False)
                return

            connector_service.put_custom_servers(
                user_id,
                merged_servers(existing, plan),
            )
    except OctopError as exc:
        click.echo(f"error: {exc.message}", err=True)
        raise SystemExit(1) from exc

    _print_plan(plan, dry_run=False)


@xyb.command("init-mdt")
@click.option("--user", "as_user", default=None, help="Acting user (defaults to the pinned user).")
@click.option(
    "--member",
    "members",
    multiple=True,
    help="Expert id to instantiate as a team member (repeatable; defaults to all).",
)
@click.option("--name", default=None, help="Team host display name.")
@click.option("--dry-run", is_flag=True, help="Print the plan without creating anything.")
def init_mdt(
    as_user: str | None,
    members: tuple[str, ...],
    name: str | None,
    dry_run: bool,
) -> None:
    """Create the MDT expert instances and the consultation host team.

    The library packages are **templates**: they cost nothing until an instance
    exists. A team host, however, needs real member agent ids, so this command
    instantiates the roster first and then creates the ``kind=team`` host.

    Idempotent: an expert that already has an instance for this user is reused,
    and an existing MDT team is reported rather than duplicated.
    """
    import asyncio

    from octop.cli.support.acting import resolve_cli_acting_user_id
    from octop.infra.agents.experts.catalog import build_create_spec_from_expert
    from octop.infra.agents.teams import TEAM_KIND, TEAM_TEMPLATE_NAME
    from octop.infra.errors import OctopError
    from octop.infra.utils.locale import resolve_user_locale

    selected = tuple(members) if members else DEFAULT_MDT_MEMBERS
    team_name = name or "小胰宝 MDT 会诊"

    try:
        uid = resolve_cli_acting_user_id(None, as_user)
    except OctopError as exc:
        click.echo(f"error: {exc.message}", err=True)
        raise SystemExit(1) from exc

    async def _plan_only() -> list[tuple[str, str]]:
        from octop.cli.support.db import open_cli_services

        with open_cli_services() as services:
            rows = services.repos.agent_repo.list_by_user(uid)
            return [(r.agent_id, r.template_name or "") for r in rows]

    existing: list[tuple[str, str]] = asyncio.run(_plan_only())
    have = {template: agent_id for agent_id, template in existing if template}

    if dry_run:
        to_create = [expert for expert in selected if expert not in have]
        table_lines = [
            f"将创建 {len(to_create)} 个专家实例，复用 {len(selected) - len(to_create)} 个"
        ]
        for expert in selected:
            mark = "复用" if expert in have else "创建"
            table_lines.append(f"  [{mark}] {expert}")
        has_team = any(template == TEAM_TEMPLATE_NAME for _aid, template in existing)
        table_lines.append(f"会诊团队：{'已存在，跳过' if has_team else '将创建'}")
        click.echo("\n".join(table_lines))
        return

    async def _run() -> dict[str, Any]:
        from octop.cli.repl.embedded_session import embedded_runtime

        created: list[str] = []
        member_ids: list[str] = []

        async with embedded_runtime() as server:
            assert server.app_runtime is not None
            assert server.services is not None
            registry = server.app_runtime.agent_registry
            catalog = server.expert_catalog
            if catalog is None:
                raise OctopError(ErrorCode.NOT_FOUND, "expert catalog unavailable")

            rows = server.services.repos.agent_repo.list_by_user(uid)
            by_template = {r.template_name: r.agent_id for r in rows if r.template_name}

            for expert_id in selected:
                agent_id = by_template.get(expert_id)
                if agent_id is None:
                    expert = catalog.get(expert_id)
                    if expert is None:
                        raise OctopError(ErrorCode.NOT_FOUND, f"expert {expert_id!r} not found")
                    locale = resolve_user_locale(user_repo=server.services.user_repo, user_id=uid)
                    spec = build_create_spec_from_expert(
                        expert_id=expert_id,
                        expert=expert,
                        user_id=uid,
                        locale=locale,
                    )
                    row = await registry.create(spec, defer_bootstrap=True)
                    agent_id = row.agent_id
                    created.append(agent_id)
                member_ids.append(agent_id)

            team_id = by_template.get(TEAM_TEMPLATE_NAME)
            if team_id is None:
                team = await registry.create(
                    AgentCreateSpec(
                        name=team_name,
                        user_id=uid,
                        kind=TEAM_KIND,
                        template_name=TEAM_TEMPLATE_NAME,
                        member_ids=member_ids,
                        welcome_message=MDT_TEAM_WELCOME,
                    )
                )
                team_id = team.agent_id
                added_to_team = len(member_ids)
            else:
                # An existing team must actually receive the new roster. Writing
                # members only on creation made `--member` a no-op that still
                # reported the new count, and left the orchestration rules frozen
                # at whatever they were when the team was first created.
                teams = server.app_runtime.agent_registry.teams
                current = teams.member_ids(team_id)
                missing = [mid for mid in member_ids if mid not in current]
                if missing:
                    next_roster = [*current, *missing]
                    teams.assert_roster_writable(team_id, next_roster)
                    teams.replace_members(team_id, next_roster)
                    await registry.reload(team_id)
                member_ids = next_roster if missing else current
                added_to_team = len(missing)

            # Re-seed every run so a rule change reaches existing teams without a
            # release. The write is idempotent.
            await _write_orchestration_rules(registry, team_id)

        return {
            "created": len(created),
            "reused": len(member_ids) - len(created),
            "member_ids": member_ids,
            "team_id": team_id,
            "added_to_team": added_to_team,
        }

    try:
        result = asyncio.run(_run())
    except OctopError as exc:
        click.echo(f"error: {exc.message}", err=True)
        raise SystemExit(1) from exc

    if json_output_enabled():
        click.echo(_json.dumps(result, indent=2, ensure_ascii=False))
        return
    click.echo(
        f"MDT 会诊已就绪：团队 id {result['team_id']}，"
        f"成员 {len(result['member_ids'])} 位（新建实例 {result['created']}，"
        f"新增入队 {result['added_to_team']}）"
    )


async def _write_orchestration_rules(registry: Any, team_id: str) -> None:
    """Seed the medical orchestration rules into the team host workspace.

    They live in the team *instance* rather than in the shared upstream team
    template on purpose: the generic template is used by every non-medical team
    too, and giving all of them a medical consultation protocol would be wrong.
    """
    row = registry.get_row(team_id)
    if row is None:
        return
    # No public accessor exists for "the workspace of a row that has no running
    # harness agent yet", and the team was just created, so the private helper is
    # the only route. Keep the blast radius to this single call.
    workspace = registry._backend_workspace_for_row(row)  # noqa: SLF001
    await workspace.aupload_many([("MDT-ORCHESTRATION.md", _ORCHESTRATION_RULES.encode("utf-8"))])


def _print_plan(plan: Any, *, dry_run: bool) -> None:
    from rich.console import Console
    from rich.table import Table

    if json_output_enabled():
        click.echo(
            _json.dumps(
                {
                    "dry_run": dry_run,
                    "steps": [
                        {
                            "name": step.name,
                            "channel": step.channel,
                            "action": step.action,
                            "reason": step.reason,
                        }
                        for step in plan.steps
                    ],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    table = Table(title="小胰宝 MCP 播种" + ("（dry-run，未写入）" if dry_run else ""))
    for col in ("server", "通道", "动作", "说明"):
        table.add_column(col)
    for step in plan.steps:
        table.add_row(step.name, step.channel, step.action, step.reason)
    Console(file=sys.stdout).print(table)

    added = len(plan.added)
    kept = len(plan.kept)
    skipped = len(plan.skipped)
    if dry_run:
        click.echo(f"将新增 {added} 个，保持 {kept} 个，跳过 {skipped} 个（未写入）")
    else:
        click.echo(f"已新增 {added} 个，保持 {kept} 个，跳过 {skipped} 个")

    for step in plan.skipped:
        if step.action == "unbuilt":
            click.echo(f"  ! {step.name}: {step.reason}", err=True)


#: Medical orchestration rules, seeded into the team host workspace.
#:
#: The upstream team template already establishes "the coordinator coordinates
#: and does not execute". What it cannot know is the medical flow, so those
#: rules live here and are written into the created team's workspace rather than
#: into the shared template (which every non-medical team also uses).
_ORCHESTRATION_RULES = """\
# MDT 会诊编排规则（医学）

本文优先级高于团队模板的通用说明；与通用说明冲突时，以本文为准。

## 一、先做危机信号筛查（最高优先级）

用户消息到达后，**第一件事**是判断有没有自伤、自杀念头、绝望或情绪失控的信号。

- 有 → **不派工**。由你直接陪伴回应，第一行给出全国心理援助热线 **12356**，
  并建议尽快联系主管医生或就近精神科／心理科。
- 没有 → 进入下面的常规流程。

## 二、齐料：先看案情摘要完整不完整

派工前检查这几项，缺关键项**先问用户**，不要凭经验补全：

| 项 | 为什么必须先有 |
|---|---|
| 分期与影像结论 | 可切除性、放疗与介入的讨论都依赖它 |
| 病理类型与取材方式 | 决定结论的确定性 |
| 既往治疗线数 | 决定「还剩什么可选」 |
| 基因检测结果 | 决定能否讨论靶向／免疫方向 |
| 体力状况 | 决定能否耐受下一步治疗 |

缺项写法：`还缺 <具体项>；先补这一项，我这边才能给你更准的视角。`

成员报回来的内容里，凡是资料没写的，一律写「**未提供**」，不得写「一般来说」「通常」。

## 三、选视角：按问题选 2–4 个，不要全开

| 用户问的是 | 通常选 |
|---|---|
| 能不能手术、要不要开刀 | 胰腺外科 + 影像科（+ 肿瘤内科） |
| 该用什么方案、还有哪些方向 | 肿瘤内科 +（基因检测解读） |
| 报告看不懂、指标什么意思 | 影像科 / 病理科 / 基因检测解读（按报告类型） |
| 黄疸、引流、支架 | 胆道梗阻与引流 + 影像科 |
| 发烧、血象异常 | 感染科 + 血液科 |
| 疼、吃不下、体重掉 | 营养科 + 安宁疗护 |
| 情绪撑不住 | 心理支持（**单独回应，不派工**） |
| 有没有试验可以参加 | 临床试验专员 + 肿瘤内科 |

只有用户明确说「从头到尾理一遍」时才扩大范围。**全开等于十几次模型调用，不是默认动作。**

## 四、派工：写任务说明书，不转发原话

每个成员拿到的是**改写后的任务**，必须包含：

1. **目标**：这次要它回答什么
2. **约束**：只给视角与维度，不出诊断、不推荐医院医生、不预测生存期
3. **交付格式**：明确要求 `【XX视角】` 骨架，第三段必须是「可以问科室医生的具体问题 3–5 条」
4. **相关材料切片**：把该视角需要的部分摘给它，成员看不到本工作区
5. **统一的案情摘要**：所有成员拿到**同一份**摘要，否则各视角说的不是同一件事

## 五、汇总：并列，不要平均成结论

输出结构固定：

```
【MDT 视角汇总】

一、本次参与的视角
二、案情摘要（含缺失项）
三、各视角分述（逐个列出，不复述全文，只保留骨架与问题清单）
四、各视角分歧点及其原因   ← 必须有，且必须写清为什么分歧
五、汇总问题清单（去重后按科室归类）
六、提醒（该补的资料、需要立刻就医的信号）
```

## 六、禁止事项

- ❌ 不得写「综合各位专家意见，建议……」——那等于给出会诊结论
- ❌ 不得复述成员全文
- ❌ 不得编造成员没说过的结论
- ❌ 不得用成员的口吻冒充发言
- ❌ 不得自己对医学问题下判断；你只编排

## 七、收工

成员回来后最多三句收尾：说明这次覆盖了哪些视角、分歧在哪、下一步该补什么。
"""
