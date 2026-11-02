# ADSL architecture-adaptation pilots — 2026-11-01

Two completed, excluded exploratory ADSL runs using Claude Sonnet 5.5: an independently implemented GxP-Agent-inspired Process-DAG and an independently implemented PharmaSUG AI-431-inspired variable pipeline. These are architecture adaptations, not author software or numerical replications. Both delivered 254 subjects and 49 named/typed variables, reproduced semantically, and produced usable P21 reports. Neither was zero-finding.

| Measure | GxP-Agent-inspired | AI-431-inspired | Interpretation |
|---|---|---|---|
| Model | claude-sonnet-5-5 | claude-sonnet-5-5 | Same hosted API identifier; immutable weights not established |
| Implementation unit | 15 serial process nodes | 49 independent variable tasks + review + export | Different decomposition and resource budgets |
| Accepted first-attempt units | 13 / 15 | 49 / 49 variable tasks | Different unit denominators; export also first-attempt accepted |
| Locally repaired units | 2 | 0 | GxP derive_completion/apply_metadata; no manual clinical code edits |
| Final dataset delivery | 1 / 1 | 1 / 1 | ADSL only |
| Variable name/type coverage | 49 / 49 | 49 / 49 | Does not establish value accuracy |
| Subjects | 254 | 254 | Exact randomized subject identities checked |
| Independent rebuild | Succeeded | Succeeded | Offline clean replay |
| Semantic reproducibility | True | True | Data/Define semantic comparison |
| Byte equality | False | False | XPT writer timestamps differ; Define bytes identical |
| P21 report usable | True | True | Usability does not mean zero findings |
| P21 validation coverage | Complete | Complete | One expected ADaM dataset |
| P21 dataset-rule pairs | 3 | 2 | Lower is better; descriptive only |
| P21 finding instances | 3 | 2 | All reported findings concern labels |
| P21 distinct rules | 3 | 2 | Native severity unassigned |
| Selected source checks | 13 checks / 3302 assessments / 0 errors | 13 checks / 3302 assessments / 0 errors | 11 DM predecessor variables + 2 SV anchor dates; not all derivations |
| Native input tokens | 304777 | 542259 | Includes failed local attempts and AI-431 advisory review |
| Native output tokens | 42080 | 77607 | Provider telemetry, not billed cost |
| Generation responses | 17 | 51 | AI-431: 49 variables + review + export |
| Workflow elapsed seconds | 362.201 | 426.792 | Includes terminal evaluation; preparation excluded |
| Completed runs under final implementation | 1 | 1 | Separate development runs; not randomized concurrent comparison |
| Verified billed cost | Unavailable | Unavailable | No rate-based estimate or balance inferred |

## Detailed results

- [GxP-inspired result table and methodology](gxp-agent/README.md)
- [AI-431-inspired result table and methodology](ai431/README.md)
- [Machine-readable comparison](comparison.csv) and [JSON](comparison.json)
- [Retained development history](development-history.json)
- [Publication provenance](publication-provenance.json) and [file checksums](SHA256SUMS)

## What these observations support

The completed runs demonstrate that the benchmark input/evaluation boundary can be exercised by two alternative ADSL generation architectures. They do not establish one architecture is superior. Each final implementation has one measured run; designs have different units, concurrency, prompts and call budgets and were revised after earlier failures. Outputs are descriptive case studies, not matched randomized repetitions or estimates of original-paper performance.

GxP adaptation uses Python/pandas/pyreadstat and an adapted dependency order rather than original R/pharmaverse. AI-431 adapts only the already-confirmed-specification generation/execution/QC/merge workflow; its model review is advisory, without interactive human specification refinement or human code rescue. It flagged eight potential specification/subset blockers that remain unadjudicated. These are model flags, not confirmed errors. Neither structural checks, selected direct-source checks nor P21 establishes all clinical derivations are correct.

P21 is an independent terminal evaluator and is not returned for repair. Both use ADSL-only expected dataset coverage, ADaMIG1.3, FDA2508.1, CT2026-03-27, MedDRA8.0 and client1.0.9. Findings: GxP AD0018/AD0320/AD0509; AI-431 AD0018/AD0509, one instance each. Severity is unassigned in the native reports. Byte-equality remains false because of XPT writer timestamp fields, although Define bytes are identical and semantic comparisons pass.

Run usage includes all recorded clinical-run responses, including failed local candidates and the AI-431 advisory review. Nonclinical qualification and earlier failed development attempts are not included in final-run token/time totals and must not be treated as free: AI-431 export qualification separately consumed 4999 input/4917 output tokens. Original failed attempts remain in development-history.json and private evidence; final successes do not replace them.

## Development transparency

| Run | Status | Accepted work | Stopping reason / role |
|---|---|---|---|
| gxp-adsl-20261028-v2 | failed | 12/15 nodes | Validate response truncated at 8192 output tokens |
| gxp-adsl-20261031-v3 | failed | 7/15 nodes | Uppercase source path then repair prose rejected by strict parser |
| gxp-adsl-20261101-v4 | failed | 14/15 nodes | Define export path underspecified; checker required a different directory |
| gxp-adsl-20261101-v5 | completed | 15/15 nodes | Published completed adaptation |
| ai431-adsl-20261101-v1 | failed | 49/49 variables; merge passed | Accepted workspace file missing during packaging; filesystem root cause not established |
| ai431-adsl-20261101-v1/recovery-continuation | failed | Original variable programs reused with exact hashes, not regenerated | Post-hoc infrastructure continuation; simulated unavailable bash tools repeated until export truncation at 32768 |
| ai431-adsl-20261101-v2 | completed | 49/49 variables + export | New full run; explicit Path interface, dedicated tool-free export, non-cloud execution storage |

An initial GxP preparation was superseded before clinical generation to refine technical checks; it is not a discarded clinical run. The three earlier GxP failures and the AI-431 failure/continuation are development evidence under different freezes and are not extra replicates of the final implementations.

## Scope and privacy

These ADSL-only denominators are 1 dataset / 49 variables. Do not append them to the historical full-study 13-dataset / 531-variable table as comparable endpoints. The existing formal main-study lock and runtime code are unchanged by this publication. This commit publishes result aggregates and evidence hashes only; it does not distribute the local architecture runner code, clinical inputs, generated patient-level outputs, model requests/replies, full advisory text, P21 workbook, dictionaries or API credentials. Collaborators can review tables and leave GitHub comments/issues; private evidence requires separate controlled access.

Architecture references: [GxP-Agent](https://arxiv.org/html/2608.16890v1), [PharmaSUG 2026 AI-431](https://pharmasug.org/proceedings/2026/AI/PharmaSUG-2026-AI-431.pdf).
