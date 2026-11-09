# Full-benchmark AI-431-inspired five-model results

Independent implementation of the [PharmaSUG 2026 AI-431 architecture](https://pharmasug.org/proceedings/2026/AI/PharmaSUG-2026-AI-431.pdf): advisory specification review, independent variable generation, sandbox execution/local repair, QC, keyed merge and terminal evaluation. All 13 datasets / 531 variables are targeted. This is not author software or numerical reproduction, and is excluded from the formal main study.

[Excel workbook](comparison.xlsx) · [CSV table](comparison.csv) · [Full metric components and per-model summaries](comparison.json). Unavailable is different from zero.

| No. | Metric | Claude Sonnet 5.5 — Anthropic official | Gemini 3.1 Pro Preview — Google official | DeepSeek Flash — DeepSeek official | Gateway-claimed Sol 6.1 — unverified upstream | gpt-oss-20b — DeepInfra |
|---:|---|---|---|---|---|---|
| 1 | Workflow completion and complete dataset packages | failed; variables 49/531 | failed; variables 30/531 | failed; variables 49/531 | Not started: readiness_http_403 | failed; variables 37/531 |
| 2 | Reproducible final packages | Unavailable | Unavailable | Unavailable | Unavailable | Unavailable |
| 3 | Valid final P21 evaluations | Unavailable | Unavailable | Unavailable | Unavailable | Unavailable |
| 4 | Initial and final dataset-rule pairs | Unavailable | Unavailable | Unavailable | Unavailable | Unavailable |
| 5 | Reduction from initial to final | Not applicable / unavailable | Not applicable / unavailable | Not applicable / unavailable | Unavailable | Not applicable / unavailable |
| 6 | Final findings by severity | Not applicable / unavailable | Not applicable / unavailable | Not applicable / unavailable | Unavailable | Not applicable / unavailable |
| 7 | Newly introduced dataset-rule pairs | Not applicable / unavailable | Not applicable / unavailable | Not applicable / unavailable | Unavailable | Not applicable / unavailable |
| 8 | NPI summary errors / assessed records | mean_coverage: unavailable; mean_value: unavailable | mean_coverage: unavailable; mean_value: unavailable | mean_coverage: unavailable; mean_value: unavailable | Unavailable | mean_coverage: unavailable; mean_value: unavailable |
| 9 | NPI baseline errors / assessed records | baseline_covariate: unavailable | baseline_covariate: unavailable | baseline_covariate: unavailable | Unavailable | baseline_covariate: unavailable |
| 10 | TTE linkage errors / assessed records | subject_coverage: unavailable; start_date: unavailable; event_status: unavailable; source_link: unavailable; event_date: unavailable; duration_arithmetic: unavailable; censor_convention: unavailable | subject_coverage: unavailable; start_date: unavailable; event_status: unavailable; source_link: unavailable; event_date: unavailable; duration_arithmetic: unavailable; censor_convention: unavailable | subject_coverage: unavailable; start_date: unavailable; event_status: unavailable; source_link: unavailable; event_date: unavailable; duration_arithmetic: unavailable; censor_convention: unavailable | Unavailable | subject_coverage: unavailable; start_date: unavailable; event_status: unavailable; source_link: unavailable; event_date: unavailable; duration_arithmetic: unavailable; censor_convention: unavailable |
| 11 | Missing extra and duplicate expected records | Unavailable | Unavailable | Unavailable | Unavailable | Unavailable |
| 12 | Assessable checks / planned checks | 0/10 | 0/10 | 0/10 | Unavailable | 0/10 |
| 13 | Workflow API cost estimate in USD | Not applicable / unavailable | Not applicable / unavailable | Not applicable / unavailable | Unavailable | Not applicable / unavailable |
| 14 | Input and output tokens | Input 1,077,625; output 81,829; cached input 0 | Input 554,082; output 225,559; cached input 0 | Input 659,614; output 410,806; cached input 37,376 | Unavailable | Input 888,157; output 161,643; cached input unavailable |
| 15 | End-to-end elapsed time in minutes | 5.91 | 13.24 | 16.37 | Unavailable | 10.40 |
| 16 | Tool calls and failed tool calls | Model tool calls N/A; 54 recorded API responses | Model tool calls N/A; 41 recorded API responses | Model tool calls N/A; 51 recorded API responses | Unavailable | Model tool calls N/A; 69 recorded API responses |
| 17 | Dataset Delivery Rate | 0/13 | 0/13 | 0/13 | Unavailable | 0/13 |
| 18 | Variable Coverage | 0/531 | 0/531 | 0/531 | Unavailable | 0/531 |
| 19 | Failure-stage distribution | input_reading=3; code_execution=1; failed variables=0; failed row tasks=0; merge QC=1; blocked datasets=12; API failures=0; incomplete/invalid replies=0 | input_reading=8; code_execution=2; failed variables=1; failed row tasks=0; merge QC=0; blocked datasets=12; API failures=1; incomplete/invalid replies=0 | code_execution=1; failed variables=0; failed row tasks=0; merge QC=1; blocked datasets=12; API failures=0; incomplete/invalid replies=0 | Not started: readiness_http_403 | input_reading=7; code_execution=24; failed variables=12; failed row tasks=0; merge QC=0; blocked datasets=12; API failures=0; incomplete/invalid replies=0 |

## Run status and failures

- Claude Sonnet 5.5 — Anthropic official: **failed**, 49/531 variable tasks passed; 0/12 row universes passed. Native responses: 54 (including 1 advisory reviews). Merged cross-variable QC failed; downstream datasets were blocked. Passing each variable locally does not establish cross-variable consistency. [Exact merge-gate adjudication](claude/merge-failure-adjudication.json).
- Gemini 3.1 Pro Preview — Google official: **failed**, 30/531 variable tasks passed; 0/12 row universes passed. Native responses: 41 (including 1 advisory reviews). Failed/blocked task details: [gemini/summary.json](gemini/summary.json). [Additional adjudication](gemini/failure-adjudication.json). [Additional adjudication](gemini/runtime-intervention-adjudication.json).
- DeepSeek Flash — DeepSeek official: **failed**, 49/531 variable tasks passed; 0/12 row universes passed. Native responses: 51 (including 1 advisory reviews). Merged cross-variable QC failed; downstream datasets were blocked. Passing each variable locally does not establish cross-variable consistency. [Exact merge-gate adjudication](deepseek/merge-failure-adjudication.json).
- Gateway-claimed Sol 6.1 — unverified upstream: readiness failed with HTTP403; no clinical generation or clinical inputs transmitted. A requested/returned gateway string does not authenticate an official OpenAI upstream. No recharge or model substitution occurred.
- gpt-oss-20b — DeepInfra: **failed**, 37/531 variable tasks passed; 0/12 row universes passed. Native responses: 69 (including 1 advisory reviews). Failed/blocked task details: [gpt_oss_20b/summary.json](gpt_oss_20b/summary.json). [Additional adjudication](gpt_oss_20b/failure-adjudication.json).

## Fixed design and interpretation

Four qualified endpoints use the same frozen implementation and input bytes, three concurrent independent variable tasks, serial datasets and models, provider-default sampling/reasoning, maximum32768 output/reasoning tokens and two local code/QC attempts per task/export. Model order: Claude → Gemini → DeepSeek → gpt-oss-20b. No overall repair-time budget. API300-second and sandbox1800-second timeouts protect individual operations. Provider/default/hosted alias differences prevent equal-weight or equal-sampling claims. The gateway remains a separate unverified-provenance endpoint. gpt-oss-20b is hosted by DeepInfra, not run locally.

Approved clinical specifications never change. Per-dataset model reviews are advisory and not fed to workers. Variable contexts are deterministically selected from the unchanged specifications, including dependency specifications, global rules/details, relevant value-level metadata/parameter map/codelists; full specifications remain readable offline. ADSL starts with controller randomized subject keys only. Other row universes are generated by the model; scalar row helpers and stable controller row IDs align repeated-subject records. Each variable worker sees no other current-dataset worker outputs/programs and independently recomputes intermediates. Exact keys, types, lengths, ownership and selected merged consistency checks gate keyed merging. There is no exhaustive clinical derivation or row-universe oracle.

Failed independent variables block that dataset merge and dependent datasets; unrelated work can continue. Provider, invalid completion or controller failures stop new requests while retaining in-flight evidence. P21 is terminal only and never repair feedback. Final accepted delivery is distinguished from individual passed variables and rejected candidates. Complete delivery plus full validated coverage is required for the primary P21 metric; partial findings are descriptive only. No complete initial package was scored, so reduction and newly introduced rule metrics are unavailable. Auxiliary NPI/TTE checks have the benchmark's original narrow/conditional limits. Strict semantic and byte reconstruction scores are not relaxed for small floating differences.

All observed native usage includes failed/truncated calls, reviews and local repairs. Cached input is a subset of total input; Anthropic uncached/cache-read/cache-created components are normalized explicitly. USD cost is unavailable without verified billing. Model tool-call counts are N/A for tool-free direct APIs; sandbox counts are separate. One nonrandomized exploratory attempt cannot establish model or architecture superiority. Historical GxP and ADSL results stay unchanged and are not pooled into this cohort.

## Privacy and reproduction

See [implementation, adaptation limits and commands](../../../ai431_full/README.md). Generated Python runs in the pinned network-disabled Docker image, without credentials, references, evaluator or other-run access. Full native requests/responses, clinical files/programs and every failure remain in private lossless archives with per-file stream-hash verification. Only aggregates, code and hashes are published. The formal main-study lock is unchanged.

Native token totals cover observed usage receipts. An HTTP/transport failure without usage is not evidence of zero billed usage. Per-model timing receipts disclose nonconcurrent execution dates; interrupted preparation and manual runtime interventions are retained explicitly.

## Nonconcurrent execution and retained intervention

Claude ran on November 5 and Gemini on November 7 after a disk-space pause. Before resumption, all 468 pinned P21 cache files were restored from preserved copies and matched the original frozen hashes; no runtime upgrade occurred. Gemini COMP8FL exhausted two local attempts and COMP24FL received HTTP402 for exhausted prepaid credit. New requests stopped. An already in-flight DSRAEFL task subsequently passed after stopping an owned Docker preparation loader with no running processes. The retained adjudication records this post-hoc infrastructure unblock: no generated code was edited and no additional model request was triggered by the intervention. Elapsed time includes diagnosis and intervention. No P21 validation was reached for that attempt.

DeepInfra returned null cache-token details. A post-hoc aggregate-only reporter repair recovered input/output totals from unchanged native receipts and leaves cached input unavailable. No clinical request was repeated and no frozen experimental code or generated program was changed.

## Later requested follow-ups

The [combined nineteen-metric table](../architecture-followups-2026-11-08/README.md) retains every result above and adds the November 8 follow-up attempts, with official OpenAI kept separate from the historical gateway. This historical table is unchanged apart from this navigation link.
