# Full-benchmark AI-431 adaptation: execution and review

This is an independently implemented exploratory adaptation of [PharmaSUG 2026 AI-431](https://pharmasug.org/proceedings/2026/AI/PharmaSUG-2026-AI-431.pdf), not original author software or a numerical reproduction. It targets all 13 benchmark datasets / 531 variables. It is excluded from the formal main study. See [fixed implementation contracts](../ai431_full/README.md).

## Five planned endpoints

| Endpoint | Service | Provenance |
|---|---|---|
| Claude Sonnet 5.5 | Anthropic official | Hosted provider model assertion |
| Gemini 3.1 Pro Preview | Google official | Preview version assertion |
| DeepSeek Flash | DeepSeek official | Hosted alias assertion |
| Sol 6.1 | xyz.llmapigateway.org | Third-party claimed upstream; never labelled official OpenAI |
| gpt-oss-20b | DeepInfra | Hosted open-weight model, not local execution |

One new clinical attempt per qualified endpoint, provider defaults, 32768 output/reasoning cap, three independent variable workers, serial datasets/models, two local execution/QC attempts. No transport retry or overall repair-time budget. Keep readiness failures in the planned cohort with unavailable performance metrics. Dollar cost needs verified billing. Token accounting includes reviews, repairs and rejected completions.

## Workflow

1. Verify the approved source package against its existing freeze. Copy only complete frozen SDTM/specification/SAP inputs and source schemas; no reference ADaM, historical generated programs or model outputs.
2. Test each issuer-specific API with synthetic text. Bind the exact observed response-model ID. An unavailable gateway does not authorize substitution or sending its key to official OpenAI.
3. Qualify offline wrappers, repeated-subject row alignment, missing character/numeric values, independent rebuilding and 13/531 synthetic export in the pinned Docker image. Synthetic fixture programs must never become clinical derivation/export implementations.
4. Create a verified non-cloud code/input/runtime snapshot. Freeze all four qualified endpoint roots **before** the first clinical request. Do not edit hash-bound packages, evaluator or specifications during this cohort.
5. For each dataset: retain an advisory model specification review; obtain row identities (ADSL randomized keys, otherwise a model-generated complete row universe); independently generate/execute/QC each variable; merge by exact row/subject keys; check selected cross-variable invariants. Failed variables/merge checks block that dataset and its dependents. Unrelated work may continue.
6. Generate one combined exporter for accepted datasets without value changes. Independently replay programs offline and evaluate terminal P21 plus existing selected NPI/TTE checks. P21 is never repair feedback. Complete validated coverage is required for the primary P21 metric. No complete initial P21 comparator exists.
7. Preserve every failure. Compress complete private evidence and verify every archived file hash before removing only duplicated raw execution directories. Review aggregate outputs and scan for credentials/records before GitHub publication.

## Commands

Use a dedicated Python3.12 environment with pandas2.2.3, numpy2.2.4, pyreadstat1.3.6 and the existing evaluator dependencies. Load local credentials only through the private environment file. Never put keys into commands, repository files or chat.

```bash
python -m unittest ai431_full.test_pipeline research_analysis.test_ai431_reporting
python -m ai431_full.readiness --out NEW_READINESS --env-file PRIVATE_ENV --execute
python -m research_analysis.qualify_ai431_full --out NEW_QUALIFICATION --source VERIFIED_SOURCE_ROOT --synthetic-exporter SYNTHETIC_ONLY_EXPORTER --env-file PRIVATE_ENV
python -m research_analysis.run_ai431_batch --batch NEW_BATCH --source VERIFIED_SOURCE_ROOT --readiness NEW_READINESS --qualification NEW_QUALIFICATION/receipt.json --env-file PRIVATE_ENV --execute
```

Run commands from the verified code snapshot. Environment-specific paths and clinical artifacts remain private. Never overwrite an existing batch/freeze. Fresh implementation changes require new versioned roots and explicit adjudication; they are not silent repeats.

The runner requires **10 GiB free before each model starts**. A disk prelaunch failure has zero clinical calls and no run-location/evidence archive. After space is restored, preserve the original orchestration state and resume only those unstarted roots:

```bash
python -m research_analysis.run_ai431_batch --batch EXISTING_BATCH --resume-unstarted --env-file PRIVATE_ENV --execute
```

This command refuses any endpoint with an existing clinical run-location or evidence archive. It cannot silently rerun a failed clinical attempt. Original prelaunch states/errors remain archived. Do not lower a frozen guard or erase a clinical failure to obtain a completed package.

```bash
python -m research_analysis.report_ai431_full --root COMPLETED_OR_FAILED_ROOT --out NEW_AGGREGATE_DIR
python -m research_analysis.publish_ai431_full --batch FINISHED_BATCH --summaries FINISHED_BATCH/aggregates --out NEW_PUBLIC_RESULT_DIR
```

The reporter verifies the full archive, frozen code/inputs, native identities/settings/usage, accepted programs/workspaces and final package hashes. The publisher retains all 19 metric labels, failed endpoint statuses and unavailable cells. XLSX is authored with the bundled spreadsheet tooling, visually reviewed and matched to CSV/JSON. Add final output hashes after the workbook is copied. Publish aggregates/code/hashes only.

## Initial 2026-11-05 execution status

Readiness passed for Claude, Gemini, DeepSeek and gpt-oss-20b; gateway Sol returned HTTP403 with no clinical transmission. Claude's 49 ADSL variables each passed local structural QC, but merged treatment-duration consistency failed. It delivered no accepted final package and did not reach P21. This is a selected cross-variable gate outcome, not proof that all 49 variables are clinically correct or that P21 failed.

The other three qualified endpoints were blocked before clinical start by insufficient disk space. Their frozen roots and original prelaunch errors are retained, with no generated clinical outcomes. Do not call the entire requested comparison complete until those first clinical attempts have run or the user explicitly defers them. Historical GxP/ADSL results and formal main-study freeze remain unchanged.
