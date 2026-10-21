# Exploratory pre-experiment: six workflows, 16 metrics

[Comparison table](metrics.md) · [Excel workbook](metrics.xlsx) · [CSV](metrics.csv) · [Machine-readable results](metrics.json) · [All auxiliary checks](auxiliary-checks.csv) · [Evidence audit](evidence-audit.json)

Three fresh self-review workflows completed, alongside three previously observed P21-feedback qualification smokes. Both conditions use OpenCode; “ReAct” is not a separate condition. These are six selected examples, one per model and condition, excluded from the formal main study. No main-study workflow has started. Earlier failed qualification attempts remain in private evidence and are not included in these cost totals.

## Interpretation

All six delivered 13 readable datasets. Final packages reproduced semantically in five examples; Google self-review failed independent reconstruction because its program did not create the required output directory in a clean workspace. This failure is retained.

P21-feedback had initial/final dataset-rule pair counts of 26→24 (OpenAI), 26→24 (Anthropic), and 49→15 (Google). Content guards flagged OpenAI and Google, so their reductions are not accepted as guarded improvements. Anthropic had no detected regression, although its selected NPI coverage check retained 20 extra records.

Self-review final qualified counts were 26 pairs for OpenAI and 26 for Anthropic. Their initial P21 evaluations were unavailable, so qualified reductions cannot be computed. Both Google self-review P21 evaluations were unavailable. Row 4 now prominently displays all three initial saved-report counts (pairs, instances and distinct rules) for each self-review model as unqualified observations. The qualified initial scores remain unavailable; these observations are not substituted scores. In particular, the table cannot establish a treatment effect or rank models reliably.

The three new self-review workflows cost an estimated $2.4424 (OpenAI), $7.0374 (Anthropic), and $1.4284 (Google), totaling approximately $10.91. These are telemetry estimates, not reconciled invoices. Runtime and token measurements are descriptive; provider accounting conventions differ.

## Technical issue requiring review before the main study

The frozen evaluator rejected four self-review checkpoint evaluations with `P21 runtime drift during validation`. A diagnostic on a copy of Google initial artifacts found changes in the P21 client log and `app.data`; only the latter is exempted by the current integrity rule. The client log also contained callback exceptions. The original temporary cache diffs were not retained, so the diagnostic does not prove the exact cause of each original rejection or establish that callback exceptions are harmless.

Original scores, reports and agent outputs were preserved; no agent was rerun, no score was promoted, and sealed main code was not changed. Scheduling paused after Google for adjudication and seal verification, then resumed with the same controller. One host-only diagnostic overlapped Google review, limiting timing comparability; diagnostic feedback was not supplied to the agent. Resolve and independently review the evaluator/runtime behavior before launching the formal main study. Any evaluator change requires an explicitly versioned amendment, fresh freeze and qualification as appropriate.

## Evidence and scope

The audit checks all six retained workflows against checkpoint/workspace manifests, session continuity, normal completion, requested model identity, frozen prompts, and baseline migration hashes. Newly added Finder `.DS_Store` metadata is excluded from equality checks with paths and hashes recorded; no evidence was deleted. This is local consistency verification, not an externally signed attestation. Source evaluation hashes and the unchanged main seal are recorded in the public audit.

The original 18 reporting items are retained in 16 rows by combining workflow completion with delivery, and initial with final finding counts. Auxiliary checks cover selected derivations and coverage only; they do not establish comprehensive clinical correctness. Full severity mapping was unavailable (findings reported as Unassigned). Planned-check coverage is reported because the applicable denominator has not been adjudicated. Only aggregate results are published; clinical records, raw sessions, credentials and dictionaries remain private.
