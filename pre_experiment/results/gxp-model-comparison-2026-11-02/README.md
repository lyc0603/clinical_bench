# Full-benchmark GxP-inspired model comparison

One new full-DAG exploratory attempt was planned for each of Gemini, DeepSeek and gateway-claimed Sol. Gemini and DeepSeek passed nonclinical readiness and were started once; the gateway returned HTTP 403 before clinical generation. No substitute model was selected. Gemini failed during ADSL merge because generated code used a wrong source path or nonexistent JSON field. DeepSeek was blocked by the controller character-storage boundary: its explicit object character container became numeric after JSON read, confirmed by a synthetic reproduction. Its original failure is retained and must not be interpreted as a model clinical-value error. The separately labelled DeepSeek engineering continuation reexecutes six unedited historical node programs under a nullable-character boundary fix before generating remaining nodes; reused receipts do not incur new model calls and are not double-counted. The continuation passed 27/73 nodes, then ADQSADAS record_universe returned length at 32,768 completion tokens (30,682 reasoning tokens); the incomplete response was rejected and remaining scheduling stopped. No final export or P21 evaluation occurred. The historical Claude failed-and-continued case is a separate reference. This is not a randomized matched experiment or a formal main-study repetition.

## All 19 metric labels

| No. | Metric | Claude Sonnet 5.5 — historical continuation | Gemini 3.1 Pro Preview — Google official | DeepSeek Flash — DeepSeek official — engineering continuation | Gateway-claimed Sol 6.1 — unverified upstream |
|---:|---|---|---|---|---|
| 1 | Workflow completion and complete dataset packages | Original failed; post-hoc continuation completed | failed | Original controller-blocked; continuation failed | Not started: readiness HTTP 403 |
| 2 | Reproducible final packages | Semantic False; bytes False | Unavailable | Unavailable | Unavailable |
| 3 | Valid final P21 evaluations | Usable True; full coverage True | Unavailable | Unavailable | Unavailable |
| 4 | Initial and final dataset-rule pairs | 30 | Unavailable | Unavailable | Unavailable |
| 5 | Reduction from initial to final | Not applicable / unavailable | Not applicable / unavailable | Not applicable / unavailable | Unavailable |
| 6 | Final findings by severity | {"Unassigned": 12830} | Not applicable / unavailable | Not applicable / unavailable | Unavailable |
| 7 | Newly introduced dataset-rule pairs | Not applicable / unavailable | Not applicable / unavailable | Not applicable / unavailable | Unavailable |
| 8 | NPI summary errors / assessed records | mean_coverage: 0/234; mean_value: 0/234 | mean_coverage: unavailable; mean_value: unavailable | mean_coverage: unavailable; mean_value: unavailable | Unavailable |
| 9 | NPI baseline errors / assessed records | baseline_covariate: 0/234 | baseline_covariate: unavailable | baseline_covariate: unavailable | Unavailable |
| 10 | TTE linkage errors / assessed records | subject_coverage: 0/254; start_date: 0/254; event_status: 0/254; source_link: 0/152; event_date: 0/152; duration_arithmetic: 0/254; censor_convention: 0/102 | subject_coverage: unavailable; start_date: unavailable; event_status: unavailable; source_link: unavailable; event_date: unavailable; duration_arithmetic: unavailable; censor_convention: unavailable | subject_coverage: unavailable; start_date: unavailable; event_status: unavailable; source_link: unavailable; event_date: unavailable; duration_arithmetic: unavailable; censor_convention: unavailable | Unavailable |
| 11 | Missing extra and duplicate expected records | NPI missing/extra/duplicates 0/0/0; TTE missing/extra/duplicates 0/0/0 | Unavailable | Unavailable | Unavailable |
| 12 | Assessable checks / planned checks | 10/10 | 0/10 | 0/10 | Unavailable |
| 13 | Workflow API cost estimate in USD | Not applicable / unavailable | Not applicable / unavailable | Not applicable / unavailable | Unavailable |
| 14 | Input and output tokens | Input 19,374,930; output 237,274; cached input 0 | Input 664,342; output 16,038; cached input 0 | Input 5,257,733; output 394,274; cached input 524,672 | Unavailable |
| 15 | End-to-end elapsed time in minutes | Original 27.42; continuation 11.97 | 2.61 | Overall 213.96; Original 7.05; continuation 19.15 | Unavailable |
| 16 | Tool calls and failed tool calls | Model tool calls N/A; 76 recorded API responses | Model tool calls N/A; 4 recorded API responses | Model tool calls N/A; 31 recorded API responses | Unavailable |
| 17 | Dataset Delivery Rate | 13/13 | 0/13 | 0/13 | Unavailable |
| 18 | Variable Coverage | 531/531 | 0/531 | 0/531 | Unavailable |
| 19 | Failure-stage distribution | Original export failed; storage-only continuation completed; strict reproduction false | input_reading=1, code_execution=2; blocked datasets=12; provider failures=0 | Original controller null-character failure; continuation stopped at ADQSADAS: output/reasoning cap (length) | Not started: readiness HTTP 403 |

Excel workbook: [comparison.xlsx](comparison.xlsx). Detailed machine-readable values: [comparison.json](comparison.json). Spreadsheet-compatible table: [comparison.csv](comparison.csv). Per-model evidence summaries: [Claude](claude/summary.json), [Gemini](gemini/summary.json), [DeepSeek](deepseek/summary.json).

## Design and interpretation

The original Gemini and DeepSeek attempts use the same repaired 73-process-node DAG; the DeepSeek continuation adds the documented nullable-character controller fix. All target all 13 datasets/531 variables, full specification context, provider-default temperature/reasoning, output/reasoning cap32768, two local attempts per node/export, and at most two concurrent dataset branches. Models run serially in Gemini → DeepSeek order. No web tools are supplied; generated Python executes offline in the same pinned Docker image. P21 is terminal only and never feeds repairs. Full inputs, clinical programs and results are not shared across new models.

The historical Claude run used the earlier all-missing-character gate and then an explicitly post-hoc export-storage continuation. Its original failure stays in the record; it is not a clean same-version control. Hosted aliases and provider defaults do not establish fixed or equal weights/sampling. The third-party gateway model string would not authenticate an official OpenAI upstream even if available.

Unavailable metrics are not zero. A partial package cannot provide the primary complete-coverage P21 score. Candidate export coverage is descriptive and separate from accepted final delivery. There is no complete initial P21 comparator, so reduction and newly introduced rule pairs are N/A. Native token receipts include thinking where reported; cached input is a subset of input, not an additional token total. Dollar cost is unavailable without verified billing/rates. Model tool counts are N/A for these direct API calls; sandbox counts remain in detailed records.

Auxiliary checks cover selected NPI/TTE expectations only and cannot certify all clinical derivations. P21 findings, a validator execution failure, model code failure and provider readiness failure are different outcomes. Strict semantic/byte reproduction scores are retained even for tiny floating serialization differences; no tolerance relaxation is used to improve a score. Single attempts do not support superiority or causal claims.

## Reproduction and privacy

See [provider runner](../../../gxp_models/README.md), [architecture](../../../gxp_full/README.md), [engineering continuation](../../../gxp_recovery/README.md) and [original ADSL adaptation](../../../gxp_adsl/README.md). All failed attempts, source/runtime pins, native responses and usage receipts remain in private, lossless hash-verified evidence archives. The repository contains code and aggregate measurements only; no credentials, patient records, raw model requests, SDTM/ADaM files or dictionaries are published. The formal main-study lock is unchanged.

Additional receipts: [DeepSeek completion limit](deepseek/completion-limit-adjudication.json), [gateway nonclinical retest](gateway-readiness-retest.json). The controller category `provider_failure` includes an unacceptable completion stop reason here; it does not imply an API outage. No account recharge was performed.

## Later requested follow-ups

The [combined nineteen-metric table](../architecture-followups-2026-11-08/README.md) retains every result above and adds the November 8 follow-up attempts, with official OpenAI kept separate from the historical gateway. This historical table is unchanged apart from this navigation link.
