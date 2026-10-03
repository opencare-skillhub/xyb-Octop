---
name: chinadrugs-collect
description: 当需要检索**中国药物临床试验登记与信息公示平台**（chinadrugtrials.org.cn）的登记记录时使用。该通道不是 MCP：它由本技能用**你本人的浏览器会话**驱动，记录落本机。未配置会话时明确告知不可用，**不绕过、不猜测结果**。Use for the China drug trial registry via your own browser session.
metadata:
  octop:
    emoji: "🇨🇳"
    label:
      zh: "中国药物临床试验登记平台"
      en: "China Drug Trial Registry"
    summary:
      zh: "用本人浏览器会话检索中国药物临床试验登记平台；记录落本机。"
      en: "Search the China drug trial registry with your own browser session."
source_repo: opencare-skillhub/chinadurgtrials
source_license: NONE
adapted: 2026-10-02
readiness: 需配置（需要患者本人的浏览器会话 Cookie；未配置时只给获取步骤）
---
> ## 通道定位与凭据（优先级高于本文其余内容）
>
> - 中国药物临床试验登记与信息公示平台这一通道**不是 MCP 服务**，由本技能用**你本人的浏览器会话**检索；这与另外三个 MCP 通道的实现方式不同。
> - 会话 Cookie 只落在你本机（`~/.xyb-chinadrugtrials/config.json`，权限 0600），不进仓库、不回显、不进日志。
> - **未配置会话时，如实说这一通道本次不可用**，不要把它说成「没有相关试验」（见 `trial-search` 技能的故障四态）。
> - 不绕过站点的任何验证或访问控制。


# 中国药物临床试验登记信息采集

## 概述

从中国药物临床试验登记与信息公示平台采集有权访问的临床试验登记信息。使用本技能可进行关键词和高级条件检索、自动分页、详情页归档、网页下载表单模拟、RAG JSON 构建、离线 JSON 回建及按正文哈希的增量同步。

仅采集有权访问的数据。遵守目标平台使用规则，控制请求频率，并仅使用调用方有权使用的 Cookie。不得尝试绕过访问控制、验证码或反爬机制。

## 资源

- `scripts/scraper.py`：命令行主抓取器。
- `scripts/main.py`：交互式菜单入口。
- `scripts/cookie_tools.py`：从浏览器 cURL 或 HTTP 响应头提取、合并 Cookie。
- `scripts/session_bootstrap.py`：启动本 Skill 专用 Chromium Profile，导出并验证目标站点 Cookie，保存本地 cURL；不读取日常浏览器 Profile，也不绕过人工验证。
- `scripts/build_json_from_raw.py`：不访问网络，从 `raw/` HTML 回建 RAG JSON。
- `scripts/verify_output.py`：逐个核对最近一次成功登记号是否具有 raw HTML、RAG JSON、原始 DOC、原始响应留档和可选 DOCX。
- `scripts/config.example.json`：无凭证的配置模板。
- `scripts/requirements.txt`：Python 依赖。
- `references/platform-workflow.md`：平台端点、页面结构、产物与排查参考。

## 执行前检查

1. 确认请求目标、关键词、高级条件、输出路径和运行模式（全量或增量）。
2. 要求提供本人浏览器中已验证会话的 Cookie，或让调用方粘贴浏览器“复制为 cURL”的完整请求；不得将 Cookie 写入版本库、日志或最终摘要。
3. 在独立工作目录中安装依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r scripts/requirements.txt
python3 -m playwright install chromium
cp scripts/config.example.json config.json
```

4. 将 Cookie 保存在本地 `config.json` 的 `cookies` 字段；将该文件加入 `.gitignore`。

## 工作流选择

| 目标 | 推荐操作 |
|---|---|
| 首次获取某一检索结果的全部记录 | 全量同步 |
| 每日检查新增或内容变化 | 增量同步 |
| 已有详情 raw HTML，需要生成或调整 JSON | 离线回建 JSON |
| Cookie 过期或缺失 | 运行 `session_bootstrap.py` 刷新专用浏览器会话；仅在网站要求时完成正常人工确认 |
| 中途终止且只想补齐缺失详情 | 非增量模式配合 `--resume` |

## 更新 Cookie

优先使用专用浏览器会话刷新：

```bash
python3 scripts/session_bootstrap.py --config config.json --keywords "胰腺癌" --state "招募中"
```

启动的 Chromium Profile 保存在当前 Skill 目录 `.browser-profile/`，只用于该平台，不读取用户日常 Chrome Profile。程序会导出目标域 Cookie，并用一次只读搜索请求验证会话；验证成功后将 Cookie 保存到本地 `config.json`，同时在 `.session/latest-search.curl` 保存可复现 cURL。以上文件都属于凭证或运行态，必须保持在 `.gitignore` 中。

若平台出现人工验证，仅允许在该专用浏览器窗口中按网站正常流程完成；不得绕过验证码、访问控制或反爬机制。完成后回到终端继续导出；如果验证仍未通过，明确报告会话不可用，不能将其解释为“0 条结果”。

也可使用交互菜单：

```bash
python3 scripts/main.py
```

在菜单中选择“刷新浏览器会话”。保留“粘贴浏览器复制的 cURL”作为无法启动本地 Chromium 时的备用方式；该方式从 `-b` 或 `--cookie` 提取请求 Cookie，通常比单独的响应头更完整。

也可在 Python 中调用：

```python
from scripts.cookie_tools import extract_cookie_from_curl, save_cookie_to_config
cookie = extract_cookie_from_curl(curl_text)
save_cookie_to_config("config.json", cookie, merge=True)
```

从响应头提取 `Set-Cookie` 只适用于服务端实际下发的字段。若站点还要求 `token` 等浏览器会话字段，保留并合并原有完整 Cookie。

## 首次全量抓取

使用配置文件：

```bash
python3 scripts/scraper.py --config config.json
```

或显式指定条件：

```bash
python3 scripts/scraper.py \
  --keywords "胰腺癌" \
  --state "招募中" \
  --delay 1.5 \
  --cookies "name=value; name2=value2"
```

支持的高级参数：`--reg-no`、`--indication`、`--case-no`、`--drugs-name`、`--drugs-type`、`--appliers`、`--communities`、`--researchers`、`--agencies`、`--state`。

保持合理请求间隔；默认每次请求间隔为 1.5 秒。不要并发轰击目标平台。

## 每日增量同步

运行：

```bash
python3 scripts/scraper.py --config config.json --incremental

# Cookie 遇到挑战页时，自动启动专用浏览器刷新并重试一次
python3 scripts/scraper.py --config config.json --incremental --auto-refresh-session
```

按以下顺序处理每条记录：

1. 获取详情页并保存 `raw/<登记号>_detail.html`；
2. 仅从保存后的 raw HTML 解析 RAG JSON；
3. 对规范化详情全文计算 SHA-256；
4. 与 `state.json` 或已有 JSON 中的 `content_hash` 比较；
5. 正文不变时只刷新 raw 与状态，不重写 JSON，也不重复下载 Word；
6. 新增或正文变化时写入 JSON、保存平台原样 Word，并更新指纹状态。

将 `summary.json` 中的 `skip_count` 解释为“正文未变化”，而不是“抓取失败”或“文件缺失”。

## 下载与文件格式

详情页下载必须优先按页面中 `button.download` 所在 `<form>` 的 `action`、`method` 和表单字段提交。不要把列表页的关键词、分页或排序字段混入下载请求。

平台可能将 Word 2003 XML（WordML）作为 `.doc` 响应：

- 保存 `word/<登记号>.doc` 作为浏览器下载的原样字节；
- 保存 `word/source/<登记号>.source.doc` 作为原始响应留档；
- macOS 可使用 `textutil` 生成兼容的 `word/<登记号>.docx`；
- 若 Pages 无法打开原始 `.doc`，优先使用 WPS、Microsoft Word 或生成的 `.docx`。

Word 下载失败不能阻断 JSON 归档：只要详情页的结构化数据成功提取，就将该记录标记为 JSON 成功，并在汇总中记录 Word 缺失。

## 离线回建 RAG JSON

在已有 raw HTML 的情况下运行：

```bash
python3 scripts/build_json_from_raw.py --output "output/胰腺癌"
```

覆盖既有 JSON：

```bash
python3 scripts/build_json_from_raw.py --output "output/胰腺癌" --force
```

不要为了回建 JSON 再次请求平台。回建完成后检查 `json_backfill_summary.json`、`state.json` 与生成的 JSON 数量。

## 验收

完成抓取后执行以下检查：

1. 读取 `summary.json`，核对 `total_records`、`total_extracted`、`success_count`、`fail_count`。
2. 执行以下命令，逐一比对 `summary.json.results` 中成功记录的登记号与各类归档产物：

```bash
python3 scripts/verify_output.py --output "output/胰腺癌"
```

3. 在非 macOS 环境无法使用 `textutil` 生成 DOCX 时，改用：

```bash
python3 scripts/verify_output.py --output "output/胰腺癌" --allow-missing-docx
```

4. 报告增量跳过数量与失败数量，区分“未变化跳过”和“下载/解析失败”。
5. 将 Cookie、原始会话头和任何个人凭证排除在报告、压缩包和 Git 提交之外。

## 常见故障

- **没有结果表格、空 `<body>` 且含混淆 meta/script，或被重定向登录页**：这是会话失效或反爬挑战页，不可直接解释为“检索结果为 0 条”。更新浏览器实际搜索请求 cURL 中的完整 Cookie 后重试；`--debug` 会保存响应以便复核。
- **`raw/` 有文件但 `json/` 为空**：执行 `build_json_from_raw.py`；检查详情页中是否存在包含表格的 `paddingSide15` 容器。
- **原始 `.doc` 无法打开**：确认响应包含 WordML 特征而非登录 HTML；使用 WPS/Word，或打开生成的 `.docx`。
- **增量任务没有下载 Word**：若汇总显示记录 `unchanged`，这是预期行为；先核对历史输出是否存在对应文档。

详细页面与接口规律见 `references/platform-workflow.md`。
