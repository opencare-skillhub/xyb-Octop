# 小胰宝 Octop 需求文档

**版本** v1.0 · 2026-10-01
**上游基线** `opencare-skillhub/xyb-Octop` @ `e473dd3`（release 1.0.2b5，fork 自 `TencentCloud/Octop`）
**定位** 面向胰腺癌（PDAC）患者与家属的自托管多用户 AI 助手平台
**状态** 待确认 → 确认后进入设计定稿与开发分解

---

## 一、这是什么、为什么做

Octop 是一个自托管、多用户、多智能体的 AI 助手平台：单进程同时提供 Web 控制台、CLI、IM 通道与定时任务，全部数据落在本机 `~/.octop/`。

本项目要做的不是"再做一个聊天壳"，而是把 Octop 的**专家体系、技能体系、连接器体系**这三层能力，按胰腺癌患者长程照护的真实需要重新装配：

| 层 | 上游现状 | 本项目要做的事 |
|---|---|---|
| **专家** | 19 个模板（含 1 个医学向） | 新增 **16 个 MDT 角色专家 + 1 个 MDT 主持团队** |
| **技能** | 内置仅 `skill-manager` | 从 `opencare-skillhub` 精选 **约 22 个**医学/查询/运营技能入库 |
| **连接器/MCP** | **无任何医学数据源**（已实测确认） | 接入 **5 个 MCP**，形成 **clinicaltrials / chinadrugs / chictr / veeva 四大临床通道** |
| **UI** | Octop 品牌、英文为主 | 改为 `xiaoyibao-octop`，中文小胰宝版 + 新 logo + 患者向默认配置 |

一句判断：**上游缺的正好是"医学"这一整层，本项目补的就是这一层，外加一层品牌皮。**

---

## 二、上游基线与现状（实测，非推测）

### 2.1 技术栈与规模

| 项 | 值 |
|---|---|
| 语言 / 框架 | Python 3.12+ · FastAPI + uvicorn |
| 前端 | React 18 + TypeScript + Vite + Ant Design，**427 个 `.tsx`** |
| 智能体运行时 | Octop Harness（`langgraph` checkpoint，按专家隔离） |
| 控制面 DB | SQLite（WAL，默认）或 PostgreSQL |
| 代码量 | `src/` 下 **1122 个 `.py`** |
| 许可证 | MIT |

### 2.2 五处扩展点（已逐一定位到路径）

| # | 扩展点 | 路径 | 机制 |
|---|---|---|---|
| 1 | **专家库** | `src/octop/infra/agents/experts/library/<id>/` | `catalog.py` 启动扫描；`manifest.json` 定元数据；创建实例时把文件 seed 进工作区 |
| 2 | **子代理库** | `src/octop/infra/agents/subagents/library/{zh,en}/<division>/` | Markdown 定义 + frontmatter（`name`/`description`/`tools`） |
| 3 | **内置技能** | `src/octop/infra/agents/builtin_skills/` | `_builtin_skills` 根，seed 进**每个**专家的工区；当前只有 `skill-manager` |
| 4 | **连接器 / MCP** | `src/octop/infra/connectors/` | `custom_mcp.py` 支持 `stdio` 与 `streamable_http`；`catalog.py` 管 OAuth/MCP 目录项 |
| 5 | **插件** | `src/octop/infra/agents/plugins/bundled/` + `plugins/seed.py` | 随包分发，`plugin.yaml` 带 version，seed 只做升级刷新 |

### 2.3 专家包规范（数据，非代码）

```
<id>/
├── manifest.json      # id / label{zh,en} / description / welcome_message /
│                      # icon_name / color / prompt_files / quick_prompts / task_examples
├── SOUL.md            # 人格 + 安全边界（红线写这里）
├── AGENTS.md          # 操作规程 + 意图路由表
├── BOOTSTRAP.md       # 首次会话引导
├── USER.md            # 档案摘要（由脚本生成，只读）
├── agents/*.md        # 子代理（frontmatter: id/description/tools）
├── skills/<name>/SKILL.md   # 技能（frontmatter + metadata.octop 标签）
├── references/*.yaml|md     # 信源路由表等
└── scripts/*.py       # 档案/校验脚本
```

**关键差异（相对 PI Desktop）**：Octop 是服务端，**有完整终端、浏览器、文件系统能力**。PI Desktop 里"技能没有 shell 权限、脚本指令等于一句空话"的判断，在这里**不成立**——脚本能真正跑起来。这直接抬高了外部技能的可用度。

### 2.4 团队（AgentTeams）机制

`kind=team` 的主持人专家：轻量工具集（仅 `agent_list` + 异步 `ask_agent` + 记忆 + 时间），不挂文件系统/浏览器/搜索/MCP/技能。模板已是中文，且已确立「协调人不是执行人」「不得原样转发用户原话」的准则——**与本项目 MDT 主持人的定位天然吻合**。

### 2.5 上游已有的医学向资产（复用，不重造）

- `clinical-learning-subscription` 专家（基层医生指南学习向）——含 15 个技能、3 个信源路由 YAML、分级核验与"不做诊疗"安全域设计。**它的安全域写法与信源分级可直接移植给患者向专家。**

---

## 三、用户、场景与角色

| 角色 | 占比 | 主要场景 | 需要的能力 |
|---|---|---|---|
| **患者本人 / 家属**（主） | 高 | 病情梳理、报告解读、治疗选择的提问准备、并发症识别、营养心理、找试验 | MDT 专家 + 医学技能 + 四通道查询 |
| **社区志愿者 / 病友群管理员** | 中 | 回答群内高频问题、按规范产出科普、避免凭记忆答 | 运营技能 + 反幻觉护栏 |
| **社区运营**（内容/数据线） | 中 | 公众号内容、PDAC 情报日报、RAG 知识库维护 | 内容与情报技能 + FastGPT 同步 |
| **多社区承载**（延展） | 低 | 小铃铛（淋巴瘤）、小肺宝（肺癌）同平台 | 结构可复制，本期不做 |

**多用户自托管**是 Octop 的原生假设，患者各自独立账号、独立工作区、独立记忆，符合"病友数据不互相可见"的隐私要求。

---

## 四、已定决策（2026-10-01 确认）

| # | 决策项 | 决定 | 影响 |
|---|---|---|---|
| D1 | MDT 角色承载形态 | **专家库专家 + MDT 主持团队** | 每个角色是可 1:1 对话的独立专家，另建 1 个 `kind=team` 主持人编排会诊 |
| D2 | opencare-skillhub 技能范围 | **精选核心内置，分批入库** | 约 22 个，按医学/查询/运营三类；逐个标注来源+许可+适配方式 |
| D3 | UI 定制深度 | **品牌替换 + 患者向默认配置** | 保留上游页面结构，便于后续合并上游 |
| D4 | MCP 与四通道落地 | **npm 引用 + 本地服务内置** | 已发布 npm 的锁版本 npx 引用；`ctv-mcp-server` 本地源码内置为 stdio 服务；maskdesk 按脱敏插件/技能接，不当 MCP |

---

## 五、功能需求

### FR-1 UI：中文小胰宝版

| ID | 需求 | 验收标准 |
|---|---|---|
| FR-1.1 | 产品名改为 `xiaoyibao-octop` | `pyproject.toml`、`dashboard/package.json`、CLI 入口名一致 |
| FR-1.2 | 界面名称改为「小胰宝」 | `dashboard/index.html` 的 `<title>` 与 `apple-mobile-web-app-title`、`dashboard/public/manifest.json` 的 `name`/`short_name` 均为「小胰宝」 |
| FR-1.3 | 换 logo | 给定 logo（`picgo-1302991947.cos.ap-guangzhou.myqcloud.com/.../Pop Mart Character Front View (2).png`）替换 `dashboard/public/` 下 logo 资源；PWA 图标（192/512/apple-touch/favico）同步重生成 |
| FR-1.4 | 中文为默认语言 | 首次启动与未登录页默认 `zh`；`src/octop/i18n/zh.json` 与 `dashboard/src/locales/zh.json` 补齐小胰宝品牌词 |
| FR-1.5 | 患者向默认配置 | 新装实例默认加载 MDT 专家库；默认不暴露工程/运维向插件（`tetris`/`fun-facts`/`sports-scores` 等娱乐与开发类 bundled 插件默认关闭） |
| FR-1.6 | 品牌收口可核查 | 提供脚本列出所有残留 "Octop" 品牌串（白名单外应为 0） |

**边界**：不改上游页面结构与路由；不做导航裁剪（D3 的选择）。

### FR-2 技能入库

| ID | 需求 | 验收标准 |
|---|---|---|
| FR-2.1 | 精选约 22 个技能入库 | 见《设计文档》§4 清单；每个技能可被专家正常加载 |
| FR-2.2 | 每个技能带来源头 | 固定 frontmatter：`source_repo` / `source_license` / `adapted` / `readiness` |
| FR-2.3 | 脚本依赖改写 | 上游正文里「执行 `scripts/xxx.py`」的指令，三选一改写：转方法论 / 指向本项目已有 MCP 工具 / 明确标注降级。**不得保留无法执行的承诺** |
| FR-2.4 | 分类装载 | 医学/查询类进患者向专家；运营/内容类进运营向专家，互不串味 |
| FR-2.5 | 增量入库 | 分批交付，每批独立可验收；未入库的候选技能只在《技能评估清单》里列为待定 |
| FR-2.6 | `agent-taste-seed-system` 纳入 | 作为「美学大脑」配置类技能入库（来源与许可如实标注） |
| FR-2.7 | 许可台账 | 产出《技能许可台账》：逐仓库 `spdx_id` 实测值 + 是否可分发 + 待补 LICENSE 清单 |

### FR-3 MCP 接入

| ID | 需求 | 验收标准 |
|---|---|---|
| FR-3.1 | 五个 MCP 全部可被专家调用 | 逐个完成 `initialize` + `tools/list` 真实握手，工具数与上游 README 一致 |
| FR-3.2 | 版本锁定 | 一律锁具体版本，不用 `@latest`；实测记录握手返回的 `serverInfo.version` |
| FR-3.3 | 通道归类 | MCP 按四大通道归类，专家侧看到的是"通道能力"而非散装工具名 |
| FR-3.4 | 凭据不进仓库 | 需要 key 的（pubmed / metaso）走环境变量或本机配置，仓库内零凭据 |
| FR-3.5 | 降级可见 | 服务未装/未启时不静默失败，给出可执行的一句提示 |
| FR-3.6 | maskdesk 定位 | 作为**病历脱敏**能力接入（Apache-2.0），不包装成 MCP |

**五个 MCP 与实测信息**

| MCP | 形态 | 通道 | 许可 | 锁版本 |
|---|---|---|---|---|
| `chictr-mcp-server` | npm | chictr | Apache-2.0 | `2.0.2` |
| `mcp-pubmed-llm-server` | npm | 文献（辅助） | Apache-2.0 | `3.0.0` |
| `metaso-search-mcp` | npm | 通用检索（辅助） | Apache-2.0 | `1.1.2` |
| `@xiaoyibao_2025/dayi-mcp-server` | npm | 用药/疾病查询（辅助） | 仓库无 LICENSE ⚠️ | `0.1.7` |
| `ctv-mcp-server` | 本地源码 → stdio | **veeva** | MIT | 内置，未发布 npm |

> `dayi-search-mcp` 仓库无 LICENSE 但包已发布 npm（`npm view` 可取到 0.1.7）。因走 npm 引用而非再分发源码，许可风险较低，但仍需补 LICENSE 以正名。

### FR-4 MDT 专家体系

#### FR-4.1 专家名册（16 个专家 + 1 个主持团队）

**A 组 · 肿瘤核心 MDT（9）**

| # | 专家 id | 中文名 | 核心回答 |
|---|---|---|---|
| 1 | `xyb-mdt-surgery` | 胰腺外科 | 可切除性分档看什么、血管因素、围手术期准备 |
| 2 | `xyb-mdt-oncology` | 肿瘤内科 | 治疗线梳理、方案类别选择维度、分子分型对应方向 |
| 3 | `xyb-mdt-imaging` | 影像科 | 血管关系、分档依据、检查技术要求 |
| 4 | `xyb-mdt-pathology` | 病理科 | 取材方式对结论的限制、免疫组化与分子检测 |
| 5 | `xyb-mdt-intervention` | 介入科 | 血管介入、局部消融、TACE/HAIC、疼痛介入 |
| 6 | `xyb-mdt-radiation` | 放疗科 | 适用情形、技术维度、剂量与危及器官、与化疗顺序 |
| 7 | `xyb-mdt-nutrition` | 营养科 | 体重与进食评估、胰酶不足（PERT）、血糖、进食路径 |
| 8 | `xyb-mdt-psych` | 心理支持 | 情绪分级、危机信号优先、家属一侧 |
| 9 | `xyb-mdt-palliative` | 安宁疗护 | 症状维度、止痛顾虑、何时引入、意愿沟通 |

**B 组 · 精准与试验（2）**

| # | 专家 id | 中文名 | 核心回答 |
|---|---|---|---|
| 10 | `xyb-genomics` | 基因解读专家 | 读基因检测报告：字段→临床意义→可讨论方向；识别胚系/体系、可用靶点与"无靶点"两种结论 |
| 11 | `xyb-trial-matching` | 临床试验专员 | 按当前病情与既往治疗筛可选试验，讲清入排要什么、该问什么 |

**C 组 · 并发症与急症（5）** —— 对应你点名的六个方向

| # | 专家 id | 中文名 | 覆盖 |
|---|---|---|---|
| 12 | `xyb-acute-gi-bleeding` | 消化道出血 | 普外科/消化内镜止血视角；出血分级与就医阈值 |
| 13 | `xyb-acute-obstruction` | 肠梗阻 | 梗阻识别、减压/支架/手术的讨论维度 |
| 14 | `xyb-acute-biliary` | 胆道梗阻与引流 | **ERCP / PTCD** 的适用情形、减黄时机、术后护理 |
| 15 | `xyb-acute-infection` | 感染科 | 胆管炎、发热、腹腔感染、导管相关感染的识别与就医阈值 |
| 16 | `xyb-acute-hematology` | 血液科 | 贫血/血小板/中性粒细胞/血栓；治疗相关骨髓抑制 |

**主持团队（1）**

| 专家 id | 中文名 | 形态 |
|---|---|---|
| `xyb-mdt-chair` | MDT 会诊主持人 | `kind=team`，成员 = A/B 组按需组合 |

#### FR-4.2 角色护栏（硬性，逐条落进每个专家的 SOUL.md）

沿用姊妹项目已确立的定位——**这是"视角"，不是"会诊意见"**：

| ID | 需求 | 验收标准 |
|---|---|---|
| FR-4.2.1 | 措辞用「XX 视角」，不用「XX 专家认为」 | 专家输出模板里不得出现"专家认为/专家建议" |
| FR-4.2.2 | 产出是**问题清单**，不是结论 | 每个专家必含「可以问该科室医生的具体问题 3–5 条」 |
| FR-4.2.3 | 不出诊断、不分期结论、不给方案、不给用药 | 抽查 16 个专家的 SOUL.md 均含禁止条款 |
| FR-4.2.4 | 汇总呈现**分歧**，不平均成结论 | 主持人 AGENTS.md 明令禁止"综合各位意见，建议……"；必须有「各视角分歧点及原因」段 |
| FR-4.2.5 | 不推荐医院/医生、不做排名 | 全局红线，任何专家不得输出排序或推荐 |
| FR-4.2.6 | 摘要未提供的信息写「摘要未提供」 | 禁止凭经验补全 |
| FR-4.2.7 | 危机信号优先（心理科） | 出现自伤/自杀念头时，**第一行**给全国心理援助热线 12356 并要求联系主管医生；不淡化、不放文末；此类情况**不走 MDT 流程**，由主专家直接陪伴回应 |
| FR-4.2.8 | 安宁疗护先澄清定位 | 首段必须说明「姑息治疗 ≠ 临终关怀 ≠ 放弃抗肿瘤治疗」 |

#### FR-4.3 资源约束

| ID | 需求 | 说明 |
|---|---|---|
| FR-4.3.1 | 按需派发，不全开 | 主持人按问题选 2–4 个视角；仅当用户明确要求"从头到尾理一遍"才全开 |
| FR-4.3.2 | 专家库为模板 | 16 个是**模板**，只有被创建实例才占工作区；不预建 16 个实例 |
| FR-4.3.3 | 病人自述可脱敏 | 与 maskdesk 能力衔接，患者可先脱敏再投入 |

### FR-5 临床查询能力：四通道

**对齐要求**：与 PI Desktop（`xyb.trial-sources` 插件）已实测的工具语义保持一致，避免同一能力在两个端上参数不同。

| ID | 需求 | 验收标准 |
|---|---|---|
| FR-5.1 | 四通道可用 | clinicaltrials / chinadrugs / chictr / veeva 均可检索并取详情 |
| FR-5.2 | 通道统一抽象 | 对专家暴露统一入口（按通道选），四通道返回结构归一 |
| FR-5.3 | 故障与空值区分 | 「索引为空」「会话失效」「验证拦截」「确实 0 条」四态分别表达，**不得把故障说成结论** |
| FR-5.4 | 前置条件可见 | veeva 需先建索引、chinadrugs 需本人浏览器会话——未满足时给可执行提示，不误报 0 条 |
| FR-5.5 | 版本漂移防护 | chictr 锁 `2.0.2`（旧版参数不兼容，PI Desktop 已实测踩坑） |
| FR-5.6 | 与 MDT 专员协同 | `xyb-trial-matching` 专家的检索动作走四通道，不另起一套 |

**四通道对照**

| 通道 | 数据源 | 承载 | 前置条件 |
|---|---|---|---|
| **clinicaltrials** | ClinicalTrials.gov API v2 | npm `xiaoyibao-clinical-trials@1.0.0` | 无 |
| **chinadrugs** | 中国药物临床试验登记与信息公示平台 | 采集器 + 本地服务（Python 3 + requests + bs4） | **患者本人浏览器会话 Cookie**，落本机 `~/.xyb-chinadrugtrials/config.json`（0600） |
| **chictr** | 中国临床试验注册中心 | npm `chictr-mcp-server@2.0.2` | 首次需联网拉包 + Playwright Chromium（约 570MB）；站点可能触发人工验证 |
| **veeva** | Veeva CTV（`ctv.veeva.com`，GraphQL 公开无鉴权） | 本地 stdio 服务（源码内置） | **必须先建索引**（`import_csv_export` 或 `sync_sitemap`），否则等于空库；`robots.txt` 禁止抓 `/study-search`，故走本地索引 |

> **`clinicaltrials推送和订阅`（运营侧情报系统）不进本项目**：它是 TG/GeWe/飞书推送 + FastGPT 同步的运营系统，带 12+ 组生产密钥，不是查询来源。它对应的患者侧能力（"有更新提醒我"）由 veeva 的 watchlist 与 Octop 原生 cron 承担。

### FR-6 数据与隐私

| ID | 需求 | 验收标准 |
|---|---|---|
| FR-6.1 | 多用户隔离 | 复用 Octop 原生 JWT + 工作区隔离；患者间不可互访 |
| FR-6.2 | 最小化采集 | 不索取姓名/手机号/身份证/病历号；可用昵称 |
| FR-6.3 | 脱敏前置 | 提供 maskdesk 通路，支持 PDF/DOCX/MD 归一为 Markdown + 规则脱敏 + 打包导出 |
| FR-6.4 | 凭据本机化 | 会话 Cookie、API key 只落本机（0600），不进仓库、不回显、不进日志 |
| FR-6.5 | 数据不出机 | 默认不向公网发布患者数据；问卷类能力不发公网 |

---

## 六、非功能需求

| ID | 类别 | 要求 |
|---|---|---|
| NFR-1 | **可维护** | 尽量不改上游代码逻辑；扩展优先走"加数据（专家包/技能/配置）"而非"改代码（Python/React）"。改动点集中可枚举 |
| NFR-2 | **可合并上游** | 记录所有对上游文件的改动，形成 `XYB-UPSTREAM-DIFF.md`，便于日后跟版 |
| NFR-3 | **许可合规** | 产出许可台账；无 LICENSE 仓库**对外分发前必须补**；AGPL-3.0（`graphify-xiaoyibao`）若入库须独立标注传染性并落到发布流程 |
| NFR-4 | **来源可溯** | 医学结论标来源名称 + 年份；信源分级 A/B/C/D 沿用 |
| NFR-5 | **反幻觉** | 高可信来源命中不足 2 条时进「低证据模式」，只输出讨论要点与澄清问题 |
| NFR-6 | **性能** | 本地 stdio MCP 首个响应 < 2s；16 个专家**模板**不增加启动耗时（库扫描而非实例化） |
| NFR-7 | **可回归** | 每个阶段有可执行验证脚本；UI 改动有截图对照 |
| NFR-8 | **语言** | 患者向输出全程简体中文；禁止过程句（`I'll`/`Let me`/`Validation passed`）与检索日志外泄 |

---

## 七、内容红线（硬约束，继承并强化）

1. **不出诊断、不给处方** —— 不列药名组合、剂量、疗程、频次、给药途径；统一改「与医生讨论要点」
2. **不做医院/医生排名、不做患者推荐** —— 资助不购买结论
3. **未披露就说未披露** —— 机制、靶点、数据缺失时明写，**禁止推断**
4. **统计学边界** —— 跨试验/跨人群/跨瘤种数据不可外推；多瘤种池数据不得机械外推到亚组
5. **不做生存期预测** —— 不判断进展速度与剩余生存时间
6. **早期数据标层级** —— I 期 n=30 的 ORR 不等同 III 期结论
7. **区分注册节点与临床结果** —— IND 受理/获批临床不算疗效进展
8. **不做煽情/戏剧化修辞** —— 客观事实化措辞
9. **术语科普** —— 每术语一行、约 20 字通俗解释
10. **风险提示** —— 医学输出须带「不替代医生诊断」标识

---

## 八、不在本期范围

| 项 | 原因 |
|---|---|
| `clinicaltrials推送和订阅` 运营系统 | 12+ 生产密钥，属运营侧；患者侧能力已由 watchlist + cron 覆盖 |
| 全量 38 仓库技能 | 含 897/178/76 个技能的聚合池与开发基建，会稀释约束 |
| 跨社区（小铃铛/小肺宝） | 结构可复制，本期不做 |
| CDE 平台直连 | 公开检索能力有限 |
| 深度患者门户改造 | D3 选择保结构；导航裁剪列为后续候选 |
| 公网发布问卷（HADS） | 保持本机版 |

---

## 九、待决事项（需你决策，不阻塞文档确认）

| # | 事项 | 说明 |
|---|---|---|
| 1 | **专家数量是否收敛** | 16 个专家模板是否偏多？可选的收法：把 C 组 5 个急症合为 1 个「并发症与急症」专家（16 → 12） |
| 2 | **`graphify-xiaoyibao`（AGPL-3.0）是否入库** | 入库即引入强 copyleft。PI Desktop 已决定接入并单独标注；本项目是否同样处理 |
| 3 | **无 LICENSE 仓库补许可** | 约 12 个候选（含 `Medical-Record-Organizer`、`clinical-trial-matching`、`skill-HADS-accessment`）需补，否则对外分发说不清 |
| 4 | **组织归属与推送目标** | 改造成果推回 `opencare-skillhub/xyb-Octop` 还是新建仓库 |
| 5 | **部署形态** | 单机自托管 / 团队服务器 / 容器；决定 `.env` 与 DB 选型建议 |
| 6 | **CTV 索引重建** | 是否执行「备份旧库 → 按新 schema 重建 → 导入现有 CSV」（要动 `~/.ctv-mcp/`） |
| 7 | **病人自述采集模板** | MDT 需要"案情摘要"输入；是否引入 PI Desktop 的九段采集表作为标准输入 |
| 8 | **面具/形象资源** | 除给定 logo 外是否需要专家头像（16 个专家各一张） |

---

## 十、验收标准（整体）

| # | 验收项 | 判定方式 |
|---|---|---|
| 1 | 品牌替换无残留 | 品牌扫描脚本输出白名单外 0 条；UI 截图对照 |
| 2 | 技能入库可用 | 抽查技能能被对应专家加载并按其 SKILL.md 流程执行 |
| 3 | 五个 MCP 握手成功 | 逐个跑 `initialize` + `tools/list`，留实测输出 |
| 4 | 四通道检索可用 | 四通道各跑一次真实检索，留结果 |
| 5 | MDT 专家可 1:1 对话 | 任选 3 个专家建实例并对话，产出符合"问题清单"格式 |
| 6 | MDT 主持团队可编排 | 发起一次含 3 个视角的会诊，产出含「分歧点」段 |
| 7 | 护栏生效 | 对每个专家做越界提问（要处方/要排名/要生存期），全部正确拒绝 |
| 8 | 许可台账完整 | 每个入库技能都有 `spdx_id` 实测值与可分发判定 |
| 9 | 上游差异可枚举 | `XYB-UPSTREAM-DIFF.md` 完整 |

---

## 附：主要事实来源

- 仓库结构、扩展点、团队机制：`/Users/qinxiaoqiang/Downloads/xyb-octop` 逐文件实测
- 许可证：`gh api repos/<owner>/<repo> --jq .license.spdx_id` 逐仓库实测（2026-10-01）
- npm 版本：`npm view <pkg> version` 实测
- MDT 视角设计基线：`xiaoyibao-pi-desktop/XYB-MDT.md`、`subagents/README.md`
- 四通道接入基线：`xiaoyibao-pi-desktop/XYB-TRIAL-SOURCES.md`
- 技能库评估基线：`xiaoyibao-pi-desktop/XYB-SKILLHUB.md`
