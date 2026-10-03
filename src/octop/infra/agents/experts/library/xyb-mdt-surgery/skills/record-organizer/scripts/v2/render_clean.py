"""
v2 渲染净化层（T7 / 针对根因 R12、R13）

职责：
- 脱敏占位符的展示净化：避免把 [NAME_1]/[ID_2] 等占位符直接显示给用户。
- 内容校验：丢弃空行、占位符行、OCR 乱码行，避免噪声进入最终报告。

纯函数、可单测、零网络依赖。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

_PLACEHOLDER_RE = re.compile(r'\[(NAME|PHONE|ID|MRN|EMAIL|ADDRESS|CARD)_\d+\]')


def is_placeholder(value: Any) -> bool:
    """该值是否为脱敏占位符（或仅由占位符构成）。"""
    if not value:
        return False
    s = str(value).strip()
    stripped = _PLACEHOLDER_RE.sub('', s).strip()
    return bool(_PLACEHOLDER_RE.search(s)) and stripped == ''


def clean_name_display(name: Any, default: str = '患者') -> str:
    """姓名展示净化：占位符/空 → 中性标签（默认「患者」）。"""
    if not name or is_placeholder(name):
        return default
    return str(name).strip()


def mask_placeholders(text: Any, repl: str = '***') -> str:
    """把文本中的脱敏占位符替换为中性符号（用于一般字段展示）。"""
    if not text:
        return ''
    return _PLACEHOLDER_RE.sub(repl, str(text))


def _findings_text(row: Dict[str, Any]) -> str:
    f = row.get('findings')
    if isinstance(f, list):
        return '；'.join(str(x) for x in f if x)
    return str(f or row.get('conclusion') or '')


def drop_empty_imaging(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """丢弃 findings 为空/全空白的影像行（如无所见的 PET-CT 空行）。"""
    out: List[Dict[str, Any]] = []
    for r in rows:
        if _findings_text(r).strip():
            out.append(r)
    return out


# OCR 乱码判定：有效中文/字母/数字占比过低，或过短无信息
_MEANINGFUL = re.compile(r'[\u4e00-\u9fa5A-Za-z0-9]')


def looks_like_garbage(text: str, *, min_meaningful: int = 3) -> bool:
    """判断一行文本是否为无意义噪声（有效字符过少）。"""
    if not text:
        return True
    meaningful = len(_MEANINGFUL.findall(text))
    return meaningful < min_meaningful


def drop_placeholder_timeline(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """丢弃仅含占位提示（如「待添加」）或空事件的时间轴条目。"""
    out: List[Dict[str, Any]] = []
    for it in items:
        event = (it.get('event') or it.get('title') or '').strip()
        if not event or event in ('待添加', '未识别', '—'):
            # 仍保留带日期且有 result 的条目
            if not (it.get('date') and (it.get('result') or '').strip()):
                continue
        out.append(it)
    return out
