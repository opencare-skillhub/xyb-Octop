# 🎨 agent-taste-seed-system — 给任何 AI Agent 装上美学大脑

> 一套可移植的「审美操作系统 + 风格种子库」，让 Claude Code / Codex / OpenClaw / pi / workbuddy / codebuddy / Trae / Qoder / hermas 等任何智能体，在视觉创作上摆脱"AI 味默认审美"。
> 来源：编制者自藏《艺术风格百科大全》（24 章 250+ 艺术家/风格）→ 提炼为可执行的审美决策体系。v1.0 · 2026-09-24
> 本仓库：**https://github.com/hhx465453939/agent-taste-seed-system**

---

## 🚀 一键部署：复制指令发给你的 Agent，它自己装

> **用法（10 秒）**：在下面找到你的 Agent → 点代码块右上角 📋 复制 → 粘贴发给该 Agent → 等它自己完成部署并向你汇报。指令已自足：含仓库地址、安装步骤、汇报要求、防重复安装的防呆，Agent 无需再问你任何问题。

### 🤖 Claude Code

```text
请为本机 Claude Code 安装「美学大脑」（agent-taste-seed-system）。

仓库：https://github.com/hhx465453939/agent-taste-seed-system

步骤：
1. git clone https://github.com/hhx465453939/agent-taste-seed-system.git ~/agent-taste-seed-system（目录已存在则 cd 进去 git pull 更新）
2. bash ~/agent-taste-seed-system/deploy/install-claude-skill.sh
   （把 taste skill 装进 ~/.claude/skills/taste/，含四层种子库：总库/情绪档/代码基因卡/风格章档；脚本自带旧种子库备份）
3. 在 ~/.claude/CLAUDE.md 末尾追加「🎨 美学大脑（Taste Seed System）」薄注入节——全文逐字取自 ~/agent-taste-seed-system/deploy/claude-code.md 的「薄注入片段」小节；若 CLAUDE.md 已存在同名节则跳过，不要重复追加
4. 完成后向我汇报：skill 安装路径与文件清单、CLAUDE.md 追加结果、让我如何验证生效

注意：不要修改仓库内 references/ 的任何内容（那是种子库本体）。
```

### 🦞 OpenClaw

```text
请为 OpenClaw 工作区安装「美学大脑」（agent-taste-seed-system）。

仓库：https://github.com/hhx465453939/agent-taste-seed-system

步骤：
1. git clone https://github.com/hhx465453939/agent-taste-seed-system.git ~/agent-taste-seed-system（已存在则 git pull）
2. 先读 ~/agent-taste-seed-system/deploy/openclaw.md，然后按文档执行：
   - 把仓库的 TASTE.md 放到 workspace 根目录，references/art-seeds.md 放到 workspace 的 taste/ 子目录（多龙虾舰队时每个 workspace 各放一份，禁止跨项目串人格文件）
   - 把仓库 AGENT-INJECTION.md 里的「注入提示词」整段并入该 workspace 的 AGENTS.md 或 SOUL.md（已有同名节则跳过）
3. 完成后向我汇报：文件放置路径、注入位置，以及对龙虾的验证方式（如让它画一张海报看是否先报情绪关键词）
```

### 🧠 Codex

```text
请为本机 Codex 安装「美学大脑」（agent-taste-seed-system）。

仓库：https://github.com/hhx465453939/agent-taste-seed-system

步骤：
1. git clone https://github.com/hhx465453939/agent-taste-seed-system.git ~/agent-taste-seed-system（已存在则 git pull）
2. 读 ~/agent-taste-seed-system/deploy/generic-agents.md，按「情形 A：有全局规则文件」执行：在你的全局规则文件（如 ~/.codex/AGENTS.md）末尾追加文档中的薄注入片段（片段里的路径保持 ~/agent-taste-seed-system 不变；已有同名节则跳过）
3. 完成后向我汇报：clone 位置、修改的文件、追加的行数，以及下次视觉任务你会如何走「情绪定位→选基因→翻译参数→自检→记档」流程
```

### 🧩 Trae / Qoder / pi / workbuddy / codebuddy / hermas 等其他 Agent（通用版）

```text
请为本 Agent 安装「美学大脑」（审美种子系统）。

仓库：https://github.com/hhx465453939/agent-taste-seed-system

步骤：
1. git clone https://github.com/hhx465453939/agent-taste-seed-system.git ~/agent-taste-seed-system（已存在则 git pull）
2. 读仓库的 README.md 和 deploy/generic-agents.md，判断你自己的规则加载机制并按对应情形部署：
   - 有全局规则文件 → 在其末尾追加文档中的薄注入片段（已有同名节则跳过）
   - 只有系统提示词/知识库 → 把 AGENT-INJECTION.md 的注入提示词整段并入，TASTE.md 与 references/art-seeds.md 作为可读取的知识文件
3. 部署后自检：用一句话复述你的视觉任务工作流（情绪定位 → 查种子库选 1 主 + 1 辅基因 → 五基因翻译成参数 → 一句话自检 → 交付后记风味日志）
4. 向我汇报：部署方式、文件位置、自检复述
```

### 🌐 万能版（任意 Agent，含网页 ChatBot）

```text
从现在起装备「美学大脑」。请访问 https://github.com/hhx465453939/agent-taste-seed-system 阅读 README.md、TASTE.md、AGENT-INJECTION.md（种子库 references/ 目录按需读取，不要全量载入）。

之后所有涉及审美与视觉呈现的任务（长图/海报/PPT/图表/插画/UI/封面/配色/文生图提示词/Word 与文档排版，以及生活与社会关系中的审美咨询），你都必须：
先情绪定位（读者该感受什么，一个词）→ 按种子库选 1 主 + 1 辅风格基因 → 把五基因（色彩/光线/笔触/构图/情绪）翻译成具体参数 → 一句话自检（这张作品的风格基因是什么）→ 交付后记录本次搭配。

禁止输出 AI 味默认审美（通用卡片/蓝紫渐变）；一组作品一个主基因，敢混搭只混一层。
```

> 💡 万能版仅适用于**能联网浏览**的 Agent。若对方无法访问 GitHub：把本仓库的 `TASTE.md` 和 `references/art-seeds.md` 下载后作为附件/知识库上传给它，再发上面的指令（去掉第一条访问要求）即可。

### ✅ 部署成功的标准（任何 Agent 通用）

1. 让它「做一张 XX 海报」：它**先报情绪关键词**再动手
2. 交付时它能**一句话说出风格基因**（主 + 辅）
3. 它的种子库副本末尾出现新的风味日志条目

---

## 这是什么

核心思想：**风格即基因** —— 色彩 × 光线 × 笔触 × 构图 × 情绪，五个基因位。
任何需要审美的输出，先选基因、再动手。

**适用范围：一切需要美学的产物**——图片与插画、HTML/网页/长图、PPT、Word 与文档排版（简历/报告/公文）、图表与数据可视化、UI 与皮肤、视频分镜，乃至生活与社会关系中的审美（穿搭配色、家居氛围、礼物与请柬、仪式感设计）。人眼需要美学，人与人的关系也需要美学。

```
创作任务 → 情绪定位 → 查种子选基因（1主+1辅）→ 基因按媒介翻译成参数 → 一句话自检 → 交付 → 用户反馈 → 风味日志 → 种子库进化 → 下次更好
```

**激活词原理**：艺术家名/风格名是 LLM 预训练美学基因的激活锚点——prompt 里直接点名「马远一角构图」「卡拉瓦乔 Tenebrism」比任何形容词都精准。本系统的职责：帮你选对激活词 + 把激活出的审美翻译成可执行参数。

## 文件清单

| 文件 | 作用 |
|------|------|
| [`AGENT-INJECTION.md`](AGENT-INJECTION.md) | ⭐ 通用注入提示词 + 部署说明（最小接入看这个） |
| [`TASTE.md`](TASTE.md) | 审美操作系统入口：审美观 5 条 + 决策流程 + 情绪→种子索引 |
| [`references/art-seeds.md`](references/art-seeds.md) | L1 总库速查：全量种子单行表（250+ 艺术家，按需查询勿全文注入） |
| [`references/moods/`](references/moods/) | L2a 情绪档 ×10：每情绪主推种子的五基因详解 + 媒介适配 + 翻车清单 |
| [`references/code-genes/`](references/code-genes/) | L2b 代码基因卡 ×12：写代码出图直接抄的部署提示词 + CSS 变量块 + 反模式 |
| [`references/chapters/`](references/chapters/) | L2c 风格章档 ×24：《艺术风格百科大全》原文全量，每艺术家 2-3 句细述 |
| [`sources/`](sources/) | 源文档归档（docx 原始百科） |
| [`templates/SKILL.md`](templates/SKILL.md) | Claude Code skill 文件（四层路由版，安装脚本直接拷贝用） |
| [`deploy/`](deploy/) | 各类智能体的详细部署文档 + 一键脚本（上面指令的权威细节都在这里） |

## 知识库分层架构（重 agent 按需加载，禁止全文注入）

```
L0  TASTE.md                      决策层：情绪定位 → 该查哪层
│
├─ L2a moods/（10 份）            知道情绪时第一落点
│    每情绪 2-3 粒主推种子 · 五基因详解 · 媒介适配 · 翻车清单
│
├─ L2b code-genes/（12 张）       写代码出图（网页/长图/dashboard）
│    部署提示词 + CSS 变量块 + 激活词 + 反模式，直接抄参数
│
├─ L2c chapters/（24 章）         深挖某艺术家/流派
│    原文零删减 · 每艺术家 2-3 句细述 + AI Prompt Keywords
│
└─ L1 art-seeds.md                全量单行速查总表（关键词全局搜）
```

## 手动部署（不想发指令、自己动手时）

| 你的 Agent | 方式 | 文档 |
|-----------|------|------|
| **Claude Code** | skill + CLAUDE.md 薄注入（一键脚本） | [`deploy/claude-code.md`](deploy/claude-code.md) |
| **OpenClaw** | workspace 放置 + SOUL/AGENTS 注入 | [`deploy/openclaw.md`](deploy/openclaw.md) |
| **Codex / pi / workbuddy / codebuddy / Trae / Qoder / hermas** 等 | 全局规则文件薄注入 | [`deploy/generic-agents.md`](deploy/generic-agents.md) |
| 通用 ChatBot（无文件机制） | 系统提示词整段注入 | [`deploy/generic-agents.md`](deploy/generic-agents.md) |

```bash
# Claude Code 最快路径
git clone https://github.com/hhx465453939/agent-taste-seed-system.git \
  && bash agent-taste-seed-system/deploy/install-claude-skill.sh
```

## 使用原则

1. **种子库按需查询，不注入上下文**——创作时按情绪/章节/关键词检索需要的种子卡即可，全文进上下文是浪费
2. **风味日志是系统的灵魂**——每次交付后把搭配与反馈记进种子库末尾，定期同步回本仓库，越陈越香
3. **本仓库是活文档**——新风格、新配方、新混种，欢迎 PR 补录

## License

MIT
