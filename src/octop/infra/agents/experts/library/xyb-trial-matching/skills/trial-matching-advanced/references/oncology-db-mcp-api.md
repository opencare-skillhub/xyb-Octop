# oncology-db MCP API — Clinical Trial Matching Reference

## Overview

The oncology-db MCP server provides a comprehensive oncology knowledge graph integrating data from CIViC, OpenFDA, ClinicalTrials.gov, and OpenFDA Drug Labels.

**Database Stats (as of 2026-05-14):**
- Genes: 563
- Targets: 3,652
- Oncology drugs: 9,506
- FDA-approved drugs: 334
- Clinical trials: 18,161
- Evidence links: 8,441
- CIViC evidence total: 11,232

---

## MCP Tools for Clinical Trial Matching

### search_trials

```javascript
mcp__oncology-db__search_trials({
  query: string,       // Search query (e.g., "KRAS G12C", "EGFR TKI resistance")
  status?: string,     // RECRUITING | COMPLETED | etc.
  phase?: string      // PHASE1 | PHASE2 | PHASE3
})
```

**Returns:**
```json
{
  "query": "KRAS G12C",
  "total": 30,
  "trials": [
    {
      "nct_id": "NCT06119581",
      "title": "A Study of First-Line Olomorasib...",
      "status": "RECRUITING",
      "phase": "PHASE3",
      "conditions": "Carcinoma, Non-Small-Cell Lung|Neoplasm Metastasis",
      "interventions": "DRUG: LY3537982|DRUG: Pembrolizumab|...",
      "sponsor": "Eli Lilly and Company",
      "enrollment": 1264,
      "url": "https://clinicaltrials.gov/study/NCT06119581"
    }
  ]
}
```

### get_target_treatments

```javascript
mcp__oncology-db__get_target_treatments({
  gene: string,      // Gene symbol, e.g., "EGFR", "KRAS"
  variant: string    // Variant, e.g., "T790M", "G12C"
})
```

**Returns sensitivity and resistance drug lists with:**
- `drug_name`, `brand_name`
- `is_fda_approved` (1/0)
- `drug_type` (targeted/chemo/unknown)
- `category` (support/resist)
- `best_evidence_level` (A/B/C/D/E)
- `evidence_count`
- `combo_context` (combination therapies)
- `therapy_interaction` (Combination/Substitutes/Sequential)
- `diseases`

### get_drug_detail

```javascript
mcp__oncology-db__get_drug_detail({
  drug_name: string   // e.g., "Osimertinib", "Sotorasib", "Adagrasib"
})
```

**Returns:**
- `drug` — Name, brand, FDA approval status, dosage form, route
- `label` — Full FDA label: mechanism of action, indications, adverse reactions
- `clinical_trials` — Active trials for this drug
- `evidence` — Gene/variant/disease evidence links

### get_gene_variants

```javascript
mcp__oncology-db__get_gene_variants({
  gene: string   // e.g., "EGFR", "KRAS"
})
```

**Returns:** List of all variants for the gene with evidence counts and drug counts per variant.

### search

```javascript
mcp__oncology-db__search({
  query: string   // Gene name, drug name, or disease
})
```

General search across the knowledge base.

---

## Oncology-Db Coverage for Trial Matching

### EGFR Variants (199 total variants in database)

Top EGFR variants with clinical evidence:

| Variant | Evidence Count | Drug Count |
|---------|---------------|------------|
| L858R | 72 | 21 |
| T790M | 60 | 22 |
| Exon 19 Deletion | 51 | 16 |
| C797S | 12 | 6 |
| Exon 20 Insertion | 12 | 9 |
| S768I | 12 | 4 |
| G719A | 12 | 4 |

**T790M Sensitivity Profile:**
- Osimertinib: FDA-approved, Level A evidence
- Rociletinib: Not FDA-approved, Level B
- Erlototinib + Pemetrexed: Level C combination

**C797S Resistance Profile:**
- Osimertinib: Level B resistance (standalone)
- Brigatinib + Cetuximab: Level D support (combination)
- Note: C797S is the most clinically relevant osimertinib resistance mutation

### KRAS G12C Trials (30 active trials as of 2026-05-14)

Key KRAS G12C drugs in database:
- **Sotorasib (LUMAKRAS)** — FDA approved for NSCLC and mCRC + panitumumab
- **Adagrasib (KRAZATI)** — FDA approved for NSCLC and mCRC + cetuximab

Active Phase 3 KRAS G12C trials:
- NCT06119581 — Olomorasib + pembrolizumab +/- chemo (n=1264)
- NCT04613596 — Adagrasib +/- pembrolizumab (KRYSTAL-7, Phase 2/3)
- NCT06875310 — Adagrasib + pembrolizumab + chemo (KRYSTAL-4)
- NCT06345729 — Calderasib (MK-1084) + pembrolizumab (PD-L1 TPS >=50%)

---

## Data Sources

1. **CIViC** — Clinical Interpretations of Variants in Cancer (precisionFDA)
2. **OpenFDA** — FDA drug labels and approval data
3. **ClinicalTrials.gov** — Trial registry data
4. **OpenFDA Drug Labels** — Drug label information

---

## Integration Notes for Skill

**Strengths:**
- Gene/variant/drug relationship data is well-structured
- Clinical trials linked to specific gene targets
- FDA approval status and evidence levels help filter trials
- Evidence levels (A/B/C/D) help prioritize results

**Limitations:**
- search_trials does not support advanced filtering (e.g., specific eligibility criteria)
- Clinical trial data is snapshot-based, not real-time
- No mechanism to parse eligibility criteria text
- MET amplification returns no results in get_target_treatments (needs alternative search)

**Recommended usage pattern:**
1. Use `search_trials` for broad trial discovery
2. Use `get_target_treatments` to identify relevant gene/variant targets
3. Use `get_drug_detail` for drug mechanism and label information
4. Combine with TrialGPT's keyword strategy for deeper eligibility matching

---

## References

- oncology-db MCP server (accessed 2026-05-14)
- CIViC: https://civicdb.org
- OpenFDA: https://open.fda.gov
- ClinicalTrials.gov: https://clinicaltrials.gov