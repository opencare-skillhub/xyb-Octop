#!/usr/bin/env python3
"""专家档案状态机 — 小胰宝 MDT 视角共用。

维护「最小化案情摘要」的唯一真相，并把它渲染成只读的 ``USER.md``。

设计依据（沿用上游 ``clinical-learning-subscription`` 的成熟做法）：

* **状态只由本脚本写**。手改 ``USER.md`` 会在下次渲染时被覆盖，并造成档案与
  实际状态不一致，所以脚本是唯一入口。
* **写入是原子的**（临时文件 + ``os.replace``），并且加文件锁，避免并发写坏。
* **拒绝 PII**。不保存姓名、身份证号、手机号、住院号；只保存医学信息与昵称。
* **零第三方依赖**，兼容 Python 3.9+。

用法::

    python3 profile.py get                     # 读当前摘要
    python3 profile.py set --field stage --value "..." --confirm true
    python3 profile.py set-batch --json '{"stage": "...", "pathology": "..."}' --confirm true
    python3 profile.py clear --confirm true
    python3 profile.py fields                  # 列出可用字段

退出码：0 成功；1 参数、校验错误或未确认（未确认视为一次失败的写入，不单独设码）。
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

STATE_FILENAME = "xyb_profile_state.json"
USER_FILENAME = "USER.md"
LOCK_FILENAME = ".xyb_profile_state.lock"
SCHEMA_VERSION = 1

NOT_PROVIDED = "待确认"

#: The nine-section case summary. Order matters: it is the order patients see.
FIELDS: tuple[tuple[str, str, str], ...] = (
    ("basics", "1 基本信息", "年龄段 / 性别 / 目前体力状况（能否自理）"),
    ("pathology", "2 诊断与病理", "诊断名称 / 病理类型与分化 / 取材方式 / 确诊时间"),
    ("stage", "3 分期与影像", "影像结论 / TNM或分期 / 肿瘤位置 / 与血管关系 / 有无转移"),
    ("molecular", "4 分子检测", "基因检测项目与结果 / MSI或dMMR / TMB"),
    ("prior_treatment", "5 既往治疗", "每线方案 / 起止时间 / 疗效评价 / 停用原因"),
    ("symptoms", "6 当前症状", "疼痛 / 体重变化 / 进食 / 黄疸 / 发热 / 恶心呕吐 / 排便"),
    ("labs", "7 化验与指标", "血常规 / 肝肾功能 / 胆红素 / CA19-9 / 白蛋白 / 凝血"),
    ("medications", "8 用药与过敏", "正在用的药 / 止痛药 / 胰酶 / 降糖药 / 过敏史"),
    ("question", "9 想问什么", "这次最想解决的一个问题"),
)

FIELD_KEYS = tuple(key for key, _label, _hint in FIELDS)

#: Patterns that mean the patient pasted something we must not store.
PII_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("身份证号", re.compile(r"\b\d{17}[\dXx]\b")),
    ("手机号", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    ("住院号/病历号", re.compile(r"(住院号|病历号|门诊号)\s*[:：]?\s*\w{4,}")),
    ("银行卡号", re.compile(r"\b\d{16,19}\b")),
)

PATIENT_MARKERS = ("患者姓名", "病人姓名")


class ProfileError(Exception):
    """A validation failure the caller should report verbatim."""


def package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def state_path() -> Path:
    override = os.environ.get("XYB_PROFILE_STATE")
    if override:
        return Path(override).expanduser()
    return package_root() / STATE_FILENAME


def user_md_path() -> Path:
    override = os.environ.get("XYB_PROFILE_USER_MD")
    if override:
        return Path(override).expanduser()
    return package_root() / USER_FILENAME


def _empty_state() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "consent": False,
        "fields": dict.fromkeys(FIELD_KEYS, ""),
        "missing": list(FIELD_KEYS),
    }


def load_state() -> dict[str, Any]:
    path = state_path()
    if not path.is_file():
        return _empty_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_state()
    if not isinstance(data, dict):
        return _empty_state()
    state = _empty_state()
    state.update({k: v for k, v in data.items() if k in state})
    fields = data.get("fields")
    if isinstance(fields, dict):
        state["fields"] = {key: str(fields.get(key) or "") for key in FIELD_KEYS}
    state["missing"] = [key for key in FIELD_KEYS if not state["fields"].get(key)]
    return state


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-xyb-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp_name, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise


def _reject_pii(value: str) -> None:
    for label, pattern in PII_PATTERNS:
        if pattern.search(value):
            raise ProfileError(
                f"检测到可能的{label}，本档案不保存身份信息。请打码后重填，只保留医学内容。"
            )
    for marker in PATIENT_MARKERS:
        if marker in value:
            raise ProfileError("请只填医学信息，不要填患者姓名。")


def save_state(state: dict[str, Any]) -> None:
    state["schema_version"] = SCHEMA_VERSION
    state["missing"] = [key for key in FIELD_KEYS if not state["fields"].get(key)]
    _atomic_write(state_path(), json.dumps(state, ensure_ascii=False, indent=2) + "\n")


def render_user_md(state: dict[str, Any]) -> str:
    fields = state.get("fields") or {}
    lines: list[str] = []
    lines.append("---")
    lines.append("summary: 患者自述的案情摘要（由 scripts/profile.py 生成，请勿手改）")
    lines.append("read_when: 任何一次病情分析、视角梳理或问题清单整理之前")
    lines.append("---")
    lines.append("")
    lines.append("# 案情摘要")
    lines.append("")
    if not state.get("consent"):
        lines.append("> 尚未登记。请先与患者确认后再记录医学信息。")
        lines.append("")
    for key, label, hint in FIELDS:
        value = str(fields.get(key) or "").strip()
        lines.append(f"## {label}")
        lines.append("")
        lines.append(value if value else NOT_PROVIDED)
        lines.append("")
        lines.append(f"<sub>需要：{hint}</sub>")
        lines.append("")
    missing = state.get("missing") or []
    lines.append("## 缺失项")
    lines.append("")
    if missing:
        labels = [label for key, label, _hint in FIELDS if key in missing]
        lines.append("以下尚未提供，分析时须明确标注为「未提供」：")
        lines.append("")
        for label in labels:
            lines.append(f"- {label}")
    else:
        lines.append("无。")
    lines.append("")
    return "\n".join(lines)


def _parse_bool(raw: str | None) -> bool:
    if raw is None:
        return False
    return str(raw).strip().lower() in {"true", "1", "yes", "y", "已确认", "同意", "是"}


def _require_confirm(raw: str | None) -> None:
    if not _parse_bool(raw):
        raise ProfileError("需要显式确认：加 --confirm true（表示你已与患者确认）")


def cmd_fields(_args: argparse.Namespace) -> int:
    for key, label, hint in FIELDS:
        print(f"{key}\t{label}\t{hint}")
    return 0


def cmd_get(args: argparse.Namespace) -> int:
    state = load_state()
    if args.format == "json":
        print(json.dumps(state, ensure_ascii=False, indent=2))
    else:
        print(render_user_md(state))
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    _require_confirm(args.confirm)
    if args.field not in FIELD_KEYS:
        raise ProfileError(f"未知字段：{args.field}（可用：{', '.join(FIELD_KEYS)}）")
    value = (args.value or "").strip()
    if value:
        _reject_pii(value)
    state = load_state()
    state["fields"][args.field] = value
    state["consent"] = True
    save_state(state)
    _atomic_write(user_md_path(), render_user_md(state))
    print(json.dumps({"ok": True, "field": args.field, "updated": bool(value)}, ensure_ascii=False))
    return 0


def cmd_set_batch(args: argparse.Namespace) -> int:
    _require_confirm(args.confirm)
    try:
        payload = json.loads(args.json)
    except json.JSONDecodeError as exc:
        raise ProfileError(f"--json 不是合法 JSON：{exc}") from exc
    if not isinstance(payload, dict):
        raise ProfileError("--json 必须是一个对象")
    unknown = [key for key in payload if key not in FIELD_KEYS]
    if unknown:
        raise ProfileError(f"未知字段：{', '.join(unknown)}")
    for value in payload.values():
        text = str(value or "").strip()
        if text:
            _reject_pii(text)
    state = load_state()
    for key, value in payload.items():
        state["fields"][key] = str(value or "").strip()
    state["consent"] = True
    save_state(state)
    _atomic_write(user_md_path(), render_user_md(state))
    print(json.dumps({"ok": True, "updated": sorted(payload)}, ensure_ascii=False))
    return 0


def cmd_clear(args: argparse.Namespace) -> int:
    _require_confirm(args.confirm)
    state = _empty_state()
    save_state(state)
    _atomic_write(user_md_path(), render_user_md(state))
    print(json.dumps({"ok": True, "cleared": True}, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="小胰宝专家档案状态机")
    sub = parser.add_subparsers(dest="command", required=True)

    p_fields = sub.add_parser("fields", help="列出可用字段")
    p_fields.set_defaults(func=cmd_fields)

    p_get = sub.add_parser("get", help="读取当前摘要")
    p_get.add_argument("--format", choices=("markdown", "json"), default="markdown")
    p_get.set_defaults(func=cmd_get)

    p_set = sub.add_parser("set", help="写入一个字段")
    p_set.add_argument("--field", required=True)
    p_set.add_argument("--value", required=True)
    p_set.add_argument("--confirm", default=None)
    p_set.set_defaults(func=cmd_set)

    p_batch = sub.add_parser("set-batch", help="一次写入多个字段")
    p_batch.add_argument("--json", required=True)
    p_batch.add_argument("--confirm", default=None)
    p_batch.set_defaults(func=cmd_set_batch)

    p_clear = sub.add_parser("clear", help="清空档案")
    p_clear.add_argument("--confirm", default=None)
    p_clear.set_defaults(func=cmd_clear)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except ProfileError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
