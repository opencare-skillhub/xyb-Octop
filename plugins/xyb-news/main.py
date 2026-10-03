"""
小胰宝 · 看进展（xyb-news）— Octop tool 插件

从 PI-Desktop 的 xyb.news 插件移植而来。

职责：汇集胰腺癌相关的药物/研究进展条目，只列标题、来源、时间与原文链接。
边界：不生成疗效结论、不推荐用药，条目一律可点回原文。
"""

from __future__ import annotations

from datetime import date, timedelta

import httpx
from octop_harness.plugins import PluginContext

_DISCLAIMER = "以下为公开文献与试验信息的标题整理，供参考，不构成医疗建议，也不代表疗效结论。"

_PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_PUBMED_ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

# 默认检索式：胰腺癌相关的 KRAS / ADC / 免疫治疗
_DEFAULT_QUERY = (
    "(pancreatic cancer[Title/Abstract]) "
    "AND (KRAS[Title/Abstract] OR ADC[Title/Abstract] "
    "OR immunotherapy[Title/Abstract])"
)

_TIMEOUT_S = 20


def _days_ago_iso(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


async def fetch_progress(
    days: int = 30,
    limit: int = 20,
    query: str | None = None,
) -> str:
    """检索胰腺癌相关研究进展（PubMed）"""
    q = query or _DEFAULT_QUERY
    mindate = _days_ago_iso(days)
    maxdate = _days_ago_iso(0)

    async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
        # 第一步：ESearch — 获取匹配的 PubMed ID
        search_params = {
            "db": "pubmed",
            "term": q,
            "retmode": "json",
            "retmax": str(limit),
            "sort": "date",
            "datetype": "pdat",
            "mindate": mindate,
            "maxdate": maxdate,
        }
        search_resp = await client.get(_PUBMED_ESEARCH, params=search_params)
        search_resp.raise_for_status()
        search_data = search_resp.json()

        esearch_result = search_data.get("esearchresult") or {}
        ids = esearch_result.get("idlist") or []
        if not ids:
            return f"未找到最近 {days} 天的相关文献。\n\n---\n{_DISCLAIMER}"

        # 第二步：ESummary — 获取标题、来源、日期
        summary_params = {
            "db": "pubmed",
            "id": ",".join(ids),
            "retmode": "json",
        }
        summary_resp = await client.get(_PUBMED_ESUMMARY, params=summary_params)
        summary_resp.raise_for_status()
        summary_data = summary_resp.json()

    result_map = summary_data.get("result") or {}
    items: list[dict[str, str]] = []
    for pid in ids:
        rec = result_map.get(pid)
        if not rec:
            continue
        items.append(
            {
                "id": pid,
                "title": rec.get("title", ""),
                "source": rec.get("fulljournalname") or rec.get("source", ""),
                "date": rec.get("pubdate", ""),
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pid}/",
            }
        )

    if not items:
        return f"检索到 {len(ids)} 条结果，但无法获取详情。\n\n---\n{_DISCLAIMER}"

    # 格式化为易读文本
    lines: list[str] = [
        f"📖 胰腺癌研究进展（最近 {days} 天）",
        f"共 {len(items)} 篇\n",
    ]
    for i, item in enumerate(items, 1):
        lines.append(
            f"{i}. {item['title']}\n"
            f"   来源：{item['source']}　日期：{item['date']}\n"
            f"   链接：{item['url']}\n"
        )
    lines.append(f"---\n{_DISCLAIMER}")
    return "\n".join(lines)


def setup(ctx: PluginContext) -> None:
    ctx.tool(
        "xyb_news_progress",
        fetch_progress,
        description=(
            "检索胰腺癌相关的药物与研究进展（PubMed 文献库），"
            "返回标题、来源、时间与原文链接。"
            "支持自定义检索天数和关键词。"
            "仅返回公开摘要信息，不构成医疗建议。"
        ),
    )
