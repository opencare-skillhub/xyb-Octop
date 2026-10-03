# xyb-news · 看进展

胰腺癌研究进展检索插件（Octop `kind=tool`）。

> 从 PI-Desktop 的 `xyb.news` 插件移植：`apps/desktop/resources/plugins/xyb.news/`
> 原实现为 Electron 侧的 CommonJS（`pi.net.fetch` + `pi.commands.register`），
> 本插件将其业务逻辑重写为 Python / Octop 工具。

## 职责与边界

- 汇集胰腺癌相关的药物与研究进展条目（PubMed），只列**标题、来源、时间与原文链接**。
- 不生成疗效结论、不推荐用药；条目一律可点回原文。

## 工具

| 工具 | 参数 | 说明 |
|------|------|------|
| `xyb_news_progress` | `days`（默认 30）<br>`limit`（默认 20）<br>`query`（可选，覆盖默认检索式） | 检索最近 N 天的文献，返回格式化清单 |

默认检索式：

```
(pancreatic cancer[Title/Abstract])
AND (KRAS[Title/Abstract] OR ADC[Title/Abstract] OR immunotherapy[Title/Abstract])
```

数据源：NCBI E-utilities（`esearch.fcgi` → `esummary.fcgi`），无需 API Key。

## 安装

```bash
octop plugin install ./plugins/xyb-news --force
```

安装后需在 `config.json` 中全局启用（`plugins.xyb-news.enabled = true`），
并重启 `octop run` 或调用 `POST /api/plugins/reload`。

工具默认对 Agent 启用；可在 **Dashboard → 工具管理** 按 Agent 关闭。

## 校验

```bash
uv run python - <<'PY'
from pathlib import Path
from octop_harness.plugins import PluginRegistry, load_plugin_dir

PluginRegistry.reset()
p = load_plugin_dir(Path("plugins/xyb-news"), install_deps=False)
print(p.manifest.id, p.manifest.kind, [t.name for t in p.tools])
PY
```

期望输出：`xyb-news tool ['xyb_news_progress']`
