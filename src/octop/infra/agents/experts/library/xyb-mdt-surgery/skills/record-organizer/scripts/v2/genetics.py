"""
v2 基因检测辅助层（T4 / 针对根因 R5）

职责：
- 基因名规范化与校验（区分易混的 VEGFA/VEGFB/VEGFR 等）
- genetic_highlights 去重（按规范基因名保留信息最丰富的一条，消除 GNAS×2 重复）
- 把 TMB / MSI / MMR 等免疫标志物提升为一等展示条目

纯函数、可单测、零网络依赖。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# 实体瘤/胰腺癌常见基因白名单（用于校验与规范化，避免 VEGFR↔VEGFB 混淆被默默改写）
KNOWN_GENES = {
    'KRAS', 'NRAS', 'HRAS', 'TP53', 'SMAD4', 'CDKN2A', 'ATM', 'BRCA1', 'BRCA2',
    'PALB2', 'GNAS', 'BRD4', 'EPHB1', 'MERTK', 'VEGFA', 'VEGFB', 'VEGFC',
    'VEGFR', 'VEGFR1', 'VEGFR2', 'VEGFR3', 'GRIN2A', 'ARID1A', 'KMT2D',
    'PIK3CA', 'PTEN', 'RNF43', 'MLL3', 'MYC', 'ERBB2', 'HER2', 'MET', 'ALK',
    'ROS1', 'BRAF', 'EGFR', 'FGFR1', 'FGFR2', 'NTRK1', 'NTRK2', 'NTRK3',
    'MLH1', 'MSH2', 'MSH6', 'PMS2', 'POLE', 'STK11', 'UGT1A1', 'DPYD',
}

# 仅做「明确等价写法」的规范化，绝不把一个基因改写成另一个不同基因
_GENE_ALIASES = {
    'HER-2': 'HER2', 'HER2/NEU': 'HER2', 'C-MET': 'MET', 'C-MYC': 'MYC',
    'P53': 'TP53', 'VEGF-B': 'VEGFB', 'VEGF-A': 'VEGFA', 'VEGF-C': 'VEGFC',
}


def canonical_gene_name(name: str) -> str:
    """规范化基因名：去空白、转大写、统一连字符等价写法。不做跨基因改写。"""
    if not name:
        return ''
    s = re.sub(r'\s+', '', str(name)).upper()
    s = s.replace('（', '(').replace('）', ')')
    # 去掉尾部括号说明，如 KRAS(野生型) → KRAS
    s = re.sub(r'\(.*?\)$', '', s)
    return _GENE_ALIASES.get(s, s)


def is_known_gene(name: str) -> bool:
    return canonical_gene_name(name) in KNOWN_GENES


def _info_score(h: Dict[str, Any]) -> int:
    """对一条基因高亮信息丰富度打分，用于去重时择优保留。"""
    score = 0
    if h.get('abundance'):
        score += 3
    if h.get('evidence_tier'):
        score += 2
    if h.get('pathogenic') is True:
        score += 2
    if h.get('protein_change'):
        score += 1
    result = (h.get('result') or h.get('mutation') or '')
    score += min(len(str(result)), 40) // 10
    return score


def _merge_gene(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """合并两条同基因高亮：以信息更丰富者为主，互补缺失字段。"""
    primary, secondary = (a, b) if _info_score(a) >= _info_score(b) else (b, a)
    merged = dict(primary)
    for key in ('abundance', 'evidence_tier', 'protein_change', 'tier_label', 'result', 'mutation'):
        if not merged.get(key) and secondary.get(key):
            merged[key] = secondary[key]
    # pathogenic：任一为真则真
    if secondary.get('pathogenic') is True:
        merged['pathogenic'] = True
        merged['is_critical'] = merged.get('significance') == 'pathogenic' or merged.get('is_critical', False)
    # tags 合并去重
    tags = list(dict.fromkeys((primary.get('tags') or []) + (secondary.get('tags') or [])))
    if tags:
        merged['tags'] = tags
    return merged


def dedup_gene_highlights(highlights: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """对 category=='gene' 的条目按规范基因名去重，保留信息最丰富者。

    非 gene 条目（pgx 药敏、biomarker 等）原样保留、不参与跨类去重。
    """
    out: List[Dict[str, Any]] = []
    gene_index: Dict[str, int] = {}  # canonical gene -> index in out
    for h in highlights:
        if h.get('category') != 'gene':
            out.append(h)
            continue
        key = canonical_gene_name(h.get('gene') or h.get('marker') or '')
        if not key:
            out.append(h)
            continue
        # 规范化展示用基因名
        h = dict(h)
        h['gene'] = key
        h['marker'] = key
        if key in gene_index:
            idx = gene_index[key]
            out[idx] = _merge_gene(out[idx], h)
        else:
            gene_index[key] = len(out)
            out.append(h)
    return out


# ---------------------------------------------------------------------------
# 免疫标志物（TMB / MSI / MMR）提升为展示条目
# ---------------------------------------------------------------------------
def biomarker_rows(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """从病理/基因检测条目中提取 TMB / MSI / MMR，生成统一展示行。

    读取字段：tmb_value、msi_status，以及 report_summary/conclusion 中的 pMMR/dMMR。
    去重：同一标志物只保留一条（优先有明确取值者）。
    """
    found: Dict[str, Dict[str, Any]] = {}

    def _add(marker: str, value: str, critical: bool = False) -> None:
        value = (value or '').strip()
        if not value:
            return
        if marker in found and found[marker]['result']:
            return
        found[marker] = {
            'category': 'biomarker',
            'gene': marker,
            'marker': marker,
            'mutation': value,
            'result': value,
            'pathogenic': critical,
            'significance': 'biomarker',
            'is_critical': critical,
            'abundance': '',
            'evidence_tier': '',
            'tier_label': '免疫标志物',
            'tags': [],
        }

    for item in items or []:
        if not isinstance(item, dict):
            continue
        _add('TMB', item.get('tmb_value', ''))
        msi = (item.get('msi_status') or '').strip()
        _add('MSI', msi, critical=msi.upper() in ('MSI-H', 'MSI-HIGH'))
        # 从结论文本兜底提取 MMR 状态
        for field in ('report_summary', 'conclusion', 'clinical_summary'):
            text = item.get(field) or ''
            if not isinstance(text, str):
                continue
            m = re.search(r'\b([dp]MMR)\b', text)
            if m:
                status = m.group(1)
                _add('MMR', status, critical=status.lower() == 'dmmr')
    return list(found.values())
