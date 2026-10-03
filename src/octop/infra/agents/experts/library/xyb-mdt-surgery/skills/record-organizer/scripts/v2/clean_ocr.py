"""
v2 OCR 文本预清洗层（T2 / 针对根因 R3、R13）

职责：
- 在脱敏之前，剥离 OCR 文本中的「非临床噪声」，避免污染抽取与最终正文。
- 处理对象：云影像分享链接与安全码、微信/相册等界面文字（如「访客86718」「查看影像」）、
  ChatGPT 式对话口水（「要不要我帮你…」「好的 ✅」）、emoji 小标题、孤立页码行等。

设计原则：
- 只删「明确无临床价值」的内容，宁可漏删也不误删医疗事实。
- 纯函数、可单测、零外部依赖。
"""
from __future__ import annotations

import re
from typing import List

# ---------------------------------------------------------------------------
# 行级噪声模式：整行匹配则丢弃
# ---------------------------------------------------------------------------
_LINE_NOISE_PATTERNS: List[re.Pattern] = [
    # 云影像分享链接（含安全码的整段说明）
    re.compile(r'^\s*云影像链接为[:：].*$'),
    re.compile(r'^\s*(?:https?://)?ylyyx\.shdc\.org\.cn\S*.*$'),
    re.compile(r'^\s*安全码[:：]?\s*\d+.*$'),
    re.compile(r'^.*打开链接输入安全码查看影像.*$'),
    # 相册/访客等界面文字
    re.compile(r'^\s*访客\s*\d+\s*$'),
    re.compile(r'^\s*(?:查看影像|查看大图|保存图片|分享|转发|点赞|收藏|展开全文)\s*$'),
    # 纯页码行（OCR 常把页码单独成行，如 PDF 行号 1..45）
    re.compile(r'^\s*\d{1,3}\s*$'),
    # markdown 代码块围栏 / 「代码块」标记（OCR 噪声）
    re.compile(r'^\s*```.*$'),
    re.compile(r'^\s*代码块\s*$'),
    # 分隔线噪声
    re.compile(r'^\s*[⸻—\-_=]{2,}\s*$'),
]

# ---------------------------------------------------------------------------
# ChatGPT/对话口水：行内或整行出现即视为对话噪声
# ---------------------------------------------------------------------------
_CHATTER_PATTERNS: List[re.Pattern] = [
    re.compile(r'要不要我帮你'),
    re.compile(r'我帮你(?:整理|梳理|画|做|设计|总结)'),
    re.compile(r'^\s*好的\s*[✅👍]?'),
    re.compile(r'这样你(?:就能|可以|以后)'),
    re.compile(r'你提供的.*我帮你'),
    re.compile(r'^\s*(?:⸻|👉|🧩|🔎|📌|📝|🧪|🧬|✅|👍)\s*$'),
]

# 仅当一行「以 emoji 开头且整体是引导语气」时才剥离 emoji 前缀，
# 但保留其后的临床内容（如「📌 结论（临床提示）」要保留文字）。
_EMOJI_LEAD = re.compile(
    r'^[\s]*[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]+[\s]*'
)


def _is_pure_noise_line(line: str) -> bool:
    for pat in _LINE_NOISE_PATTERNS:
        if pat.match(line):
            return True
    return False


def _is_chatter_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    for pat in _CHATTER_PATTERNS:
        if pat.search(stripped):
            return True
    return False


def _strip_emoji_lead(line: str) -> str:
    """去掉行首引导性 emoji，保留其后正文。"""
    return _EMOJI_LEAD.sub('', line)


def clean_ocr_text(text: str) -> str:
    """清洗单份 OCR 文本，返回去噪后的文本。

    - 丢弃纯噪声行（云链接/安全码/访客/页码/围栏/分隔线）
    - 丢弃对话口水行
    - 去掉行首引导 emoji
    - 折叠连续空行
    """
    if not text:
        return text or ''

    out: List[str] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if _is_pure_noise_line(line):
            continue
        if _is_chatter_line(line):
            continue
        line = _strip_emoji_lead(line)
        out.append(line)

    # 折叠 3+ 连续空行为 1 个空行
    cleaned: List[str] = []
    blank_run = 0
    for line in out:
        if not line.strip():
            blank_run += 1
            if blank_run > 1:
                continue
        else:
            blank_run = 0
        cleaned.append(line)

    return '\n'.join(cleaned).strip() + ('\n' if text.endswith('\n') else '')


# 已知 OCR 高频错字纠正（保守：仅纠正语义明确、不会误伤的固定串）
_OCR_TYPO_FIXES = {
    '广泛移浊': '广泛转移',
}


def fix_known_ocr_typos(text: str) -> str:
    """纠正已知的、语义明确的 OCR 错字（保守白名单）。"""
    if not text:
        return text or ''
    for wrong, right in _OCR_TYPO_FIXES.items():
        text = text.replace(wrong, right)
    return text


def clean(text: str) -> str:
    """完整清洗入口：去噪 + 错字纠正。"""
    return fix_known_ocr_typos(clean_ocr_text(text))
