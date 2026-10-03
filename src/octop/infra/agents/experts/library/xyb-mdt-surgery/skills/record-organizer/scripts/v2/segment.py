"""
v2 复合文档切分层（T1 / 针对根因 R1、R2）

问题：一个输入文件 → 一个 .md → 一次 Map → 一个 report_type。
像「01 病情概述.pdf」这类同时包含 检验/基因/病理/影像/用药 的复合文档，
会被整篇坍缩成单一 clinical_records，内部结构全部丢失。

方案：把一篇 OCR 文本按「章节标题 + 内容类型」切成多个逻辑子文档，
每段独立分类与抽取。一份复合 PDF 因此能同时贡献多类记录。

设计原则：
- 只对「确属复合」的长文档切分；短文档/单一类型原样透传，避免过度切分与额外成本。
- 纯函数、可单测、零网络依赖；分类复用 map_extract 的关键词规则，保持一致。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# 复用 Map 层关键词规则，保证「段落分类」与「文件分类」口径一致
from scripts.v2 import map_extract as _me

try:
    _KEYWORD_RULES = list(_me._KEYWORD_TYPE_RULES)
except Exception:  # pragma: no cover - 防御 map_extract 结构变化
    _KEYWORD_RULES = []


# ---------------------------------------------------------------------------
# 边界识别：哪些行标志「新章节开始」
# ---------------------------------------------------------------------------
# 编号小节标题：如 "1.1 基因检测"、"4. 药物毒性提示"、"5. 现治疗方案"、"6. 影像"
_NUM_HEADING = re.compile(r'^\s*\d+(?:\.\d+){0,2}[\.、\s]\s*\S')
# Markdown 标题
_MD_HEADING = re.compile(r'^\s{0,3}#{1,6}\s+\S')
# 已知章节标题词（出现在行首/独立短行时作为边界）
_SECTION_TITLE_WORDS = [
    '基因检测', '病理组化', '病理诊断', '免疫组化', '影像报告', '影像检查',
    '现治疗方案', '药物毒性', '处方', '医嘱', '肿瘤标志物', '检验报告',
    '出院小结', '门诊记录', '住院记录', '治疗概述', '简要病史', '基本信息',
]
_SECTION_TITLE = re.compile(
    r'^\s*(?:[•◦\-*]\s*)?(?:' + '|'.join(map(re.escape, _SECTION_TITLE_WORDS)) + r')'
)


def _is_boundary(line: str) -> bool:
    """该行是否标志一个新章节的开始。"""
    if _MD_HEADING.match(line):
        return True
    if _NUM_HEADING.match(line) and len(line.strip()) <= 40:
        return True
    if _SECTION_TITLE.match(line) and len(line.strip()) <= 30:
        return True
    return False


# ---------------------------------------------------------------------------
# 基因检测报告专项（Task: 基因报告按主题分段，便于结构化；不清洗）
# ---------------------------------------------------------------------------
# 判定是否基因检测报告的强信号词
_GENE_REPORT_SIGNALS = [
    '基因检测', '检测基因', '测序', 'NGS', '变异', '丰度', '胚系', '体细胞',
    'TMB', 'MSI', 'HRR', 'panel', '突变', '碱基', '外显子',
]
# 基因报告内部章节主题词
_GENE_SECTION_WORDS = [
    '样本信息', '标本信息', '送检信息', '受检者信息', '检测项目', '检测范围',
    '检测结论', '检测结果', '结果概述', '结果摘要', '重要提示',
    '基因变异', '变异列表', '变异详情', '变异结果', '体细胞变异', '体细胞突变',
    '胚系变异', '胚系突变', '遗传性', '遗传风险',
    '临床意义', '用药提示', '用药指导', '用药建议', '靶向用药', '化疗用药', '免疫用药',
    '药物敏感', '药物代谢', 'HRR基因', '遗传咨询',
    '质控', '质量控制', '检测方法', '方法学', '检测说明', '测序深度',
    '局限性', '参考文献', '附录', '基因列表',
]
_GENE_SECTION = re.compile(
    r'^\s*(?:\d+(?:\.\d+)*[\.、\s]\s*)?(?:[•◦\-*]\s*)?(?:'
    + '|'.join(map(re.escape, _GENE_SECTION_WORDS)) + r')'
)


def is_genetic_report(text: str, *, min_signals: int = 3) -> bool:
    """是否为肿瘤基因检测报告（需多个强信号词，避免误判普通病理报告）。"""
    if not text:
        return False
    return sum(1 for s in _GENE_REPORT_SIGNALS if s in text) >= min_signals


def _is_gene_boundary(line: str) -> bool:
    """基因报告专用边界：通用边界 + 基因报告章节主题词。"""
    if _is_boundary(line):
        return True
    if _GENE_SECTION.match(line) and len(line.strip()) <= 24:
        return True
    return False


# ---------------------------------------------------------------------------
# 段落分类（复用 Map 关键词规则，最长关键词胜出）
# ---------------------------------------------------------------------------
def classify_segment(text: str) -> str:
    """对一个文本块分类，返回 report_type 枚举；无强信号则 'noise'。"""
    if not text or not text.strip():
        return 'noise'
    lower = text.lower()
    best_type = 'noise'
    best_len = 0
    for report_type, keyword in _KEYWORD_RULES:
        kw = keyword.lower()
        if kw in lower and len(keyword) > best_len:
            best_len = len(keyword)
            best_type = report_type
    return best_type


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------
@dataclass
class Segment:
    text: str
    type_hint: str
    title: str = ''
    index: int = 0


# ---------------------------------------------------------------------------
# 切分逻辑
# ---------------------------------------------------------------------------
def _split_into_blocks(text: str, boundary_fn=_is_boundary) -> List[str]:
    """按边界行把文本切成原始块（保留每块首行作为小标题）。"""
    lines = text.splitlines()
    blocks: List[List[str]] = []
    current: List[str] = []
    for line in lines:
        if boundary_fn(line) and current and any(l.strip() for l in current):
            blocks.append(current)
            current = [line]
        else:
            current.append(line)
    if current and any(l.strip() for l in current):
        blocks.append(current)
    return ['\n'.join(b).strip() for b in blocks if '\n'.join(b).strip()]


def _merge_adjacent_same_type(blocks: List[str]) -> List[Segment]:
    """对相邻同类型块做合并，减少碎片。"""
    segs: List[Segment] = []
    for block in blocks:
        t = classify_segment(block)
        title = block.splitlines()[0].strip()[:40] if block.splitlines() else ''
        if segs and segs[-1].type_hint == t and t != 'noise':
            segs[-1].text += '\n\n' + block
        elif segs and t == 'noise':
            # noise 块并入上一段，避免丢内容（如解读性文字）
            segs[-1].text += '\n\n' + block
        else:
            segs.append(Segment(text=block, type_hint=t, title=title))
    return segs


def is_composite(text: str, *, min_len: int = 300) -> bool:
    """判断文本是否「复合」：足够长且含 >=2 种不同的强类型信号。"""
    if not text or len(text) < min_len:
        return False
    blocks = _split_into_blocks(text)
    types = {classify_segment(b) for b in blocks}
    types.discard('noise')
    return len(types) >= 2


def segment_genetic_report(text: str, filename: str = '', *, min_len: int = 150) -> List[Segment]:
    """基因检测报告按主题分段（即使全篇同为 pathology 类型也分段）。

    每段类型统一标注为 pathology（基因检测归 pathology），由 Map 层按基因报告
    专项指引分别抽取，便于结构化。不做 OCR 清洗（基因报告无对话噪声且数值密集）。
    """
    if not text or len(text) < min_len:
        return [Segment(text=text, type_hint='pathology', title=filename, index=0)]
    blocks = _split_into_blocks(text, _is_gene_boundary)
    if len(blocks) <= 1:
        return [Segment(text=text, type_hint='pathology', title=filename, index=0)]
    out: List[Segment] = []
    for block in blocks:
        title = block.splitlines()[0].strip()[:40] if block.splitlines() else ''
        out.append(Segment(text=block, type_hint='pathology', title=title, index=len(out)))
    return out


def segment_document(text: str, filename: str = '') -> List[Segment]:
    """把一篇 OCR 文本切成带类型提示的子文档。

    - 复合文档（含多种强类型，如完整病情概述）：按章节/类型分段。
    - 纯基因检测报告（单一 pathology 类型）：按基因报告主题分段。
    - 其他：原样返回单段。
    """
    # 复合文档优先（病情概述等含多类内容的，走通用复合分段保留多类型）
    if is_composite(text):
        blocks = _split_into_blocks(text)
        segs = _merge_adjacent_same_type(blocks)
        out: List[Segment] = []
        for s in segs:
            if s.text.strip():
                s.index = len(out)
                out.append(s)
        return out or [Segment(text=text, type_hint=classify_segment(text), title=filename, index=0)]

    # 纯基因检测报告：按主题分段（即使全篇同为 pathology）
    if is_genetic_report(text):
        return segment_genetic_report(text, filename)

    return [Segment(text=text, type_hint=classify_segment(text), title=filename, index=0)]


# ---------------------------------------------------------------------------
# 目录级切分（流水线接入）
# ---------------------------------------------------------------------------
def segment_directory(in_dir: str, out_dir: str) -> Dict[str, int]:
    """把 in_dir 下每个 .md 切分后写入 out_dir。

    - 单段文档：保留原文件名（不影响缓存与「文件名取日期」逻辑）。
    - 多段文档：写成 `{stem}__s{NN}{suffix}.md`，stem 保留原始名（含日期）。
      suffix 用类型提示便于追踪。
    返回 {原文件名: 段数}。
    """
    in_path = Path(in_dir)
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    counts: Dict[str, int] = {}

    for md in sorted(in_path.glob('*.md')):
        text = md.read_text(encoding='utf-8')
        segs = segment_document(text, md.name)
        if len(segs) <= 1:
            if out_path.resolve() != in_path.resolve():
                (out_path / md.name).write_text(text, encoding='utf-8')
            counts[md.name] = 1
            continue
        for s in segs:
            type_tag = s.type_hint if s.type_hint and s.type_hint != 'noise' else 'misc'
            seg_name = f'{md.stem}__s{s.index:02d}_{type_tag}.md'
            (out_path / seg_name).write_text(s.text, encoding='utf-8')
        # 原地切分时删除整篇原文件，避免被重复抽取
        if out_path.resolve() == in_path.resolve():
            try:
                md.unlink()
            except OSError:
                pass
        counts[md.name] = len(segs)
    return counts
