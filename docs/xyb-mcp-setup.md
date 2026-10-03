# 项目绑定 MCP 的 AI 安装配置指引

小胰宝预置了一批临床 MCP 服务（见 [README_CN.md → MCP 服务](../README_CN.md#-mcp-服务)）。
它们不会随安装自动启用，需要为某个用户**播种**一次。

本文件给出一条可直接投喂给 AI 编码助手的提示词，让它把播种、配对、验证一次做完。
手工步骤与排错见后半部分，供提示词失效时兜底。

---

## 一、一句话提示词（复制即用）

> 请把本机的 ctv-mcp-server（源码目录由 `XYB_VEEVA_DIR` 指定，默认 `~/Downloads/ctv-mcp-server`）
> 作为本地 stdio MCP 接入小胰宝 Octop：先确认该目录下 `dist/index.js` 已构建、`node` 可解析，
> 再运行 `xyb-octop xyb init-mcp --user admin` 完成播种（需要 root 权限时先说明），
> 然后用 `scripts/xyb-check-mcp.sh` 做一次真实 MCP 握手校验，确认 `xyb-veeva` 能列出 12 个工具，
> 最后报告实际新增的 server 名、通道与工具数；前置条件不满足的服务要如实报告原因，
> 不要静默跳过，也不要修改任何我没让你改的配置。

### 为什么这么短就够

提示词只锁定三件 AI 容易做错的事，其余交给它自己读代码：

| 约束 | 防的是什么 |
|------|-----------|
| 先确认 `dist/index.js` 与 `node` | 播种器对未构建的 veeva 会报 `unbuilt` 而非写坏命令，但 AI 容易跳过这一步直接说"装好了" |
| 用 `xyb-octop xyb init-mcp` 而不是手写 JSON | 手写会绕过"只增不改"与前置条件检查，还可能起错名字造成重复挂载 |
| 要求如实报告跳过项 | `xyb-metaso` 缺 `METASO_API_KEY` 时会被跳过，AI 通常只报成功的那几个 |

---

## 二、背景：播种器解决什么问题

`xyb-octop xyb init-mcp` 把 `src/octop/infra/connectors/xyb_defaults.py` 里声明的服务
写进当前用户的 `custom-mcp` 连接器文档。这个文档是**整份覆盖**写入的，
所以播种器有三条刻意设计的行为：

1. **只增不改** —— 同名服务已存在就保持原样，你改过的配置不会被冲掉。
2. **缺前置就跳过，不写坏配置** —— 需要环境变量的服务（如 `xyb-metaso`）在变量缺失时
   只报告不写入。写进去只会把"未配置"变成启动期的隐晦报错。
3. **不替你装依赖** —— 它只写配置。npm 包、Playwright Chromium、veeva 的 `dist/` 都要你自己就绪。

---

## 三、AI 会执行的步骤

### 步骤 1：确认 veeva 前置

```bash
echo "${XYB_VEEVA_DIR:-$HOME/Downloads/ctv-mcp-server}"
ls -l "${XYB_VEEVA_DIR:-$HOME/Downloads/ctv-mcp-server}/dist/index.js"
node --version
```

三者缺一不可：入口文件存在、`node` 在 PATH 里、`node_modules` 已装
（veeva 依赖 `better-sqlite3` 原生模块，没装会在启动时炸）。

### 步骤 2：先看计划，再写入

```bash
xyb-octop xyb init-mcp --user admin --dry-run   # 只打印，不写入
xyb-octop xyb init-mcp --user admin             # 真正写入
```

期望看到 6 行计划：

| server | 通道 | 常态动作 |
|--------|------|----------|
| `xyb-clinicaltrials` | clinicaltrials | add |
| `xyb-chictr` | chictr | add |
| `xyb-veeva` | veeva | add（前置缺失时为 `unbuilt`） |
| `xyb-pubmed` | literature | add |
| `xyb-metaso` | search | **skip**（缺 `METASO_API_KEY`） |
| `xyb-dayi` | drug-search | add |

> `--user` 可省略，省略时用 `xyb-octop config set-user` 固定的用户。
> 只想补一个服务就加 `--only xyb-veeva`。

### 步骤 3：让运行中的服务感知变更

播种会写入配置并触发连接器重载。若服务正在运行且没自动重载：

```bash
curl -X POST http://127.0.0.1:8088/api/plugins/reload   # 仅插件用
# 连接器变更由 PUT/PATCH 自动调度重载；必要时重启 xyb-octop run
```

### 步骤 4：真实握手校验

项目自带探针，不需要 LLM、也不需要 Octop 在跑 —— 它按连接器网关同样的方式
直接说 MCP over stdio：

```bash
scripts/xyb-check-mcp.sh --list            # 列出已知服务与启动命令，不启动任何进程
scripts/xyb-check-mcp.sh xyb-veeva         # 只校验一个
scripts/xyb-check-mcp.sh                   # 校验全部（chictr 会首次下载约 570MB）
scripts/xyb-check-mcp.sh --json            # 机器可读
```

期望输出：

```
[PASS] xyb-veeva            veeva            OK  version=0.1.0 tools=12
passed=1 failed=0 skipped=0
```

它会把服务**实际**返回的 `serverInfo.version` 和工具数报出来，所以版本漂移是可见的，
而不是靠假设。

> 已保存的配置也可以用 API 探测：
> `POST /api/connectors/custom-mcp/test`，body `{"name":"xyb-veeva"}`。

---

## 四、手工兜底（不依赖 AI）

```bash
# 1. 查看当前已配置的 MCP
curl -s http://127.0.0.1:8088/api/connectors/custom-mcp -H "Authorization: Bearer $TOKEN"

# 2. 播种
xyb-octop xyb init-mcp --user admin --dry-run
xyb-octop xyb init-mcp --user admin

# 3. 图形界面
#    控制台 → 连接器 → 自定义 MCP
```

---

## 五、验证：怎么确认真的挂上了

分四层，从便宜到贵：

**第 1 层 — 配置写没写进去**

```bash
curl -s http://127.0.0.1:8088/api/connectors/custom-mcp -H "Authorization: Bearer $TOKEN"
```

每个服务应带 `"enabled": true` 与 `"default_open": true`。

**第 2 层 — 进程能不能拉起来**

```bash
scripts/xyb-check-mcp.sh --json
```

每个请求的服务都应 `PASS`，`xyb-veeva` 的 `tools` 应为 12。

**第 3 层 — 工具有没有挂到 Agent**

发一轮真实对话，然后看日志：

```bash
grep -i "mcp tool cache store\|MCPToolMiddleware filter" ~/.octop/logs/octop.log | tail -5
```

期望：

```
mcp tool cache store user=1 server=xyb-veeva tools=12
MCPToolMiddleware filter: mcp_servers=['xyb-veeva'] active=['xyb-veeva'] mcp=12->12
```

**第 4 层 — 工具能不能真的执行**

让它跑一个只读工具（不会改数据）：

```bash
xyb-octop chats send --agent main --plain "调用 get_index_stats，报出 CTV 本地索引的记录数与详情覆盖数。"
```

期望返回真实数字（如"记录数 210、已补全 20"）。**这一步才证明整条链路通了。**

---

## 六、排错

| 症状 | 原因 | 处理 |
|------|------|------|
| 播种显示 `unbuilt` | `dist/index.js` 不存在 | 在 ctv-mcp-server 里 `npm install && npm run build` |
| 探测 `ok: false`，命令找不到 | Octop 进程 PATH 里没有 `node` | 把 `command` 换成 node 绝对路径（`which node` 的结果） |
| 探测报 `server closed stdout before replying` | `npx -y <包名>` 无法确定跑哪个 bin —— 该包有多个 bin，或唯一的 bin 名字不等于包名 | 用 `npx -y -p <包名> <bin名>`；bin 名用 `npm view <包名> bin` 查（`xyb-metaso` 就是这种情况：包名 `metaso-search-mcp`，bin 是 `metaso-mcp`） |
| 探测 `ok: false`，模块加载失败 | `better-sqlite3` 的 ABI 与当前 node 不匹配 | 用与构建时同一个 node，或在该 node 下 `npm rebuild better-sqlite3` |
| 对话里没有该工具 | `default_open` 没生效，或服务未重载 | 检查配置里的 `default_open`，重启 `xyb-octop run` |
| `search_studies` 搜不到东西 | 本地索引是空的或覆盖不全 | 先跑 `import_csv_export` 或 `sync_sitemap` 建库，再 `backfill_details` 补详情 |
| 模型报 `Model does not exist` | 模型引用把 provider 前缀带进了模型 id | 显式指定模型绕过，如 `--model "SiliconFlow (China)/deepseek-ai/DeepSeek-V3.2"` |

---

## 七、接入自己的 MCP（模板）

任何语言的 stdio MCP 都能直接挂，不必是 Python：

```bash
curl -X PUT http://127.0.0.1:8088/api/connectors/custom-mcp \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"servers":{"my-server":{
        "transport":"stdio",
        "command":"/abs/path/to/node",
        "args":["/abs/path/to/dist/index.js"],
        "env":{"MY_DATA_DIR":"/abs/path/to/data"},
        "display_name":"我的 MCP",
        "enabled":true,
        "default_open":true
      }}}'
```

要点：

- **`command` 与 `args` 用绝对路径** —— 没有工作目录字段，相对路径会相对 Octop 进程解析。
- **`default_open: true`** 才会每轮对话自动挂载；否则只在控制台手动勾选时加载。
- **依赖自己装好** —— Octop 不会替你 `npm install` / `pip install`。
- 自定义 MCP 是**懒加载**的：启动时只登记名字，工具在你打开对话时才注入。

HTTP 传输把 `command`/`args` 换成 `"url": "https://..."` 即可；
公开地址必须 HTTPS，本机/内网可用 HTTP。
