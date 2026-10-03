# TrialGPT Methodology - NCBI's 8-Dimension Keyword Strategy

## Overview

TrialGPT is an NIH/NLM-developed end-to-end framework for zero-shot patient-to-trial matching with large language models. Published in Nature Communications (2024).

**Paper:** Qiao Jin et al., "Matching patients to clinical trials with large language models," Nature Communications, 2024.
**DOI:** 10.1038/s41467-024-53081-z
**Source:** https://github.com/ncbi-nlp/TrialGPT

## Architecture: Three-Stage Pipeline

```
Patient Summary → TrialGPT-Retrieval → TrialGPT-Matching → TrialGPT-Ranking
```

### Stage 1: TrialGPT-Retrieval (8-Dimension Keyword Generation)

Given a patient note, the system generates keywords across **8 clinical dimensions** to retrieve candidate trials at scale.

**The 8 keyword dimensions:**

1. **Disease/Condition** — Primary diagnosis and staging
   - e.g., "non-small cell lung cancer", "stage IV adenocarcinoma"

2. **Biomarkers/Genetic Alterations** — Molecular features
   - e.g., "EGFR T790M mutation", "KRAS G12C", "ALK fusion"

3. **Prior Treatments** — Treatment history
   - e.g., "osimertinib refractory", "prior platinum chemotherapy"

4. **Line of Therapy** — Treatment sequence context
   - e.g., "first-line", "second-line after EGFR TKI failure"

5. **Population Characteristics** — Demographics and enrollment constraints
   - e.g., "adult patients 18-75", "ECOG 0-1", "no brain metastases"

6. **Study Design Parameters** — Trial type and phase
   - e.g., "phase 2", "randomized", "open-label"

7. **Geographic/Institutional** — Site preferences
   - e.g., "US sites only", "academic medical center"

8. **Outcome Measures** — Endpoints of interest
   - e.g., "OS benefit", "PFS primary endpoint", "ORR"

**Implementation:**

```python
# Keyword generation command (from TrialGPT repo)
python trialgpt_retrieval/keyword_generation.py ${corpus} ${model}
# corpus: sigir, trec_2021, trec_2022
# model: gpt-4-turbo, gpt-35-turbo, etc.
```

**Prompt for keyword generation** (from paper):
LLMs are instructed to generate up to K=32 keywords ranked by importance, covering all 8 dimensions.

### Hybrid Fusion Retrieval

For each keyword, TrialGPT runs two retrievers in parallel:

- **BM25** — Lexical matching (traditional sparse retrieval)
- **MedCPT** — Semantic matching (dense vector retriever for clinical text)

Results are fused via **Reciprocal Rank Fusion (RRF)** with k=20:

```
RRF_score(t_j) = Σ (1 / (k + Rank_BM25(w_i, t_j))) + Σ (1 / (k + Rank_MedCPT(w_i, t_j)))
```

A decaying weight is applied across keywords. Final score `s_j` for trial `t_j`:

```
s_j = Σ (importance(w_i) × RRF_score(t_j | w_i))
```

**Key performance metric:** Recalls >90% of relevant trials using <6% of the initial collection.

### Stage 2: TrialGPT-Matching (Criterion-Level Eligibility)

For each candidate trial, TrialGPT-Matching performs **criterion-by-criterion analysis** for each eligibility criterion:

**Three output elements per criterion:**
1. **Explanation** — Natural language reasoning
2. **Evidence location** — Sentences in patient note supporting the classification
3. **Eligibility classification** — Included / Not Included / Not Enough Information / Not Applicable

**Performance:** 87.3% accuracy on 1015 manually-annotated patient-criterion pairs (vs. 88.7%–90.0% for human experts).

### Stage 3: TrialGPT-Ranking (Trial-Level Aggregation)

Aggregates criterion-level predictions into trial-level scores using LLM aggregation, then ranks trials by eligibility.

**Metric:** Outperforms best competing models by 43.8% in ranking and excluding trials.

## Key Design Principles for Our Skill

1. **Keyword diversity** — Generate 20-32 keywords across all 8 dimensions, not just disease terms
2. **Hybrid retrieval** — Combine lexical (BM25) + semantic (MedCPT) for robustness
3. **Criterion-level matching** — Parse inclusion/exclusion criteria separately
4. **Rank fusion** — Use RRF to combine multi-keyword results
5. **Explanation generation** — Always provide reasoning for eligibility predictions

## Citation

```bibtex
@article{jin2024matching,
  title={Matching patients to clinical trials with large language models},
  author={Jin, Qiao and Wang, Zifeng and Floudas, Charalampos S and Chen, Fangyuan
          and Gong, Changlin and Bracken-Clarke, Dara and Xue, Elisabetta and Yang, Yifan
          and Sun, Jimeng and Lu, Zhiyong},
  journal={Nature Communications},
  volume={15},
  number={1},
  pages={9074},
  year={2024}
}
```

## Access

- **GitHub:** https://github.com/ncbi-nlp/TrialGPT
- **NIH Page:** https://www.ncbi.nlm.nih.gov/research/trialgpt/
- **ArXiv:** https://arxiv.org/abs/2307.15051
- **Dataset:** https://ftp.ncbi.nlm.nih.gov/pub/lu/TrialGPT/trial_info.json