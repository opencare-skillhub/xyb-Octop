"""
v2 语义去重与方案聚合层（T5 / 针对根因 R6、R8）

职责：
- 影像/检验条目语义去重：同一份报告被多张近似照片 OCR 后，按 (日期, 模态/指标,
  文本相似度) 合并，保留信息最完整的一条，消除重复条目（如两条 2025-01-02 CT）。
- 用药方案聚合：从处方/病程文本中识别方案名与累计周期数（如「AG 方案 累计 38 次」）。

纯函数、可单测、零网络依赖。
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional


def _norm_txt(s: str) -> str:
    return re.sub(r'[\s，,。.；;：:、（）()【】\[\]]+', '', s or '')


def text_similarity(a: str, b: str) -> float:
    """两段文本的相似度（0~1）。去除标点空白后比较，鲁棒于 OCR 噪声。"""
    na, nb = _norm_txt(a), _norm_txt(b)
    if not na and not nb:
        return 1.0
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def _is_contained(a: str, b: str, *, min_len: int = 6) -> bool:
    """较短文本是否基本被较长文本包含（处理 OCR 截断的近似重复）。"""
    na, nb = _norm_txt(a), _norm_txt(b)
    short, long = (na, nb) if len(na) <= len(nb) else (nb, na)
    if len(short) < min_len:
        return False
    return short in long


def _findings_text(row: Dict[str, Any]) -> str:
    f = row.get('findings')
    if isinstance(f, list):
        return '；'.join(str(x) for x in f if x)
    return str(f or row.get('conclusion') or '')


def dedup_imaging(rows: List[Dict[str, Any]], *, threshold: float = 0.82) -> List[Dict[str, Any]]:
    """对影像条目按 (日期 + 文本相似度) 去重，保留 findings 更完整者。

    - 同日期且 findings 相似度 >= threshold 视为同一份报告的重复 OCR。
    - 空日期('—'/'')条目仅在文本高度相似时去重，避免误并。
    """
    kept: List[Dict[str, Any]] = []
    for row in rows:
        date = (row.get('date') or '').strip()
        ftext = _findings_text(row)
        dup_idx = -1
        for i, k in enumerate(kept):
            kdate = (k.get('date') or '').strip()
            same_date = date and kdate and date == kdate
            sim = text_similarity(ftext, _findings_text(k))
            contained = _is_contained(ftext, _findings_text(k))
            if (same_date and (sim >= threshold or contained)) or (sim >= 0.92):
                dup_idx = i
                break
        if dup_idx >= 0:
            # 保留 findings 更长（信息更全）的一条，补全缺失日期/模态
            if len(ftext) > len(_findings_text(kept[dup_idx])):
                merged = dict(row)
                if not (merged.get('date') or '').strip() and kept[dup_idx].get('date'):
                    merged['date'] = kept[dup_idx]['date']
                if not merged.get('modality') and kept[dup_idx].get('modality'):
                    merged['modality'] = kept[dup_idx]['modality']
                kept[dup_idx] = merged
        else:
            kept.append(row)
    return kept


def dedup_lab_trend_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """对单指标趋势点按 (日期, 值) 去重（保持原顺序）。"""
    seen = set()
    out: List[Dict[str, Any]] = []
    for r in rows:
        key = ((r.get('date') or '').strip(), str(r.get('value', '')).strip())
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


# ---------------------------------------------------------------------------
# 用药方案聚合
# ---------------------------------------------------------------------------
# 累计周期数：捕获「AG方案 累计38次」「目前 34 次 AG 化疗」「第 38 周期」等
_CYCLE_PATTERNS = [
    re.compile(r'累计\s*(?:第)?\s*(\d{1,3})\s*次'),
    re.compile(r'(\d{1,3})\s*次\s*[A-Za-z]{0,4}\s*化疗'),
    re.compile(r'第\s*(\d{1,3})\s*(?:周期|疗程|次)'),
    re.compile(r'(?:目前|现)\s*(\d{1,3})\s*次'),
    re.compile(r'(\d{1,3})\s*周期'),
]

# 常见方案名
_REGIMEN_NAMES = ['AG', 'FOLFIRINOX', 'FOLFOX', 'FOLFIRI', 'GS', 'GEMOX', 'mFOLFIRINOX', 'NALIRI']


def extract_regimen_cycles(text: str) -> Optional[Dict[str, Any]]:
    """从一段文本中提取方案名与最大累计周期数。无则返回 None。"""
    if not text:
        return None
    cycles: List[int] = []
    for pat in _CYCLE_PATTERNS:
        for m in pat.finditer(text):
            try:
                cycles.append(int(m.group(1)))
            except (ValueError, TypeError):
                continue
    regimen = ''
    upper = text.upper()
    for name in _REGIMEN_NAMES:
        if re.search(r'\b' + re.escape(name) + r'\b', upper) or (name + '方案') in text or (name + '化疗') in text:
            regimen = name
            break
    if not cycles and not regimen:
        return None
    return {'regimen': regimen, 'cycles': max(cycles) if cycles else None}


def summarize_regimen(texts: List[str]) -> str:
    """汇总多段文本，输出方案摘要串，如「AG方案 · 累计38次」。无则空串。"""
    best_regimen = ''
    best_cycles: Optional[int] = None
    for t in texts:
        info = extract_regimen_cycles(t or '')
        if not info:
            continue
        if info.get('regimen') and not best_regimen:
            best_regimen = info['regimen']
        c = info.get('cycles')
        if c is not None and (best_cycles is None or c > best_cycles):
            best_cycles = c
    if not best_regimen and best_cycles is None:
        return ''
    parts = []
    if best_regimen:
        parts.append(f'{best_regimen}方案')
    if best_cycles is not None:
        parts.append(f'累计{best_cycles}次')
    return ' · '.join(parts)
