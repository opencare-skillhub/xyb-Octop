# CancerDAO Clinical Trial Matching

End-to-end oncology clinical trial matching skill. Generates decision-grade reports for cancer patients (particularly Chinese patients) by coordinating dual-source retrieval (ClinicalTrials.gov + ChiCTR) with structured eligibility analysis.

## Install

```bash
npx skills add CancerDAO/clinical-trial-matching
```

## When to use

- "找临床试验"、"临床入组"、"匹配试验"
- "trial matching"、"clinical trial"、"NCT"、"ChiCTR"
- Cancer diagnosis + gene mutation + treatment history → requesting trial options

## Quick Start

```bash
# Patient profile example
# Use the skill with a patient description:
# "我爸刚确诊肺腺癌四期，EGFR突变，用过奥希替尼，现在耐药了。想找临床试验。"
```

## Architecture

- `SKILL.md` — orchestrator + 7-step workflow
- `evals/` — benchmark cases
- `references/` — clinical knowledge (EGFR/KRAS resistance, ChiCTR search, oncology-db MCP)

## License

MIT — CancerDAO
