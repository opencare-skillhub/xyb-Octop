---
name: trial-matching-advanced
description: 当需要的不是「列出试验」而是**逐条判断符合性**时使用：把患者条件与每个试验的入排标准逐项对照，输出通过/待确认/不符合及原因，并给出该向研究团队确认的问题。**不给入组结论**，也不在没有真实登记号时编造编号。Use for item-by-item eligibility analysis against real registry records.
metadata:
  octop:
    emoji: "🔬"
    label:
      zh: "入排逐条对照"
      en: "Eligibility Item Analysis"
    summary:
      zh: "把患者条件与试验入排逐条对照，标注通过/待确认/不符合及原因。"
      en: "Compare the patient against each eligibility criterion, item by item."
source_repo: opencare-skillhub/clinical-trial-matching
source_license: NONE
declared_license: MIT
adapted: 2026-10-02
readiness: 需改写（上游用自己的检索通道；本项目改为调用已配置的四通道工具，不新增依赖）
---
> ## 与 `trial-search` 的分工（优先级高于本文其余内容）
>
> 本技能**只做逐条对照**，不自己检索。顺序固定：
>
> 1. 先用 `trial-search` 通过四通道工具取得**真实登记记录**；
> 2. 再用本技能把患者条件与每条记录的入排标准逐项对照；
> 3. 输出「通过 / 待确认 / 不符合」三态与原因，**不给入组结论**。
>
> - **没有真实登记号（NCT / CTR / ChiCTR / Veeva UTN）的记录一律不得出现在结果里**；宁可说「本次未取得可核验记录」。
> - 上游正文里提到的自有检索接口在本项目**不使用**；一律走平台已配置的四通道工具。
> - 通道故障（索引为空 / 会话失效 / 验证拦截）必须如实说明，不得当成「没有匹配试验」。
>
> ### 工具名对照（上游名字在本项目不可用）
>
> | 上游正文写的 | 本项目实际可用的 |
> |---|---|
> | `mcp__oncology_db__search_trials` | 通道 `clinicaltrials`（工具 `search_clinical_trials`） |
> | `mcp__chictr__search_trials` | 通道 `chictr`（工具 `search_trials`） |
> | —（上游没有） | 通道 `veeva`（工具 `search_studies`） |
> | —（上游没有） | 中国药物临床试验登记平台：走 `chinadrugs-collect` 技能，不是工具 |
>
> 正文 `## References` 里列的 `chictr-search-guide.md` / `egfr-tki-resistance.md` / `kras-g12c-landscape.md` 本次**未随包导入**（与胰腺癌场景无关或已有专门技能），看到这些文件名时不要去找文件。


# CancerDAO Clinical Trial Matching

End-to-end oncology clinical trial matching that generates decision-grade reports for patients by coordinating dual-source retrieval (ClinicalTrials.gov + ChiCTR) with structured eligibility analysis.

> ⚠️ **免责声明**：本工具仅提供信息匹配服务，不构成医疗建议。所有入组决策须由各试验机构临床研究团队审核。

## When to use

触发以下任一场景时激活本技能：

- "找临床试验"、"临床入组"、"匹配试验"
- "trial matching"、"clinical trial"、"NCT"、"ChiCTR"
- 提供癌症诊断 + 基因突变 + 治疗史，请求试验选项
- 患者说"耐药了想找试验"、"靶向药失效了怎么办"

**禁止**：在无法验证真实招募状态时编造 NCT/ChiCTR 编号。

**ChiCTR 查无结果时**：若 `mcp__chictr__search_trials` 返回空，按以下顺序回退：
1. 换用单 token 简化关键词重试（如"胰腺癌"→"BRCA"）
2. 回退到 ClinicalTrials.gov（用 `mcp__oncology_db__search_trials`）并附加中文适应症描述
3. 终级方案：用 WebSearch 搜索 `site:chictr.org.cn [疾病] [突变]` 并验证注册号格式（ChiCTR-XXX-XXXXXX）

## Workflow


### Step 1 — 患者信息提取

从用户输入中提取结构化患者档案，必填字段：
```json
{
  "cancer_type": "NSCLC | CRC | PDAC | breast | gastric | ...",
  "stage": "IV | III | II | I",
  "mutations": ["EGFR L858R", "KRAS G12C", ...],
  "treatment_history": [{"line": 1, "regimen": "...", "outcome": "PR|SD|PD"}, ...],
  "prior_therapies": ["奥希替尼", "帕博利珠单抗", ...],
  "ecog": "0-4"
}
```

参考：`references/oncology-db-mcp-api.md` 查看可用基因/靶点覆盖范围。

### Step 2 — 生成 8 维搜索计划


创建 8 个搜索维度（参考：`references/trialgpt-methodology.md`）：
1. **疾病+突变特异** — e.g. `NSCLC EGFR T790M`
2. **泛实体瘤** — e.g. `solid tumor KRAS G12C` (basket trials)
3. **联合靶点** — e.g. `KRAS G12C cetuximab`
4. **通路/耐药策略** — e.g. `RAS-ON inhibitor`, `pan-KRAS`
5. **exhaustive 药物名称** — 所有研究中的 + 已批准的同靶点药物
6. **细胞治疗** — CAR-T, TIL, TCR-T
7. **免疫（后PD-1）** — bispecific, LAG-3, TIGIT
8. **中文关键词（ChiCTR）** — 单 token 查询（ChiCTR 分词器较脆弱）

### Step 3 — 双源检索


**ClinicalTrials.gov** — 通过 `mcp__oncology_db__search_trials`：
```python
mcp__oncology_db__search_trials(query="KRAS G12C NSCLC", status="RECRUITING")
```

**ChiCTR** — 通过 `mcp__chictr__search_trials`：
```python
mcp__chictr__search_trials(keyword="结直肠癌 KRAS G12C", max_results=20)
mcp__chictr__search_trials(keyword="胰腺癌 BRCA", max_results=20)
```

详见：`references/chictr-search-guide.md`

### Step 4 — 验证招募状态 + 可行性评分


对每个候选试验：
- 验证 NCT ID 真实性（绝不虚构）
- 5 维可行性评分：招募状态、地理可及性、时间成本、经济成本、槽位可用性
- 过滤至 top candidates

### Step 5 — 逐试验 eligibility 分析


对每个候选试验评估：
1. **入排标准匹配** — 逐条 vs 患者档案
2. **风险注释** — 关键耐药机制（EGFR TKI 耐药：C797S 顺式/反式突变、MET 扩增、KRAS G12C 耐药：继发 RAS/MAPK 通路激活；详见 references/egfr-tki-resistance.md）
3. **疗效上下文** — 试验疗效 + vs 标准治疗


### Step 6 — 决策合成



输出：
- Top-N 匹配路径（按可行性 + 多样性，不按"推荐"排名）
- 每试验"匹配理由"（禁止数值评分）
- 自助联系信息（研究者/中心信息，供患者自行联系）
- Goals-of-Care 触发（3rd+ 线或预测 OS <12 个月时，提示缓和护理选项）

### Step 7 — HTML 报告


生成自包含 HTML 报告（优先路径：`~/Downloads/临床试验匹配报告_{date}.html`；若 Downloads 不可写则输出到当前工作目录）。报告须包含完整 disclaimer，无外部资源依赖。

## 合规规则（硬编码 — 违反 = bug）

### Forbidden（输出中绝对不出现）

| 类别 | 禁止 | 替代 |
|---|---|---|
| 数值评分 | "9.2/10"、"匹配度 85%"、"得分 73"、任何 N/M 或 N% 的形式给试验打分 | 用"匹配理由"叙述符合点 + 不符合点 |
| 排名词 | "Top 1 试验"、"最适合"、"最优选择" | "符合的试验"（不排序）+ 按地理/瘤种/线数分组 |
| **"推荐"一词** | "推荐 NCT0xxx"、"推荐 XX 试验"、"我推荐"、"建议你参加 XX" | "符合入排标准的试验"、"匹配点和不匹配点如下"、"可以和医生讨论的选项" |
| 虚构 ID | 编造 NCT 编号、ChiCTR 编号、PI 联系方式 | 只输出经 live API（`mcp__oncology_db__search_trials` / `mcp__chictr__search_trials`）验证的真实 ID |
| 直接入组指令 | "你可以联系 XX 报名"、"你符合，去打这个电话" | "如希望进一步评估入组，请将本报告交给主管医生联系研究中心" |

⚠️ **"推荐"是关键禁词**。原因：在中国医疗法规下，AI 输出"推荐 XX 试验"会被认定为构成医疗建议，超出工具定位。中文同义词全部禁用——"推荐 / 建议你参加 / 我建议 / 强烈建议 / 优先选择 XX"全部触发 bug。

### Mandatory（输出中必须出现，位置固定）

1. **报告顶部第一行**（在任何分析内容之前）：
   ```
   ⚠️ 本报告由 AI 信息匹配工具生成，不构成医疗建议。入组与否由各试验机构临床研究团队独立审核。
   ```

2. **报告底部固定 footer**：
   ```
   ───────────────────────────────────────────────────────────
   📋 报告生成信息
   - 生成时间：<ISO timestamp>
   - 数据源：ClinicalTrials.gov | ChiCTR | 验证状态：<每个 ID 的验证 ✓/✗>
   - 工具版本：clinical-trial-matching v2.0
   ───────────────────────────────────────────────────────────
   ⚠️ 所有治疗决策必须与主诊医生确认。匹配 ≠ 符合入组标准，最终以研究中心预筛结果为准。
   ```

3. **每条试验条目**必须包含：
   - NCT/ChiCTR ID（带 ✓ 验证标记）
   - 主要入选标准（逐条 vs 患者档案，用 ✓/⚠️/✗ 标注）
   - 主要排除标准（逐条评估）
   - 触发的 R 规则（见下方）— 若有
   - 中心信息（如果 live API 返回了）

## R1-R5 规则触发标记（显式化、可观测）

eligibility 分析（Step 5）每命中下列任一规则，**必须在该试验条目里显式输出规则名称 + 降级原因**——不允许只在内部判断而不在输出里写。这样未来 eval 可以直接 grep `R1`/`R2`/`R3`/`R4`/`R5` 验证规则触发率。

| 规则 ID | 触发条件 | 降级到 | 输出格式 |
|---|---|---|---|
| **R1** | 试验排除"已使用过同类机制药物" AND 患者用过该类（例：抗血管生成、KRAS G12Ci、EGFR TKI、抗 PD-1） | `conditional`（条件匹配） | `[R1 触发 · 同类药物历史] 试验排除曾用 <同类药物>，患者已用过 <具体药物>。降级为 conditional，需机构审核。` |
| **R2** | 试验限定治疗线数（如 "2L only"）AND 患者已完成线数超出 | `conditional` 或 `excluded` | `[R2 触发 · 治疗线数错配] 试验限 <X-Y> 线，患者已完成 <N> 线。若硬限 → excluded；若软限 → conditional。` |
| **R3** | 试验主要扩展瘤种与患者瘤种不一致（如试验主招 BRCA 卵巢癌/乳腺癌，患者为结肠癌） | `conditional` | `[R3 触发 · 适应症错配] 试验主要瘤种为 <X>，患者为 <Y>，理论符合但非主招方向。降级为 conditional。` |
| **R4** | 试验要求器官功能指标 AND 患者在边界值或不达标（例：要求 eGFR ≥ 60，患者 58.9） | `conditional` 或 `excluded` | `[R4 触发 · 器官功能边界] 试验要求 <指标 ≥/≤ X>，患者 <当前值>。距离边界 <Δ>。若边界 ±10% 内 → conditional；超出 → excluded。` |
| **R5** | eligibility 逐条评估存在 ≥ 2 个关键标准信息缺失（用户档案中没有该字段） | `conditional` + 列出缺失项 | `[R5 触发 · 关键信息缺失] 以下 <N> 项无法判断：<逐条列出>。降级为 conditional，建议补充信息后再评估。` |

### R 规则的渲染规范

- 每条命中规则的试验，**必须**在 eligibility 表格下方加一个 markdown callout：

  ```
  > **触发的合规规则**
  > - [R1 触发 · 同类药物历史] ...
  > - [R3 触发 · 适应症错配] ...
  ```

- 没触发任何规则的试验也要显式标注：`> 触发的合规规则：无 (R1-R5 均未命中)`——便于 eval 验证"未漏报"。

## Goals-of-Care 触发：必须提及缓和护理选项

当下列任一条件成立时，**报告末尾**必须独立出一个"缓和护理选项"块（不能省略，不能合并进试验列表）：

- 患者完成 ≥ 3 条治疗线（含当前线）
- ECOG ≥ 3
- 预测 OS < 12 个月（从治疗线数、瘤种、特殊预后基因判断）
- 患者主动提及"治不动了"/"想停下"/"不想再试了"

固定块格式：

```
═══════════════════════════════════════════
🤝 缓和护理选项（Goals-of-Care 触发原因：<列出触发条件>）
═══════════════════════════════════════════

匹配试验不是唯一选择。在你目前的阶段，下面这些也值得和医生讨论：

1. 缓和医疗（palliative care）门诊 — 不等于放弃治疗，是症状管理 + 生活质量优化
   早期接入已被证明能延长生存（Temel et al., NEJM 2010）
   推荐查找：本地三甲医院"安宁疗护科"或"缓和医疗科"

2. 疼痛专科 — 如果有疼痛或睡眠问题
3. 心理支持 — 患者本人 + 家属同样需要
4. 营养支持 — 维持体能是后续治疗的前提
```

不允许：跳过这一块直接给试验。Goals-of-Care 触发后这一块**永远在试验列表之前出现**。

## 罕见突变 / 无匹配试验的替代策略（必须输出）

当 eligibility 分析后 **0 个试验**符合（或仅有 conditional 匹配且全部高风险）时，**不允许**简单回"未找到匹配试验"。必须给出至少 3 条替代策略：

1. **篮子试验/伞式试验**：搜索按机制（而非瘤种）招募的试验，例如 NCI-MATCH、TAPUR、NCI-MPACT、KEYNOTE-158（TMB-H）。给出至少 1 条具体 NCT ID。
2. **专科中心 / 国家罕见肿瘤中心**：中国境内具体名单——CAMS 罕见肿瘤中心、复旦肿瘤医院罕见肿瘤 MDT、北京大学肿瘤医院（如适用）。
3. **文献查询路径**：PubMed 关键词组合 + ASCO/ESMO 大会 abstract 检索方式（给出具体 query 示例）。

固定块格式：

```
═══════════════════════════════════════════
🔍 0 匹配 / 罕见情形 — 替代策略
═══════════════════════════════════════════

1. 篮子/伞式试验（按机制招募，不按瘤种）：
   - <具体 NCT ID 1> — <机制/标的>
   - <具体 NCT ID 2> — <机制/标的>

2. 罕见肿瘤专科中心：
   - <中心名称> · <科室> · <城市>
   - ...

3. 文献检索 query 示例：
   - PubMed: "<gene> <mutation>" AND "<cancer> rare" AND "(case report OR clinical trial)"
   - ASCO abstract: site:meetinglibrary.asco.org "<gene>" "<cancer>"
```

## 数据来源

| 来源 | 工具 | 覆盖 |
|---|---|---|
| ClinicalTrials.gov | `mcp__oncology_db__search_trials` | 全球试验，NCT IDs |
| ChiCTR | `mcp__chictr__search_trials` | 中国试验，ChiCTR IDs |

## 常见错误

| 错误 | 正确做法 |
|---|---|
| 编造 NCT ID | 只通过 live API 验证后输出真实 ID |
| 用"推荐"排名 | 用"匹配理由" + 可行性评分描述 |
| 忽略耐药机制 | 查阅 `references/egfr-tki-resistance.md` 或 `references/kras-g12c-landscape.md` |
| ChiCTR 复合查询 | 用单 token 分别查询，再合并（分词器脆弱） |

## References


- `references/trialgpt-methodology.md` — 8 维搜索策略 + BM25+MedCPT 检索
- `references/chictr-search-guide.md` — ChiCTR MCP 使用 + 注册号格式
- `references/oncology-db-mcp-api.md` — oncology-db MCP 工具覆盖范围
- `references/egfr-tki-resistance.md` — EGFR TKI 耐药机制（C797S/MET amp 等）
- `references/kras-g12c-landscape.md` — KRAS G12C 试验 landscape

## File map

```
clinical-trial-matching/
├── SKILL.md
├── README.md
├── evals/
│   ├── evals.json
│   └── files/
│       ├── patient1.json
│       └── patient2.json
└── references/
    ├── trialgpt-methodology.md
    ├── chictr-search-guide.md
    ├── oncology-db-mcp-api.md
    ├── egfr-tki-resistance.md
    └── kras-g12c-landscape.md
```
