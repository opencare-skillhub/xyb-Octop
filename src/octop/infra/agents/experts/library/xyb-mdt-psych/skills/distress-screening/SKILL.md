---
name: distress-screening
description: 当患者情绪困扰需要结构化初筛时使用。提供 HADS（医院焦虑抑郁量表）的条目说明、计分规则与结果解读框架，**全部在本机完成，不上传、不发布公网**。Must use for structured distress screening; local-only, never published.
metadata:
  octop:
    emoji: "📋"
    label:
      zh: "情绪困扰初筛（HADS）"
      en: "Distress Screening (HADS)"
    summary:
      zh: "本机完成 HADS 初筛、计分与解读；不发布公网、不上传数据。"
      en: "Local-only HADS screening, scoring and interpretation."
source_repo: opencare-skillhub/skill-HADS-accessment
source_license: NONE
adapted: 2026-10-02
readiness: 受限（仅本机版；公网发布路径已移除）
---
> ## 本项目的使用范围（优先级高于本文其余内容）
>
> 上游技能支持把问卷**发布到公网平台**收集作答。**本项目不使用该路径。**
> 需求明确要求问卷保持本机版（见 `XYB-REQUIREMENTS.md` §八），因此：
>
> - 问卷只在本机生成与作答，**不上传、不发布、不用第三方托管**；
> - 不收集姓名、手机号、身份证号、住院号；作答记录只留本机；
> - 量表结果是**初筛**，不构成心理或精神科诊断；
> - 出现自伤或自杀念头时，按本专家 `SOUL.md` 的危机信号流程处理，优先级高于本技能。
>
> 下文是上游原始说明，其中涉及公网发布的部分仅作背景了解，本项目不执行。

# Skill: HADS 心理量表评估助手

## 核心能力

为癌症患者提供标准化 HADS（医院焦虑抑郁量表）在线评估服务：

1. **问卷发布**：生成交互式 HTML 问卷并发布到 EdgeOne 公网
2. **自动计分**：患者填写后前端自动计算焦虑/抑郁评分
3. **结果导出**：支持截图、PDF、JSON 三种格式
4. **数据标准化**：输出符合医疗数据标准的结构化 JSON
5. **量表设计 Agent**：支持通过 LLM 提示词生成自定义量表（PHQ-9, GAD-7 等）
6. **智能解读 Agent**：结合 LLM 对评估结果进行深度临床解读，并提供个性化干预决策建议
7. **自优化系统**：基于 [info] 日志记录执行过程，自动识别性能瓶颈并优化流程

## 使用场景

### 场景 1：为单个患者生成问卷

```bash
# 生成问卷 HTML
python src/publisher.py --patient-id P001

# AI Agent 发布到 EdgeOne
用 EdgeOne MCP 发布 deployed/questionnaires/hads_P001_xxx.html
```

### 场景 2：解析评估结果

```bash
python src/result_parser.py results/json/hads_result_P001.json
```

### 场景 3：量表自优化流程 (升级版)

1. **多维日志记录**：系统自动生成四级日志（EXECUTION, SEMANTIC, DECISION, REFLECTION）。
2. **事后反思 (Reflection)**：每次核心任务完成后，`Reflection Agent` 自动回溯日志。
3. **人工审批约束**：
   - **审批范围**：所有涉及业务逻辑（量表题目、评分规则）、提示词版本或流程结构的变更，必须经过人工批准。
   - **受保护内容**：HADS 核心 14 题结构、评分权重（0-21 分制）严禁自动修改。
   - **可优化内容**：UI 说明文字、EdgeOne 发布策略、日志分发逻辑等辅助性功能。
4. **安全机制**：系统设计为"建议权模式"，所有优化提案以待审批状态呈现，未经确认的提案不会被执行。

### 场景 4：智能结果解读

1. **自动提取结果**：`result_parser.py` 解析患者提交的 JSON 原始数据。
2. **生成解读提示词**：`Interpretation Agent` 根据评分、维度及风险等级生成深度解读提示词。
3. **LLM 干预决策**：调用 LLM 获取包含心理疏导、生活建议及医疗转介的结构化方案。

## 输出格式规范

### JSON 格式（标准接口）

```json
{
  "skill": "hads-assessment",
  "version": "1.0.0",
  "patient_id": "P001",
  "assessment_date": "2026-01-20T14:30:00",
  "hads": {
    "anxiety": 12,
    "depression": 8
  },
  "interpretation": {
    "anxiety_level": "abnormal",
    "depression_level": "borderline",
    "overall_risk": "high"
  }
}
```

## 与 skill-report-genie 集成

1. 患者完成评估后下载 `hads_result_P001.json`
2. 将文件放入：`~/skill-report-genie/patient_data/P001/`
3. skill-report-genie 自动识别并整合到综合报告
