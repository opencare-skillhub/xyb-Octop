"""
v2 层间契约校验（T9 / 防止 Map→Shuffle→Reduce→Context 契约漂移）

提供纯函数校验器，返回「问题描述」列表（不抛异常）：
- validate_map_output：单条 Map 输出是否符合 data-contract
- validate_context：渲染 context 是否满足模板所需的关键不变量
                    （含「姓名不得是占位符」「时间轴标题不得是文件名」等回归护栏）

生产环境以 logger.warning 形式提示；测试中可断言问题列表为空。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

REPORT_TYPES = {
    'lab_results', 'imaging', 'pathology', 'medication',
    'clinical_records', 'basic_info', 'invoice', 'noise', 'error',
}

_DATE_OK = re.compile(r'^(\d{4}|\d{4}-\d{2}|\d{4}-\d{2}-\d{2})$')
_FILENAME_RE = re.compile(r'\.(pdf|jpe?g|png|heic|webp|bmp|tiff|md|docx?|xlsx?)\b', re.IGNORECASE)
_PLACEHOLDER_RE = re.compile(r'\[(NAME|PHONE|ID|MRN|EMAIL|ADDRESS|CARD)_\d+\]')


def validate_map_output(item: Dict[str, Any]) -> List[str]:
    """校验单条 Map 输出。返回问题列表（空=通过）。"""
    issues: List[str] = []
    if not isinstance(item, dict):
        return ['map 输出不是 dict']
    rt = item.get('report_type')
    if rt not in REPORT_TYPES:
        issues.append(f'report_type 非法: {rt!r}')
    # 日期精度：允许空 / YYYY / YYYY-MM / YYYY-MM-DD
    d = item.get('document_date') or item.get('report_date') or ''
    if d and not _DATE_OK.match(str(d)):
        issues.append(f'document_date 格式异常: {d!r}')
    # lab_values 结构
    lv = item.get('lab_values')
    if lv is not None:
        if not isinstance(lv, list):
            issues.append('lab_values 不是数组')
        else:
            for i, row in enumerate(lv):
                if not isinstance(row, dict) or not (row.get('name') or '').strip():
                    issues.append(f'lab_values[{i}] 缺少 name')
                    break
    return issues


def validate_context(ctx: Dict[str, Any]) -> List[str]:
    """校验渲染 context 的关键不变量。返回问题列表（空=通过）。"""
    issues: List[str] = []
    required = [
        'demographics', 'timeline_items', 'tumor_marker_tables',
        'genetic_highlights', 'imaging_summary', 'medication_table',
    ]
    for key in required:
        if key not in ctx:
            issues.append(f'context 缺少必需键: {key}')

    demo = ctx.get('demographics') or {}
    name = str(demo.get('name', '') or '')
    if _PLACEHOLDER_RE.search(name):
        issues.append(f'demographics.name 仍是脱敏占位符: {name!r}')

    # 时间轴标题/事件不得是文件名（根因 R10 回归护栏）
    for t in (ctx.get('timeline_items') or []):
        if not isinstance(t, dict):
            continue
        label = str(t.get('event') or t.get('title') or '')
        if _FILENAME_RE.search(label):
            issues.append(f'时间轴条目疑似使用文件名: {label!r}')
            break

    # 标题不得泄漏占位符
    title = str(ctx.get('report_title', '') or '')
    if _PLACEHOLDER_RE.search(title):
        issues.append(f'report_title 含脱敏占位符: {title!r}')

    return issues
