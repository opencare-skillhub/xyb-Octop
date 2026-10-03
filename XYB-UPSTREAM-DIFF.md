# XYB-UPSTREAM-DIFF — 上游改动清单

**上游基线** `opencare-skillhub/xyb-Octop` @ `e473dd3c4a4741618ffde1a42a3492341a189e8e`（release 1.0.2b5，2026-09-29）
**用途** NFR-2：本项目对小胰宝所做的每一处改动都登记在此，便于日后跟版合并上游。
**维护规则** 每次改动上游文件，同一次提交内追加一行；新增文件不登记（它们不冲突），只登记**被修改或删除的上游文件**。

---

## 一、改动分类口径

| 类型 | 含义 | 合并上游时的成本 |
|---|---|---|
| **A · 加数据** | 只往既有扫描目录放文件 | 零冲突 |
| **B · 加配置** | 新增清单/声明，少量代码读取 | 低 |
| **C · 改上游文件** | 修改或删除上游已有文件 | **需要逐行复核**，本文件主要登记这一类 |

目标比例约为 A 70% / B 20% / C 10%（见设计文档 §1.1）。**本文件存在的意义就是把 C 类压到最小并全部留痕。**

---

## 二、C 类改动登记（改上游文件）

| # | 上游文件 | 改动内容 | 原因 | 阶段 | 状态 |
|---|---|---|---|---|---|
| C-1 | `src/octop/infra/agents/teams/template/*` | **不改**（原计划要改，实施时改为方案 B） | 上游团队模板是**固定单一模板**，被所有团队共用（含非医学团队）。把医学会诊协议写进去会污染通用模板。改为：MDT 编排规则写进**被创建的团队实例工作区** `MDT-ORCHESTRATION.md`，由 `octop xyb init-mdt` 播种 | P5 | ✅ 完成（方案变更，见下方说明） |
| C-2 | `src/octop/infra/agents/plugins/manager.py`（+ 12 个 `bundled/*/plugin.yaml` 各加两行注释与一行键） | 新增 `default_enabled` 支持：读取点为 `_bundled_default_enabled()` / `_plugin_is_enabled()`，替换 6 处「默认 True」的判断；12 个娱乐/信息类插件声明 `default_enabled: false` | 上游「所有 enabled 读取一律默认 True」，且 `install_from_market` 硬编码 `enabled: True`（`:378`），没有「默认关闭」这个旋钮。FR-1.5 要求患者侧不默认暴露娱乐/工程类插件 | P3 | ✅ 完成 |
| C-3 | `dashboard/index.html` | `<title>`、`apple-mobile-web-app-title` → 小胰宝；启动屏改用新 logo | FR-1.2 / FR-1.3 | P3 | ✅ 完成 |
| C-4 | `dashboard/public/manifest.json` | `name`/`short_name`/`description` → 小胰宝 | FR-1.2 | P3 | ✅ 完成 |
| C-5 | `dashboard/public/logo_*`、`pwa-*`、`apple-touch-icon.png`、`favico.svg` | 换为小胰宝 logo 派生资源 | FR-1.3 | P3 | ✅ 完成 |
| C-6 | `src/octop/i18n/{zh,en}.json` | 品牌词替换 | FR-1.4 | P3 | ✅ 完成 |
| C-7 | `dashboard/src/locales/{zh,en}.json` | 品牌词替换 | FR-1.4 | P3 | ✅ 完成 |
| C-8 | `pyproject.toml` | `[project].name` → `xyb-octop`；作者串、新增 console script `xyb-octop`（**保留 `octop` 兼容别名**） | FR-1.1 / 测试计划 D1 | P3 | ✅ 完成 |
| C-9 | 发布管线：`.github/workflows/{release,docker-publish,octop-desktop,fnos-build-fpk}.yml`、`desktop/portable/{_common.sh,package.sh}`、`scripts/release_download_links.py`、`fnos/{docker,native}/manifest`、`Makefile`、`docker/*`、`README*.md` | 品牌串替换（产物名 `xyb-octop-*`、仓库 slug、商店展示名小胰宝） | FR-1.1 / FR-1.6 | P3 | ✅ 完成 |

### C-1 的方案变更说明（重要）

设计文档原计划**直接改上游团队模板**（`infra/agents/teams/template/`），把医学编排规则写进去。
实施时发现这不成立：`seed_team_template` 从**同一个固定目录**为**所有** team 播种
（`infra/agents/teams/service.py:311-348`），所以改模板等于给每一个团队——包括非医学团队——
装上「12356 危机热线 / 分歧点 / 不派工」这套医学协议。

**改用的方案**：通用模板一行不动；医学编排规则作为 `MDT-ORCHESTRATION.md` 写进
**被创建的那个团队实例的工作区**，由 `octop xyb init-mdt` 在创建团队后播种。

好处有三：
1. **零上游改动**，C-1 从「改上游」降级为「不改」，跟版更省事；
2. 医学规则只作用于小胰宝自己创建的会诊团队，不会外溢；
3. 规则可随实例更新，不需要发版。

代价：团队实例的编排规则不由模板自动继承——**换新团队要重新执行一次
`octop xyb init-mdt`**（命令幂等，重复执行不会重复建）。

### C 类改动是如何做的（可重跑、不靠手改）

全部品牌替换由 `scripts/xyb_rebrand.py` 完成，而不是手工编辑或全局 `sed`：

- 规则表**有序**，「保护的契约名」写在「通用品牌名」之前，因此 `octop run`、`~/.octop`、`OCTOP_HOME`、`src/octop/`、`postgresql://octop:octop@…` 这类字符串先被消费掉，不会被误改。
- **幂等**：连跑两次第二次为 0 改动（`--check` 门禁，`tests/unit/naming/` 有断言）。
- `--dry-run` 可先看全量差异再落盘，`--check` 用于 CI。

> 曾经踩到的坑（已修复并留痕）：早期版本把 `packages = ["src/octop"]`、`myreg/octop:v1`、`postgresql://octop:octop@…` 也改了。**这正是"禁止全局替换"的实例证据**，规则表现在按上下文精确匹配。


---

## 三、A/B 类新增清单（不改上游文件，仅备查）

| 路径 | 类型 | 阶段 |
|---|---|---|
| `src/octop/infra/agents/experts/library/xyb-*/`（17 个专家包） | A | P2 ✅ |
| `src/octop/infra/agents/builtin_skills/xyb-*/`（4 个护栏技能） | A | P2 ✅ |
| `src/octop/infra/connectors/xyb_defaults.py` | B | P1 ✅ |
| `src/octop/cli/commands/xyb.py` | B | P1 ✅ |
| `scripts/xyb-*`（审计/探针/生成器/引导） | B | P0 ✅ |
| `dashboard/public/brand/` | A | P3 ✅ |
| `XYB-*.md` | A | P0 ✅ |

### 副产物（不是交付物，已在 .gitignore 之外手工清理）

- `cache/index.json` — 由 `mcp-pubmed-llm-server` 在**当前工作目录**落盘产生。跑 MCP 探针时会生成，不要提交。
- `.workbuddy/` — 会话工具目录，先于本项目存在。
- `dashboard/node_modules/` — 前端依赖，已在 `.gitignore` 内。


---

## 四、冻结契约（明确不改，改了就破坏兼容）

这些是「看着像品牌、其实不是」，全局替换会立刻打破兼容。`scripts/xyb_name_audit.py`
的 `C1–C8` 检查会守住它们。

| 冻结项 | 实测位置 | 冻结原因 |
|---|---|---|
| 数据目录 `~/.octop` | `src/octop/infra/utils/paths.py` | 既有安装的用户数据、专家、技能都在这里 |
| `OCTOP_HOME` 覆盖 | 同上 | 已文档化的部署契约 |
| 导入包 `src/octop/` | 637 个模块 | 改导入路径没有收益，却要动每一个模块 |
| `octop-login.txt` | `infra/setup/password_file.py` | 用户按文档找这个文件名 |
| systemd 单元 `octop-desktop-*.service` | `infra/desktop/setup.py` | 已装在用户机器上，改名会造成孤儿单元 |
| 容器数据路径 `/data/.octop` | `docker/Dockerfile` | 卷契约 |
| compose 挂载 `OCTOP_DATA` | `docker/docker-compose.yml` | 既有 compose 文件继续可用 |
| HTTP 头 `X-Octop-Agent-Id` | `dashboard/src/api/request.ts`、`api/routers/mbti.py` | 前后端混版本互通 |
| 依赖 `octop-harness` / `octop-memory` / `octop-gateway` / `octop-browser` | `pyproject.toml` | 上游第三方发行包，不是我们的 |
| 环境变量前缀 `OCTOP_*` | 207 个文件 | 部署契约 |
| `OctopBot` | 频道名 | 第三方平台名，不是本产品品牌 |
| `slash.fields.octop` | `src/octop/i18n/*.json` | 斜杠命令字段名 |

> **决定**：**包名与数据目录保持 `octop`**。改包名会波及 637 个 `.py` 的 import 与全部用户数据路径，收益仅为「包名好看」，不做。

---

## 五、UI 展示名与产物名的分层（本项目的口径）

用户已确认：**界面显示「小胰宝」，包名/镜像名用 `xyb-octop`**。因此两条命名链并存：

| 层 | 取值 | 例子 |
|---|---|---|
| **展示名**（患者可见） | 中文「小胰宝」 | 浏览器标签页、PWA 安装名、侧栏 wordmark、登录页、欢迎语 |
| **技术名**（产物/包/镜像/商店 ID） | ASCII `xyb-octop` | `pyproject` name、console script、wheel、Docker 镜像、FnOS `appname`、桌面/便携包文件名 |

**后果（已在 `XYB-TEST-PLAN.md` 记录）**：测试计划 AC-1 原要求「界面名也是 ASCII 的
`xyb-octop`」，与本决定冲突。现将 AC-1 收窄为**只约束包名与产物名**，
界面展示名改为断言「小胰宝」，`I14/I15` 的 ASCII 门禁不再覆盖 PWA `name`/`short_name`
与 HTML title（它们现在**应当**含中文）。

---

## 六、每次改动后的登记流程

```bash
# 1. 看这次动了哪些上游文件
git diff --name-only HEAD

# 2. 是否在上面的 C 类登记表里？不在就补一行
# 3. 跑门禁，确认没有碰到冻结契约
scripts/xyb-check-branding.sh
```

**判定标准**：`git diff --name-only` 列出的路径，减去「A/B 类新增清单」里的路径，
剩下的每一条都必须在 §二 的 C 类表里有登记。没有登记的上游改动视为遗漏。

---

## 七、独立评审发现与处置（2026-10-02）

一次对抗性评审（无 BLOCKER，10 MAJOR / 10 MINOR）对本项目做了只读复核。
下表是每条的处置，**未修的也留在这里**，避免丢失。

### 本轮已修

| # | 问题 | 处置 | 验证 |
|---|---|---|---|
| M1 | 品牌改造没覆盖 UI：95 个 tsx 里 139 处用户可见 "Octop"，而门禁只扫 8 个文件 | 门禁扩到全部 `.tsx`（用「JSX 文本 + `t()` 兜底串」精确提取，避免 100+ 误报）；修掉 25 处可见串并重指帮助链接 | 门禁 `failed=0`；`--explain` 只剩已记录标识符 |
| M2 | 英文文案让用户运行一个**不存在的命令**（`CLI: 小胰宝 update`）——通用规则把 CLI 命令名也改了 | 恢复 `octop`，并在规则表加 `keep-cli-name-in-prose` 保护 | 4 处文案已正确；门禁白名单已记录 |
| M3 | `xyb_import_skills.py --check` 无法失败：缺溯源头时返回 1 但未被计数 | 修 `main` 的失败计数 | 构造无来源头的技能，门禁正确退出非 0 |
| M4 | Docker Hub 镜像后缀没改（仍是 `/octop`），而 `I10` 靠注释误判为 PASS | 改发布步骤；`I10` 改为断言 `hub=` 行 | `grep` + 门禁 |
| M5 | FnOS Docker 包拉取一个没有任何工作流发布的镜像（组织名与镜像名都旧） | compose 与 README/Dockerfile/manifest 统一为 `ghcr.io/opencare-skillhub/xyb-octop`；`fnos/*` 纳入两个工具的文件清单 | `grep` 无残留 |
| M6 | **危机信号不是第一条**：自伤位列 6 条急症最后，且规定首句只说「立即就医/120」不含 12356；心理专家的问诊项排在第 5 项（而该文件自称一次最多问 3 项） | 危机信号独立成「第四节·优先级高于一切」，含 12356 首行、不派工、不进入骨架；躯体急症降为第五节；自检表加入危机项 | 17 个专家 AGENTS.md 全部重新生成并校验通过 |
| M9 | 每个专家 AGENTS.md 都指导模型使用**不存在的目录**（`../../references/`、`agents/`） | 删除这两条；改为「技能优先于记忆」「判断留在本视角」 | 生成器 `--check` 通过 |
| m1 | 两个校验器在 PASS 行也打印失败文案（`[PASS] ... package dir missing`） | 仅失败时打印 detail | 目视确认 |
| m9 | `dashboard/package.json` 仍是 `octop-dashboard` | 改为 `xyb-octop-dashboard` | 读取确认 |
| 色板 | 菜单品牌色是上游暖玫红 `#E85D75`，与新 logo 冲突 | 默认色板换为 logo 薄荷绿（`mint`），旧存储值 `rose` 自动迁移 | 真实浏览器计算样式：`--fn-color-brand: #2F8F80`、`--fn-sidebar-item-active-bg: #EAF6F3` |
| 吉祥物 | 空状态吉祥物是上游红色章鱼，与新品牌冲突 | 4 个吉祥物资源由新 logo 生成，尺寸保持一致 | 截图确认 |

### 经复核为「有意保留」，不改

评审把这些当成缺陷，但它们正是 `XYB-UPSTREAM-DIFF.md` §四列出的**冻结契约**：

- `~/.octop`、`OCTOP_HOME`、`src/octop/`、`octop-harness` 等导入与数据路径；
- `X-Octop-Agent-Id` / `X-Octop-Access-Token` 协议头（混版本互通）；
- JSON/YAML 键名 `"octop"`（SKILL.md frontmatter 命名空间）；
- 路由 `/octop/*`、存储键 `octop:*`、数据库名/用户名 `octop`；
- 容器镜像名 `octop` 与上游安装脚本 CDN 路径。

### 第二轮已修（承接上表）

| # | 问题 | 处置 | 验证 |
|---|---|---|---|
| M7 | `init-mdt` 对已存在团队不改成员，`--member` 空操作但输出报新成员数 | 改为：存在团队时用 `teams.replace_members` 增补缺失成员、`registry.reload` 生效，并**每次**重新播种编排规则（规则变更无需发版） | 实跑：先建 3 人团队 → 再跑默认名册 → 团队实际从 3 人变 11 人；第三次跑 0 新建、0 入队 |
| M8 | `DEFAULT_MDT_MEMBERS` 漏掉 `xyb-mdt-intervention`（需求 A 组第 5 位） | 补入；测试从 `<= 12` 改为**精确断言 11 个成员**，并断言不含急症视角 | `pytest tests/unit/cli/test_xyb_cmd.py` 9 passed |
| M10 | `xyb-brand.py --check` 在正确树上误报资源过期（逐字节比较跨 Pillow 构建不可复现） | 改为比较**解码后的像素与画布尺寸**；SVG 比较其内嵌栅格的解码结果 | `xyb-brand.py --check` exit 0；该门禁**接入 pytest**（评审指出此前只绑定未调用） |
| FR-1.5 | 娱乐/工程类 bundled 插件未默认关闭 | 新增 `default_enabled` 键与解析器，替换 6 处默认判断；12 个娱乐/信息类插件声明关闭 | 新增 8 个测试；`test_plugin_seed`/`test_bundled_plugins_layout`/`test_plugin_manager`/`test_plugins` 共 41 passed |

### 第三轮已修（m 系列与孤立代码）

| # | 问题 | 处置 |
|---|---|---|
| m2 | 护栏校验 G1–G6 **形同虚设**：这六条由共享模板提供，任何生成的 SOUL.md 都能通过，无法发现某个角色缺失专属禁令 | 新增 **G8**：从 `xyb_soul_data.SOUL_DATA` 读该角色的 `extra_bans`，要求逐条出现在其 SOUL.md。已实测：删掉介入专家的角色禁令后 G8 失败，恢复后通过。检查项从 323 → 340 |
| m3 | 文档与注释写「18 个专家 / 18 个视角」，实际 17 个包 | 统一为 17；case-summary 共享技能经生成器同步到全部 17 份 |
| m4 | chictr 探针把**任何**失败都判为 `CHALLENGED`（其 hint 含 "verification"） | 改为只匹配 `result.error`；把 `LOCAL_SSL_TRUST` 补进文档化的状态词表 |
| m5 | `trial-search` 把单个通道的空结果说成「四个通道都没检索到」 | 改为**逐通道**表述，并把「是否逐通道说 0 条」加进自检 |
| m8 | `profile.py` 文档写「退出码 2 需要确认」，实际不可达 | 文档改为与实现一致（未确认按 1 处理） |
| 孤立代码 | `SUPPORT_CHANNELS`、`precondition_hints()`、`include_optional`（无调用方会传）、`SOULS = ()`、`RULES_BY_NAME`（注释称测试使用，实无） | 全部删除；`channel_of()` 保留（有测试且是通道↔服务的唯一映射） |

### 评审项处置结论

三轮处置完毕，**无遗留项**：10 条 MAJOR 与 10 条 MINOR 全部落地（修复、或经复核判定为有意
保留的冻结契约并已说明理由）。评审同时明确「未发现问题」的类别：生成器与已提交文件的一致性、
dataclass 默认值与字段顺序陷阱、分层与契约违规、SQL 外泄、路由层业务逻辑。

唯一无法在代码侧解决的是环境阻塞（见 `XYB-DESIGN.md` 实施状态表的「环境级阻塞」）：
chictr 需要下载 Playwright Chromium，而 `~/Library/Caches/ms-playwright/__dirlock`
被 macOS TCC 保护、当前用户无法删除，`playwright install` 因此中止。
