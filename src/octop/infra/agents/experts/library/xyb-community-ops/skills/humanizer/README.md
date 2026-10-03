# 小胰宝 Humanizer

面向中文医学科普、患者教育、社区内容、专家观点整理以及中英文内容的 Humanizer Skill。

> 当前版本以 `SKILL.md` 的版本头为准，变更历史见 [`CHANGELOG.md`](./CHANGELOG.md)。
> 本 README 不写死版本号，避免出现第三个会漂移的版本来源。

## 设计目标

它不是"AI 检测器规避器"。核心目标是：

> **自然度 + 作者感 + 医学可信度 + 对读者的尊重。**

尤其强调：**不能靠恐吓、羞耻、灾难化语言或虚假紧迫感来提高读者注意力。**

## 核心原则

1. 事实不可动。
2. 证据等级不可升级。
3. 不伪造个人经历、专家观点或引用。
4. 不用恐吓提高注意力。
5. 不制造虚假希望。
6. 不为了 AI detector 而牺牲自然度和准确性。
7. 尊重读者，把复杂问题讲清楚，而不是替读者制造情绪。

完整清单见 `SKILL.md` 的 NON-NEGOTIABLE RULES。

## 参考文件怎么加载

`SKILL.md` 的 Workflow 一节规定先按任务类型加载参考，避免每次都把所有文件读进来：

| 场景 | 加载 |
|---|---|
| 中文改写 | `references/ai-tells-zh.md` |
| 英文改写 | `references/ai-tells-en.md` |
| 医学、药物、临床试验、患者教育 | `references/medical-writing.md`、`references/fear-free-communication.md` |
| 清单／速查类文章（一次列多条试验、多个药物、多家中心） | `references/checklist-articles.md` |
| 指定 Sam／小胰宝风格 | `references/voice-sam.md` |
| 指定其他 Voice | 对应 `voice-*.md`；文件不存在时停下并请用户提供语料，不得悄悄回退到 Sam Voice |

## 使用模式

- `light`：只修明显 AI 味，尽量不动结构。
- `standard`：默认；重构模板化表达、节奏和连接方式。
- `deep`：两轮编辑，再做医学和 Voice 审稿。
- `audit`：只诊断，不重写；用 `workflows/audit.md`。

未指定时按 `standard`。多条目清单稿在 `standard` 基础上额外加载 `checklist-articles.md`。

## Voice：支持自定义作者风格

Humanizer 不应该把所有文章改成同一种"人味"，因此支持 Voice Profile。

优先级：当前任务明确指定的声音 > 项目级 `VOICE.md` / Voice Profile > 用户指定的 `voice-*.md` > `references/voice-sam.md` > 小胰宝默认声音。

### 最简单的用法

在 `references/` 下创建 `voice-yourname.md`，然后在提示中说：

```text
使用 voice-yourname 风格，standard 去 AI 味。
```

### 更推荐的做法

准备 5–10 篇你真正喜欢、并且确实代表自己写作习惯的文章。**不要只提供一篇。**

让 Agent 分析：句子长短、段落节奏、常用词、不喜欢的词、专业程度、判断是否直接、如何表达不确定性、如何写结论、是否使用第一人称、口语程度、幽默程度。

**不要让模型复制原文句子。** Voice Profile 应该描述稳定的写作规律，而不是保存可直接拼接的句库。生成后由作者人工校正，再用盲测重跑 Benchmark。

### 项目级 Voice

如果这个 Skill 用在项目中，可以放一个 `VOICE.md`，或 `references/voice-project.md`。

如果用户明确指定了 `--voice custom` 或其他名称但文件不存在，Skill 会提示创建 Voice Profile，不会默默套用 Sam 风格，也不会仅凭一篇文章伪造完整作者画像。

示例：

```text
/humanize --voice sam
/humanize --voice my-voice
/humanize --voice community
```

## 目录结构

```text
xiaoyibao-humanizer/
├── SKILL.md                  主文件：版本头、NON-NEGOTIABLE RULES、Pass A–G、Voice、Modes、Trigger
├── README.md                 本文件：定位、用法、维护约定
├── CHANGELOG.md              变更记录，每次改动顶端加一条
├── check-version.sh          校验 SKILL.md 版本头与 CHANGELOG 顶部条目是否一致
├── .gitignore
├── _user_meta.json           由 WorkBuddy 维护的安装元信息，不要手改
├── references/
│   ├── ai-tells-zh.md            中文 AI 痕迹诊断（十三节）
│   ├── ai-tells-en.md            英文 AI 痕迹诊断
│   ├── medical-writing.md        医学事实、证据层级、招募状态写法
│   ├── fear-free-communication.md 无恐吓医学沟通规范
│   ├── checklist-articles.md     清单／速查类文章的体例规则
│   ├── voice-sam.md              Sam／小胰宝默认 Voice Profile
│   └── voice-profile.md          自定义作者声音的方法
├── workflows/
│   ├── article.md            文章改写流程
│   ├── community.md          患者／社区内容流程
│   ├── medical.md            医学内容流程，事实完整性优先于文风
│   └── audit.md              只审不改，含 1–5 分打分维度
└── evals/
    ├── README.md
    ├── benchmark.md              第一轮 20 篇 Benchmark 方案
    ├── run_benchmark.py
    ├── voice-analysis-v0.1.md
    ├── dataset/                  benchmark 与 voice 语料
    ├── prompts/                  盲测与对比用提示词
    ├── red-team/                 回归测试用例
    └── results/v0.3/             冻结基线结果
```

## 维护

### 版本规则

改动 `SKILL.md` 或 `references/` 下的实质内容时，**两件事必须同时做**：

1. 把 `SKILL.md` 版本头的 `vX.Y.Z` 升一位；
2. 在 `CHANGELOG.md` **顶部**加一条，写清改了哪个文件、以及依据是哪一次实改。

只改版本号不记 CHANGELOG（或反过来）会造成版本记录脱节。本技能历史上出现过两次：v0.4.3 被两条并行改动线同时占用；`SKILL.md` 升到 v0.4.5 而 CHANGELOG 仍停在 v0.4.4。

纯错别字或格式修正可以不升版本号，但仍建议在 CHANGELOG 记一行。

### 提交前自查

```sh
./check-version.sh
```

- 一致 → 输出 `OK`，退出码 0；
- 不一致 → 列出两个版本号并给出修改建议，退出码 1；
- 版本号解析不到 → 提示跳过，退出码 0。

想挂成提交钩子（不一致时会阻断提交，可用 `--no-verify` 跳过）：

```sh
ln -sf ../../check-version.sh .git/hooks/pre-commit
```

### git 工作流

本目录是独立仓库，默认分支 `main`。

```sh
git log --oneline              # 改过哪些版本
git show <commit>              # 某次改了什么
git diff HEAD -- references/ai-tells-zh.md   # 未提交的改动
git restore <file>             # 丢弃某文件的未提交改动
git revert <commit>            # 回退某次提交（生成新提交，安全）
```

### 多会话并行修改的风险

本技能曾被多个会话同时修改，因此：

- **仓库只在本地，没有远端**。它给的是回溯和 diff 能力，机器上的目录若被整体删除，git 也保不住；需要异地备份就加远端。
- **git 不能阻止版本号撞车**。真正有效的是约定：技能改动尽量只在一个会话里做，或每完成一处就提交。
- 若 A 会话改了文件还没提交，B 会话执行 `git add -A` 会把 A 的半成品一起卷进自己的提交。提交前先看一眼 `git status`。

## 推荐测试方法

不要只看 AI detector。第一轮建立并冻结 20 篇 Benchmark：

- 中文医学科普 5 篇；
- 中文患者／社区文章 5 篇；
- 中文一般文章 5 篇；
- 英文文章 5 篇。

每篇做：

```text
A 原文
B 普通 Humanizer
C Xiaoyibao Humanizer
D 真人编辑
```

盲测自然度、作者感、医学准确性、证据校准、恐吓倾向、意义保留等指标。

特别加入真人文章做 Human Preservation Test，防止 Humanizer 把真正的人类文字也改成统一模板。

硬性 Gate：医学准确性 < 4、意义保留 < 4 或恐吓控制 ≤ 2，均判定失败。

## 版本沿革

只列里程碑；从 v0.4.1 起进入逐版微调阶段，逐条记录见 `CHANGELOG.md`，本文件不再重复。

- **v0.3**：建立英文痕迹、无恐吓沟通、医学写作与 Voice 参考；第一轮 20 篇 Benchmark、评分加权与硬性 Gate、9 类 18 个红队案例成型。
- **v0.4**：`ai-tells-zh.md` 从 6 类扩到 11 类，补标题功能标签腔、编辑腔动词、术语腔复合名词、emoji 分类、患者措辞生硬、未上市药物措辞越界、Footer 盲区、同一要点多处重复；`voice-sam.md` 补 Headings 与 Footer 章节。
- **v0.4.1 及以后**：补署名与隐私规范，逐步补清单／速查类稿件的体例（新增 `checklist-articles.md`）、meta 引导句、总结式话术与命令式叮嘱等。当前版本见 `SKILL.md` 版本头。
