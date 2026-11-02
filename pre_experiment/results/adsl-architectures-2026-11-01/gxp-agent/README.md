# Claude ADSL Process-DAG results — 2026-11-01

One complete excluded exploratory architecture-adaptation run, new frozen root `gxp-adsl-20261101-v5`. Prior failed development attempts remain retained and are not repetitions under this final implementation.

| Measure | Result | Interpretation |
|---|---|---|
| Model | claude-sonnet-5-5 | Anthropic direct Messages API; provider-default sampling/reasoning |
| Scope | ADSL only | Independent Python Process-DAG adaptation; not original R implementation |
| Run status | Completed | Workflow completed; does not mean zero conformance findings |
| Passed nodes | 15 / 15 | All fixed dependency nodes accepted |
| First-attempt accepted nodes | 13 / 15 | No repeated whole-run attempts inside this frozen run |
| Locally repaired nodes | 2 / 15 | derive_completion, apply_metadata |
| Generation requests | 17 | Includes two failed node candidates; final P21 feedback never returned to model |
| Dataset delivery | 1 / 1 (100%) | ADSL XPT delivered in accepted final package |
| Variable name/type coverage | 49 / 49 (100%) | Specified names and Character/Numeric storage types; not value accuracy |
| Subject count | 254 / 254 | GEN01 randomized subject identity gates applied |
| Define-XML | Delivered | At output/adam/datasets/define.xml |
| Independent rebuild | Succeeded | Offline execution; exit code 0 |
| Semantic reproducibility | Yes | ADSL data and Define-XML semantic comparison |
| Byte reproducibility | No | Define-XML identical; XPT differs only at writer timestamp bytes |
| Selected direct-source checks | 13 checks; 3302 assessments; 0 errors | 11 DM predecessors + SV Visit3 TRTSDT/RANDDT; limited auxiliary coverage |
| P21 report usable | Yes | Not a claim of zero findings |
| P21 ADSL validation coverage | Complete | Expected ADaM dataset processed; source support domains are not ADaM outputs |
| P21 dataset-rule pairs | 3 | Primary conformance count; lower is better |
| P21 finding instances | 3 | Three findings across three rules |
| P21 distinct rules | 3 | AD0018, AD0320, AD0509 |
| P21 rejected ADSL records | 0 | 254 ADSL records processed |
| P21 raw exit code | 5 | 5; report retained and judged usable by frozen evaluator |
| Native input tokens | 304777 | Includes failed local attempts |
| Native output tokens | 42080 | Includes failed local attempts |
| Native cache-read tokens | 0 | Provider telemetry |
| Native cache-creation tokens | 0 | Provider telemetry |
| Elapsed workflow seconds | 362.201 | Includes terminal evaluation; excludes preparation |
| Offline rebuild seconds | 11.131 | One independent reconstruction |
| P21 execution seconds | 35.366 | Terminal validation |
| API cost (USD) | Not calculated | No verified pricing or billed-cost receipt supplied |
| Comprehensive derivation correctness | Not established | No independent oracle for all 49 variables |
| Full 13-dataset benchmark | Not evaluated | Do not pool denominators with full-study endpoints |

## P21 findings

| Rule | Message | Instances | Severity in report |
|---|---|---:|---|
| AD0018 | Variable label mismatch between dataset and ADaM standard | 1 | Unassigned |
| AD0320 | Non-standard dataset label | 1 | Unassigned |
| AD0509 | *SDT must contain 'Start Date' in the label | 1 | Unassigned |

The three findings concern variable/dataset labels. They remain part of the measured result and were not repaired after terminal evaluation. Severity was unassigned in the native report; do not recast these as specifically errors or warnings. A usable report is not a zero-finding pass.

## Interpretation and scope

This run demonstrates end-to-end feasibility of applying the benchmark input and evaluator to an independently implemented GxP-Agent-inspired ADSL Process-DAG. It does not establish superiority over another architecture, original-paper numerical replication, full clinical value correctness or GxP compliance. The language, model and dependency ordering differ from the original paper. There is one measured run under this implementation and no matched monolithic ADSL control.

Earlier failed attempts were retained with separate freezes. This version explicitly supplies input/output paths, extracts one unambiguous Python block, permits at most two attempts per node and uses max_tokens 32768. All 14 technical tests passed before freezing. No generated clinical code was manually edited during the frozen run. P21 findings were never fed back to the model.

Independent reconstruction produced identical Define-XML bytes. XPT files had equal lengths and exactly eight differing bytes at offsets 158, 159, 174, 175, 478, 479, 494 and 495, within library/member writer timestamps. Masking only these known 16-byte timestamp fields makes XPT bytes identical. This diagnoses the byte mismatch without changing the frozen metric, which remains false.

Sources: hash-verified state, all native model receipts, accepted workspace manifests and terminal evaluation in the private run root. Public-safe evidence is in summary.json, steps.csv and audit.json. Raw clinical inputs, requests, outputs and P21 report stay private.

Freeze SHA-256: `defcf0cfcdec94d8ad18b5c1508b50fbcb930722a21b16b7d3a0f468f7def3a9`. P21 report SHA-256: `7b80b121609956bea344062ce3aebaf858365c59afaf60d2b19db24713f1c4f6`.


This is the public aggregate report. Raw clinical artifacts, full model advisory text, generated code and provider requests remain private. Publication source hashes and a cross-architecture comparison are in the parent directory.
