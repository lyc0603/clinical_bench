# AI-431-inspired Claude ADSL results

| Measure | Result |
|---|---|
| Model | claude-sonnet-5-5 |
| Run status | completed |
| Variable tasks accepted | 49 / 49 |
| Accepted on first attempt | 49 |
| Variables accepted after repair | None |
| Export | passed |
| Final dataset delivery | 1 / 1 |
| Final variable name/type coverage | 49 / 49 |
| Subjects | 254 |
| Semantic rebuild | True |
| Byte equality | False |
| P21 report usable | True |
| P21 coverage complete | True |
| P21 dataset-rule pairs | 2 |
| P21 finding instances | 2 |
| P21 distinct rules | 2 |
| Selected source-check errors | 0 |
| Native input tokens | 542259 |
| Native output tokens | 77607 |
| Model responses including review and failed candidates | 51 |
| Elapsed seconds | 426.792 |
| Cost USD | Not evaluated |

## Reconstruction detail

The byte-equality metric remains false. Define-XML is byte-identical; XPT differs only in library/member writer timestamp fields. Masking those known fields yields identical XPT bytes. This diagnostic does not change the frozen metric. See rebuild-byte-diagnostic.json.

## Interpretation

One independently implemented Python variable-generation/execution/QC/merge adaptation, not original author software or a replication of its time-saving claims. Frozen input specs were already approved; model review was advisory and never changed specifications. No human repair was performed during the frozen run. Each variable had at most two attempts, with three independent tasks concurrent. Full package metrics are unavailable when merge/export is blocked; missing P21 is not zero findings.

P21 is terminal only and does not inform variable repair. Selected source checks cover only limited predecessor/date values, not every clinical derivation. One run and unmatched task/call budgets cannot establish architectural superiority. This ADSL-only result is separate from full-study 13-dataset/531-variable endpoints. Native usage includes advisory review and all retained responses; billing rates were not verified.

The advisory review flagged 8 potential blockers. These are unadjudicated model flags, not confirmed errors; frozen inputs were unchanged. The full model advisory review remains private; its unadjudicated count is reported in summary.json.

This revision explicitly typed the Path input interface, gave export a separate compact tool-free prompt using installed libraries, and executed in non-cloud local storage before archiving. Previous failures remain separate; this is a new development implementation rather than a prespecified repetition under the earlier version. Synthetic qualification tokens are reported separately and excluded from measured clinical-run usage.

## P21 findings

| Rule | Message | Instances | Severity |
|---|---|---:|---|
| AD0018 | Variable label mismatch between dataset and ADaM standard | 1 | Unassigned |
| AD0509 | *SDT must contain 'Start Date' in the label | 1 | Unassigned |

## Variable/task results

| Task | Status | Attempts | Accepted attempt |
|---|---|---:|---|
| STUDYID | passed | 1 | 1 |
| USUBJID | passed | 1 | 1 |
| SUBJID | passed | 1 | 1 |
| SITEID | passed | 1 | 1 |
| SITEGR1 | passed | 1 | 1 |
| ARM | passed | 1 | 1 |
| TRT01P | passed | 1 | 1 |
| TRT01PN | passed | 1 | 1 |
| TRT01A | passed | 1 | 1 |
| TRT01AN | passed | 1 | 1 |
| TRTSDT | passed | 1 | 1 |
| TRTEDT | passed | 1 | 1 |
| TRTDUR | passed | 1 | 1 |
| AVGDD | passed | 1 | 1 |
| CUMDOSE | passed | 1 | 1 |
| AGE | passed | 1 | 1 |
| AGEGR1 | passed | 1 | 1 |
| AGEGR1N | passed | 1 | 1 |
| AGEU | passed | 1 | 1 |
| RACE | passed | 1 | 1 |
| RACEN | passed | 1 | 1 |
| SEX | passed | 1 | 1 |
| ETHNIC | passed | 1 | 1 |
| SAFFL | passed | 1 | 1 |
| ITTFL | passed | 1 | 1 |
| EFFFL | passed | 1 | 1 |
| COMP8FL | passed | 1 | 1 |
| COMP16FL | passed | 1 | 1 |
| COMP24FL | passed | 1 | 1 |
| DISCONFL | passed | 1 | 1 |
| DSRAEFL | passed | 1 | 1 |
| DTHFL | passed | 1 | 1 |
| BMIBL | passed | 1 | 1 |
| BMIBLGR1 | passed | 1 | 1 |
| HEIGHTBL | passed | 1 | 1 |
| WEIGHTBL | passed | 1 | 1 |
| EDUCLVL | passed | 1 | 1 |
| DISONSDT | passed | 1 | 1 |
| DURDIS | passed | 1 | 1 |
| DURDSGR1 | passed | 1 | 1 |
| VISIT1DT | passed | 1 | 1 |
| RFSTDTC | passed | 1 | 1 |
| RFENDTC | passed | 1 | 1 |
| VISNUMEN | passed | 1 | 1 |
| RFENDT | passed | 1 | 1 |
| DCDECOD | passed | 1 | 1 |
| DCREASCD | passed | 1 | 1 |
| MMSETOT | passed | 1 | 1 |
| RANDDT | passed | 1 | 1 |
| export | passed | 1 | 1 |

Frozen SHA-256: `08a3b330812cabf474bd526bda3c457b1a1cb936b9085b5f68a5dda8e4450949`. Raw clinical artifacts remain private. Aggregate provenance is in audit.json.


This is the public aggregate report. Raw clinical artifacts, full model advisory text, generated code and provider requests remain private. Publication source hashes and a cross-architecture comparison are in the parent directory.
