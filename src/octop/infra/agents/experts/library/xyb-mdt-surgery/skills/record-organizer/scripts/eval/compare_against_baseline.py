"""
事实级一致性对比工具（T10 / 落地「100% 一致」的可操作定义）

把生成的 HTML 报告与「金标准事实清单」(doc/baseline-facts.json) 逐项核对，
输出 命中/缺失/违禁(多余噪声) 统计与一致率分数。

通过标准：缺失=0 且 违禁=0。

用法：
    python -m scripts.eval.compare_against_baseline output/report.html
    python -m scripts.eval.compare_against_baseline output/report.html --facts doc/baseline-facts.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_FACTS = _PROJECT_ROOT / 'doc' / 'baseline-facts.json'


def html_to_text(html: str) -> str:
    """去掉 style/script 与标签，返回可见文本。"""
    html = re.sub(r'<style.*?</style>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<script.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', html)
    # 还原常见实体
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    return re.sub(r'\s+', ' ', text)


def load_facts(path: str | Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding='utf-8'))


def compare(text: str, facts: Dict[str, Any]) -> Dict[str, Any]:
    """核对文本与事实清单，返回结构化结果。"""
    must_appear: Dict[str, List[str]] = facts.get('must_appear', {})
    must_not: List[str] = facts.get('must_not_appear', [])

    categories: Dict[str, Dict[str, List[str]]] = {}
    total = 0
    hit = 0
    for cat, tokens in must_appear.items():
        present, missing = [], []
        for tok in tokens:
            total += 1
            if tok in text:
                present.append(tok)
                hit += 1
            else:
                missing.append(tok)
        categories[cat] = {'present': present, 'missing': missing}

    forbidden_present = [tok for tok in must_not if tok in text]

    missing_total = total - hit
    passed = missing_total == 0 and not forbidden_present
    score = round(hit / total, 4) if total else 1.0

    return {
        'passed': passed,
        'score': score,
        'total_facts': total,
        'hit': hit,
        'missing': missing_total,
        'forbidden_present': forbidden_present,
        'categories': categories,
    }


def format_report(result: Dict[str, Any]) -> str:
    lines: List[str] = []
    status = '✅ 通过' if result['passed'] else '❌ 未通过'
    lines.append(f'事实级一致性：{status}  (命中 {result["hit"]}/{result["total_facts"]}，一致率 {result["score"]*100:.1f}%)')
    lines.append('')
    for cat, data in result['categories'].items():
        miss = data['missing']
        mark = '✅' if not miss else '⚠️'
        lines.append(f'{mark} {cat}: 命中 {len(data["present"])}/{len(data["present"]) + len(miss)}')
        if miss:
            lines.append(f'    缺失: {", ".join(miss)}')
    if result['forbidden_present']:
        lines.append('')
        lines.append(f'❌ 出现违禁内容(噪声/占位符/伪造日期): {", ".join(result["forbidden_present"])}')
    return '\n'.join(lines)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='生成报告与基准事实清单的事实级对比')
    parser.add_argument('html', help='生成的 HTML 报告路径')
    parser.add_argument('--facts', default=str(_DEFAULT_FACTS), help='金标准事实清单 JSON')
    parser.add_argument('--json', action='store_true', help='以 JSON 输出结果')
    args = parser.parse_args(argv)

    html_path = Path(args.html)
    if not html_path.exists():
        print(f'❌ HTML 不存在: {html_path}')
        return 2

    text = html_to_text(html_path.read_text(encoding='utf-8'))
    facts = load_facts(args.facts)
    result = compare(text, facts)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_report(result))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
