# Exploratory results: 19 metrics across 24 endpoints

This 28 October 2026 retrospective extension adds Dataset Delivery Rate, Variable Coverage and Failure-stage distribution to the [previous sixteen-metric report](../open-models-2026-10-25/README.md). Every original metric definition, value and numeric observation remains unchanged. No model, validator, repair or rebuild was rerun, and the frozen formal main-study protocol was not changed.

[Excel workbook](metrics.xlsx) · [Full comparison table](metrics.md) · [CSV](metrics.csv) · [JSON](metrics.json) · [Failure-stage distribution CSV](failure-stage-distribution.csv) · [Failure-stage distribution JSON](failure-stage-distribution.json) · [Evidence audit](supplementary-audit.json) · [Definitions and reproduction](../../../research_analysis/SUPPLEMENTARY-METRICS.md)

## Added metrics

- **17 Dataset Delivery Rate:** readable expected lowercase XPT files / 13. Extras do not increase the numerator. A readable empty dataset still counts as delivered; this is not record completeness.
- **18 Variable Coverage:** expected dataset-variable pairs with exact names and correct Numeric/Character storage classes / 531. Missing datasets contribute zero; unreadable schemas make the exact rate unavailable. This does not assess values, lengths, labels, date formats, record coverage or clinical correctness.
- **19 Failure-stage distribution:** observed input-reading, code-execution, dataset-export, Define-XML, rebuilding and P21-validation issues, separately for initial and final phases. Missing delivery, direct failures, downstream blockage and insufficient evidence are distinguished. Provider/controller and unclassified tool errors are retained separately. Observed recovered errors still count; these indicators do not label the entire workflow as failed.

The Excel main sheet contains all nineteen metrics. Endpoint data contains numeric numerators and denominators with formula-calculated rates, and stage statuses. Failure stages contains the aggregate distribution. Initial-only terminal results use the initial checkpoint; other terminal results use the final checkpoint. Failure-stage views are nonexclusive and must not be summed. The initial/final/terminal views are alternative summaries, not additional trials.

## Terminal coverage

| Endpoint | Dataset delivery | Variable coverage | Original controller status |
| --- | --- | --- | --- |
| openai / p21_feedback | 13/13 (100.0%) | 531/531 (100.0%) | completed |
| openai / initial_only | 13/13 (100.0%) | 531/531 (100.0%) | completed |
| openai / self_review | 13/13 (100.0%) | 531/531 (100.0%) | failed |
| anthropic / p21_feedback | 13/13 (100.0%) | 531/531 (100.0%) | completed |
| anthropic / initial_only | 13/13 (100.0%) | 531/531 (100.0%) | completed |
| anthropic / self_review | 13/13 (100.0%) | 531/531 (100.0%) | completed |
| google / p21_feedback | 13/13 (100.0%) | 531/531 (100.0%) | completed |
| google / initial_only | 13/13 (100.0%) | 422/531 (79.5%) | completed |
| google / self_review | 13/13 (100.0%) | 436/531 (82.1%) | completed |
| deepseek / p21_feedback | 13/13 (100.0%) | 531/531 (100.0%) | completed |
| deepseek / initial_only | 13/13 (100.0%) | 531/531 (100.0%) | completed |
| deepseek / self_review | 13/13 (100.0%) | 531/531 (100.0%) | completed |
| google / initial_only / temperature 0.2 | 13/13 (100.0%) | 289/531 (54.4%) | completed |
| google / initial_only / temperature 0.6 | 13/13 (100.0%) | 340/531 (64.0%) | completed |
| google / initial_only / temperature 1.0 | 13/13 (100.0%) | 384/531 (72.3%) | completed |
| gpt-oss-20b (DeepInfra) / initial_only | 0/13 (0.0%) | 0/531 (0.0%) | completed |
| gpt-oss-20b (DeepInfra) / self_review | 0/13 (0.0%) | 0/531 (0.0%) | completed |
| gpt-oss-20b (DeepInfra) / p21_feedback | 0/13 (0.0%) | 0/531 (0.0%) | completed |
| gpt-oss-120b (DeepInfra) / initial_only | 0/13 (0.0%) | 0/531 (0.0%) | completed |
| gpt-oss-120b (DeepInfra) / self_review | 0/13 (0.0%) | 0/531 (0.0%) | completed |
| gpt-oss-120b (DeepInfra) / p21_feedback | 0/13 (0.0%) | 0/531 (0.0%) | completed |
| llama-4-scout (DeepInfra) / initial_only | 0/13 (0.0%) | 0/531 (0.0%) | completed |
| llama-4-scout (DeepInfra) / self_review | 0/13 (0.0%) | 0/531 (0.0%) | completed |
| llama-4-scout (DeepInfra) / p21_feedback | 0/13 (0.0%) | 0/531 (0.0%) | completed |

Coverage reveals differences that complete-file counts cannot: some Gemini outputs deliver all thirteen readable files but omit expected variables or use incorrect storage types. Conversely, 100% variable coverage does not imply correct values or clean P21 findings. All nine DeepInfra open-model endpoints have zero readable dataset delivery and zero variable coverage in their retained terminal snapshots; their P21 stages are blocked by missing prerequisites, not evidence of a P21 service outage.

## Interpretation and evidence

The new analyses were defined after pilot outcomes were known and are exploratory, not prespecified primary endpoints. They assess retained evaluated snapshots, including artifacts from a failed controller where available; successful artifact delivery does not change controller status. Readability uses retained full-read evaluator profiles plus fresh metadata reads of hash-verified files. Measured files are checked against saved workspace manifests; checkpoint-bound tool logs and original receipt hashes are verified, with evidence hashes published in JSON. Raw clinical records, histories, specifications, keys and dictionaries remain private.

P21 stage classification uses original evaluations. Some original metric 3 entries also show later successful host reassessment, which does not erase original technical failures. A usable P21 report with findings is not a validator execution failure. A parseable ODM XML file is not proof of complete Define-XML conformance. No input-reading failure observed is not proof that input reading occurred or was comprehensive.

The 24 table endpoints are not 24 independent trials: some historical initial-only/self-review endpoints share initial generations, and settings/environments differ. Distribution counts describe these columns only; they do not support pooled inferential or causal comparisons. SHA256SUMS binds the public files. The original sixteen-metric report is retained unchanged for provenance.
