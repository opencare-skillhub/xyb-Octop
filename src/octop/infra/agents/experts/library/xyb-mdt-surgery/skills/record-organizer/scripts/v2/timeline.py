"""
v2 诊疗事件时间轴层（T6 / 针对根因 R9、R10）

问题：渲染层用「文件名」当时间轴标题，治疗叙事（PET-CT、活检、疗效评估 PR/SD/PD、
方案启停）几乎全部丢失。

方案：在 LLM 抽取的 timeline_items 之上，再用规则从临床文本派生关键事件
（疗效评估、手术/活检/穿刺等），合并、去重、按日期排序，产出干净的事件时间轴。
每个条目使用「事件描述」而非文件名。

纯函数、可单测、零网络依赖。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from scripts.v2.shuffle_group import _normalize_date

# 日期片段（紧凑 8 位 / 连字符 / 中文）
_DATE_FRAG = r'(\d{8}|\d{4}[-./]\d{1,2}[-./]\d{1,2}|\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*[日号])'

# 疗效评估：20230908疗效评估PR / 2024.01.02评估SD / 2023-09-08 疗效评估：PR
_RESPONSE_RE = re.compile(_DATE_FRAG + r'[^\n。]{0,8}?(?:疗效评估|评估|疗效)\s*[:：]?\s*(CR|PR|SD|PD)')

# 手术/活检/穿刺等操作
_PROC_KEYWORDS = ['腹腔镜探查', '大网膜活检', '活检术', '活检', '切除术', '胰十二指肠切除',
                  'Whipple', 'PTCD', '穿刺', '探查术', '根治术']
_PROC_RE = re.compile(
    _DATE_FRAG + r'[^\n。]{0,40}?(' + '|'.join(map(re.escape, _PROC_KEYWORDS)) + r')[^\n。]{0,20}'
)

_RESPONSE_LABEL = {
    'CR': '完全缓解 (CR)', 'PR': '部分缓解 (PR)',
    'SD': '疾病稳定 (SD)', 'PD': '疾病进展 (PD)',
}
_RESPONSE_ALERT = {'PD'}  # 进展标红


def extract_response_events(text: str) -> List[Dict[str, Any]]:
    """从文本中提取疗效评估事件（PR/SD/PD/CR）。"""
    out: List[Dict[str, Any]] = []
    for m in _RESPONSE_RE.finditer(text or ''):
        date = _normalize_date(m.group(1))
        assess = m.group(2).upper()
        out.append({
            'date': date,
            'event': f'疗效评估：{_RESPONSE_LABEL.get(assess, assess)}',
            'result': '',
            'hospital': '',
            'severity': '严重' if assess in _RESPONSE_ALERT else '',
            'category': 'response',
        })
    return out


def extract_procedures(text: str) -> List[Dict[str, Any]]:
    """从文本中提取手术/活检/穿刺等操作事件。"""
    out: List[Dict[str, Any]] = []
    for m in _PROC_RE.finditer(text or ''):
        date = _normalize_date(m.group(1))
        snippet = m.group(0)
        # 去掉开头日期，保留操作描述
        desc = snippet[len(m.group(1)):].strip(' ：:，,。')
        out.append({
            'date': date,
            'event': desc[:40] if desc else m.group(2),
            'result': '',
            'hospital': '',
            'severity': '',
            'category': 'procedure',
        })
    return out


def _normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    d = item.get('date') or ''
    return {
        'date': _normalize_date(d) if d else '',
        'event': (item.get('event') or '').strip(),
        'result': (item.get('result') or '').strip(),
        'hospital': (item.get('hospital') or '').strip(),
        'severity': (item.get('severity') or '').strip(),
        'category': item.get('category', 'clinical'),
    }


# ---------------------------------------------------------------------------
# 语义签名与去重（解决「同一事件多源不同措辞」造成的大量重复）
# ---------------------------------------------------------------------------
# 化疗周期：AG方案C1D1 / AG方案C1D1化疗 / AG方案化疗C1D1 / AG方案化疗C1D1开始
_CHEMO_RE = re.compile(r'([A-Za-z]{1,10})?\s*方案[^CcＣ]*?[CcＣ](\d{1,2})\s*[DdＤ](\d{1,2})')
_CD_ONLY_RE = re.compile(r'[CcＣ](\d{1,2})\s*[DdＤ](\d{1,2})')
_RESP_CODE_RE = re.compile(r'(?<![A-Za-z])(CR|PR|SD|PD)(?![A-Za-z])')
_PUNCT_RE = re.compile(r'[\s，,。.；;：:、（）()【】\[\]“”"\'’!！?？\-—_]+')


def _norm_text(s: str) -> str:
    return _PUNCT_RE.sub('', (s or '')).lower()


def _chemo_info(event: str):
    """从事件文本解析化疗周期信息，返回 (regimen, cycle, day) 或 None。"""
    e = event or ''
    if '化疗' not in e and '方案' not in e and not _CD_ONLY_RE.search(e):
        return None
    m = _CHEMO_RE.search(e)
    if m:
        reg = (m.group(1) or '').upper() or '化疗'
        return reg, int(m.group(2)), int(m.group(3))
    m2 = _CD_ONLY_RE.search(e)
    if m2 and ('化疗' in e or '方案' in e):
        return '化疗', int(m2.group(1)), int(m2.group(2))
    return None


# 含「化疗」但无实质临床细节的笼统事件（后续化疗/化疗具体周期不详等）→ 并入化疗主题
_NON_CHEMO_CTX = ('门诊', '复查', '评估', '病理', '检验', '影像', '就诊', '主诉',
                  '处方', '置管', '输液', '活检', '手术', '检查', '咨询', '随访',
                  'DSA', '分子检测', '复诊', '入院', '出院')


def _is_vague_chemo(event: str) -> bool:
    e = event or ''
    if _chemo_info(e):
        return True
    if '化疗' not in e:
        return False
    return not any(k in e for k in _NON_CHEMO_CTX)


def _event_signature(event: str) -> str:
    """事件语义签名：同义不同措辞归一到同一签名，用于去重。"""
    e = event or ''
    info = _chemo_info(e)
    if info:
        return f'chemo|{info[0]}|C{info[1]}|D{info[2]}'
    if '疗效' in e or '评估' in e:
        m = _RESP_CODE_RE.search(e)
        if m:
            return f'response|{m.group(1).upper()}'
    return 'text|' + _norm_text(e)


def _richness(it: Dict[str, Any]) -> int:
    return len(it.get('event', '') or '') + len(it.get('result', '') or '') + (10 if it.get('hospital') else 0)


def _lcs_len(a: str, b: str) -> int:
    """最长公共子串长度（用于同日「换种说法」的近似事件归并）。"""
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    best = 0
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        ai = a[i - 1]
        for j in range(1, len(b) + 1):
            if ai == b[j - 1]:
                cur[j] = prev[j - 1] + 1
                if cur[j] > best:
                    best = cur[j]
        prev = cur
    return best


def _dedup_events(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按 (date, 语义签名) 去重，保留信息更丰富者；同日叙事性事件做模糊去重。"""
    from difflib import SequenceMatcher

    best: Dict[tuple, Dict[str, Any]] = {}
    order: List[tuple] = []
    for it in items:
        key = (it.get('date', ''), _event_signature(it.get('event', '')))
        if key not in best:
            best[key] = it
            order.append(key)
        elif _richness(it) > _richness(best[key]):
            best[key] = it
    deduped = [best[k] for k in order]

    # 同日「叙事性」事件模糊去重：保留信息最全的一条，丢弃高度相似/被包含的其余条
    by_date: Dict[str, List[Dict[str, Any]]] = {}
    for it in deduped:
        by_date.setdefault(it.get('date', ''), []).append(it)
    drop_ids = set()
    for group in by_date.values():
        narr = [it for it in group if _event_signature(it.get('event', '')).startswith('text|')]
        narr.sort(key=_richness, reverse=True)  # 富信息优先保留
        kept: List[str] = []
        for it in narr:
            nt = _norm_text(it.get('event', ''))
            if not nt:
                continue
            is_dup = False
            for kt in kept:
                if (nt in kt or kt in nt
                        or SequenceMatcher(None, nt, kt).ratio() >= 0.6
                        or _lcs_len(nt, kt) >= 8):  # 同日「换种说法」的近似事件归并（保守）
                    is_dup = True
                    break
            if is_dup:
                drop_ids.add(id(it))
            else:
                kept.append(nt)
    return [it for it in deduped if id(it) not in drop_ids]


def _collapse_chemo_cycles(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """把重复的化疗事件（含周期 CxDy 与笼统化疗）合并成「方案主题」摘要，不再逐条铺开。"""
    chemo = [it for it in items if _chemo_info(it.get('event', '')) or _is_vague_chemo(it.get('event', ''))]
    if len(chemo) <= 2:
        return items
    chemo_ids = {id(it) for it in chemo}
    others = [it for it in items if id(it) not in chemo_ids]

    cycle_items = [it for it in chemo if _chemo_info(it.get('event', ''))]
    regimens = {_chemo_info(it['event'])[0] for it in cycle_items if _chemo_info(it['event'])[0] != '化疗'}
    main_reg = next(iter(regimens)) if len(regimens) == 1 else None

    dates = sorted(it.get('date', '') for it in chemo if it.get('date'))
    cycles = sorted({_chemo_info(it['event'])[1] for it in cycle_items}) if cycle_items else []

    span = f'（{dates[0]} ~ {dates[-1]}）' if dates else ''
    if cycles:
        cycle_desc = f'C{cycles[0]}–C{cycles[-1]}，共{len(cycles)}个周期' if len(cycles) > 1 else f'C{cycles[0]}'
    else:
        cycle_desc = f'共 {len(chemo)} 次记录'
    summary = {
        'date': dates[0] if dates else '',
        'event': f'{main_reg}方案化疗' if main_reg else '化疗',
        'result': f'{cycle_desc}{span}',
        'hospital': '',
        'severity': '',
        'category': 'medication',
    }
    return others + [summary]


def build_timeline_items(
    llm_items: List[Dict[str, Any]],
    texts: List[str],
    *,
    cutoff: str = '2026-12-31',
) -> List[Dict[str, Any]]:
    """合并 LLM 抽取条目与规则派生事件，强力去重并按日期排序。

    - 语义去重：化疗周期(CxDy)、疗效评估(PR/SD/PD)按语义签名归一；叙事事件包含去重
    - 化疗周期折叠：大量重复的给药周期合并成「一个方案主题」摘要
    - 规则派生事件仅作兜底：LLM 已提供较完整时间轴(>=3 条)时不再叠加正则，避免重复
    - 标题一律使用事件描述，绝不使用文件名
    """
    merged: List[Dict[str, Any]] = []
    for it in (llm_items or []):
        if isinstance(it, dict) and (it.get('event') or it.get('date')):
            merged.append(_normalize_item(it))

    # 规则派生事件仅在 LLM 时间轴稀疏时兜底，避免与 LLM 条目重复
    if sum(1 for it in merged if it.get('event')) < 3:
        for t in (texts or []):
            merged.extend(extract_response_events(t))
            merged.extend(extract_procedures(t))

    # 过滤空事件与超出 cutoff 的条目
    cleaned: List[Dict[str, Any]] = []
    for it in merged:
        if not it.get('event') and not it.get('date'):
            continue
        date = it.get('date', '')
        if date and date > cutoff:
            continue
        cleaned.append(it)

    deduped = _dedup_events(cleaned)
    collapsed = _collapse_chemo_cycles(deduped)
    collapsed.sort(key=lambda x: (not x.get('date'), x.get('date') or ''))
    return collapsed
