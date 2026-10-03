---
name: trial-search
description: 当需要在四个临床试验通道（ClinicalTrials.gov、中国药物临床试验登记与信息公示平台、ChiCTR、Veeva CTV）检索试验时使用。定义检索顺序、关键词构造、四态故障判定与结果归一，确保「查不到」不被说成「没有」。Use when searching any of the four clinical-trial channels, especially to distinguish a channel failure from a genuine zero result.
metadata:
  octop:
    emoji: "🔎"
    label:
      zh: "四通道试验检索"
      en: "Four-Channel Trial Search"
    summary:
      zh: "按通道检索并归一结果；故障四态必须分清，不得把故障说成结论。"
      en: "Search the four channels and normalise results; never report a failure as a finding."
---

# 四通道试验检索

## 一、四个通道与各自的前置条件

| 通道 | 数据源 | 载体 | 前置条件 | 说明 |
|---|---|---|---|---|
| **clinicaltrials** | ClinicalTrials.gov API v2 | MCP | 无 | 全球登记，英文为主，信息最全 |
| **chictr** | 中国临床试验注册中心 | MCP | 首次需拉包；站点可能**触发人工验证** | 国内注册试验；遇验证需本人完成，**不绕过** |
| **veeva** | Veeva CTV（ctv.veeva.com） | MCP | **必须先建本地索引** | 未建库时等于空库，**不是没有数据** |
| **chinadrugs** | 中国药物临床试验登记与信息公示平台 | **技能**（`chinadrugs-collect`） | **患者本人浏览器会话** | 国内药物临床试验，中文；**不是 MCP 通道**，由技能用会话驱动 |

**顺序建议**：先 `clinicaltrials`（无前置条件，最快确认检索本身是否正常），再 `chictr` 与 `chinadrugs`（国内可及性），最后 `veeva`（需已建索引，用于补充与订阅变更）。

### 工具名（照抄，不要猜）

| 通道 | 调用方式 |
|---|---|
| clinicaltrials | `search_clinical_trials` / `get_trial_details` / `search_by_location` |
| chictr | `search_trials` / `get_trial_detail` |
| veeva | `search_studies` / `get_study_detail` / `create_watchlist` / `run_watchlist` |
| chinadrugs | 不是工具：按 `chinadrugs-collect` 技能的流程执行 |

**看到上游文档里的 `mcp__oncology_db__*` 或 `mcp__chictr__*` 一律忽略**——那是别的环境的名字，本项目不存在。

## 二、检索词构造

从案情摘要里取四类信息组合：

1. **疾病**：`pancreatic cancer` / `pancreatic ductal adenocarcinoma` / `PDAC` / `胰腺癌`（中英文都要试）
2. **分子标志**：`KRAS G12D`、`CLDN18.2`、`B7-H3`、`MSI-H`、`dMMR`、`BRCA`、`NTRK`、`HER2`，以及「不限靶点」的广谱检索
3. **治疗阶段**：`first-line` / `second-line` / `pretreated` / `advanced` / `metastatic` / `neoadjuvant` / `adjuvant`
4. **地域**（如需要）：`China`、具体城市

**逐步放宽的顺序**：标志 + 阶段 → 疾病 + 标志 → 疾病 + 阶段 → 仅疾病。每放宽一次都要说明放宽了什么、为什么。

## 三、故障四态（硬性）

**这是本技能最要紧的一条：检索失败绝不能被表述成「没有相关试验」。**

| 态 | 触发 | 对患者的话术 |
|---|---|---|
| **索引为空** `INDEX_EMPTY` | veeva 返回索引未建 | 「本地还没建库，需要先导入一次数据」——**不是**「没有相关研究」 |
| **会话失效** `NO_SESSION` | chinadrugs 返回反爬挑战页 / 无会话 | 「会话过期了，需要重新提供浏览器会话」——**不是**「0 条结果」 |
| **验证拦截** `CHALLENGED` | chictr 返回验证页 | 引导本人完成站点验证（**不绕过**）；本人不在场就如实说这次查不到 |
| **确实 0 条** `EMPTY` | 正常响应且结果为空 | **按通道分别说**：「<通道名>里没检索到匹配的试验」；只有四个通道都返回正常且都为空，才能说「四个通道目前都没检索到」。否则必须写明哪个通道查了、哪个没查 |

输出前自检：

1. 每个通道分别返回了什么状态？有没有把 `INDEX_EMPTY` / `NO_SESSION` / `CHALLENGED` 写成「没有」？
2. 如果某个通道没查，是不是明说了「本次未检索该通道」而不是让它看起来像 0 条？
3. 说「0 条」时，是**逐通道**说的，还是把某一个通道的空结果扩大成了四个通道？
3. 检索条件放宽过几次？每次放宽了什么？

## 四、结果归一

每条候选试验统一输出这些字段：

```
登记号：<NCT… / CTR… / ChiCTR… / Veeva UTN…>（通道：<哪个通道>）
标题：<原文标题 + 中文要点>
分期与状态：<I/II/III 期> · <招募中 / 未开始 / 已暂停 / 已完成 / 状态未知>
干预：<药物或干预类别，不写剂量>
关键入组条件：<逐条翻译成日常说法>
关键排除条件：<同上>
中心地点：<国家 / 城市；中国中心要标出>
你可能不确定的点：<逐条列出>
```

**「你可能不确定的点」这一栏不能空着。** 患者往往不知道自己是否符合某条入排，这一栏就是告诉他去问什么。

## 五、联系研究团队要问的问题（固定给 5–7 条）

1. 以我的分期、既往治疗线数和基因结果，我是否符合这个试验的入组条件？
2. 有哪些入排条款需要我补充资料才能判断？
3. 参加需要往返几次、每次大概多久？外地患者怎么安排？
4. 试验分哪个组是随机的吗？如果分到对照组，会接受什么治疗？
5. 试验期间的费用哪些由研究承担、哪些需要自付？
6. 如果治疗期间病情进展，接下来有什么安排？
7. 我可以同时咨询其他试验吗？需要间隔多久？

## 六、红线

- ❌ 不判断患者能否入组（那是研究团队的评估）
- ❌ 不推荐「应该参加哪个试验」
- ❌ 不把故障说成结论
- ❌ 不承诺疗效，不把早期试验说成希望
- ❌ 不替患者联系研究团队或提交资料
- ✅ 每条结果都要带登记号与来源通道，便于患者和医生核对
