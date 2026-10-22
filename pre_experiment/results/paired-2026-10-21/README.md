# Paired exploratory pilot: 16 metrics, nine endpoints

[Full comparison](metrics.md) · [Excel](metrics.xlsx) · [CSV](metrics.csv) · [Typed measurements and provenance](metrics.json) · [150 auxiliary check records](auxiliary-checks.csv) · [Evidence audit](evidence-audit.json) · [Gemini rebuild diagnosis](google-final-rebuild-diagnostic.json)

This batch began on 21 October 2026 and continued on 22 October after validator adjudication. Three fresh generation sessions produced initial-only endpoints and continued in the same sessions for self-review, without P21 feedback. These six paired endpoints are compared descriptively with three previously observed P21-feedback smokes. Both interventions use OpenCode; “ReAct” denotes the P21-feedback condition here. The formal main study was not started. The [earlier independent self-review pilot](../2026-10-21/README.md) remains archived separately.

| Requested model | New initial-only pairs | New self-review final pairs | Historical P21-feedback initial → final pairs | New self-review final semantic reproduction | Estimated new generation + review cost |
| --- | ---: | ---: | --- | --- | ---: |
| OpenAI `gpt-6.1-sol` | 26 | 26 | 26 → 24 | Passed | $2.4713 |
| Anthropic `claude-sonnet-5-5` | 26 | 26 | 26 → 24 | Passed | $5.8021 |
| Google `gemini-3.1-pro-preview` | 64 | 58 | 49 → 15 | Failed | $3.0682 |

## What these results show

All six new endpoints delivered 13 readable datasets. Current P21 scores are available for every endpoint. OpenAI and Anthropic self-review left both pairs and instances unchanged: 26/4,708 and 26/4,802 respectively. OpenAI triggered two content-guard flags; Anthropic had no detected regression. A lack of detected regression does not establish comprehensive correctness.

Google self-review reduced pairs from 64 to 58, but finding instances increased from 405,028 to 502,447. It resolved 16 pairs and introduced ten, with 20 content-guard flags, so guarded improvement is unavailable. Its final rebuilding program exited successfully but regenerated ADQSNPIX with 71,200 rows instead of the submitted 61,450; the other 12 datasets matched on data and checked metadata. This is a retained artifact reproducibility failure, not a timeout. Google NPI and TTE checks also remained largely unassessable: only 2/10 planned checks were assessable in each phase. See the separate aggregate diagnosis and auxiliary records.

Historical P21-feedback reductions were 2, 2 and 34 pairs. OpenAI and Google triggered content-guard review (six and 77 flags); Anthropic had no detected regression but retained 20 extra NPI records. These selected, nonconcurrent controls cannot establish a treatment effect or a model ranking.

Estimated new API spending was **$11.3415**, counting each initial generation once. Initial-only columns repeat their shared generation cost for interpretation; do not add them to cumulative self-review costs. Historical runs, earlier failed attempts, host-only validation, and assistant-chat costs are outside this total. Costs are telemetry estimates rather than reconciled invoices. Provider token/cache/reasoning accounting is retained with its comparability limitation. Original workflow timing excludes later host reassessments.

## Validator failure, amendment and retained evidence

Earlier qualification exposed P21 callback exceptions. A declared single-processor JVM option passed a 24-validation fixed-artifact panel. The new OpenAI model phases then both completed normally and reproduced, but the original final P21 execution failed while reading copied `app.data` state (`EOFException`). The controller stopped before Anthropic and Google. This failure remains **failed** in metric 1 and **original usable 0/1** in metric 3.

The [documented continuation](../../RECOVERY.md) removed only mutable `app.data` from an otherwise identical source cache, retained `-XX:ActiveProcessorCount=1`, and let P21 initialize state in separate disposable copies. A fresh 24/24 qualification panel passed, and both completed OpenAI endpoints independently passed twice with identical counts. These observations support this mitigation; they do not prove the internal cause or guarantee future availability. No proprietary client or licensing code was modified.

The recovery lock bound the new configuration, cache manifest, tools, source evidence and qualification. Only the previously unstarted Anthropic and Google sessions ran. No completed agent was rerun. Original OpenAI evaluations, reports and failure state were retained; accepted current reassessments are separate. Historical controls were also rescored under the current qualified configuration, preserving their original evaluations and other measurements. Metric 3 distinguishes original and current usability; rescoring does not retroactively erase a failure.

The [offline audit implementation](../../../research_analysis/audit_paired.py) verified frozen execution code, qualification hashes, cache-source integrity, source mapping, workspace manifests, model identity, normal agent completion, frozen prompts, same-session continuity and initial-only receipts. OpenAI's original final checkpoint manifest was never created because the evaluator gate raised; its earlier workspace manifest and raw histories were verified instead. The audit states this limitation and does not invent a retrospective seal. It is local consistency verification, not external signed attestation.

## Interpretation limits and reproducibility

There is one new generation per model, with two correlated endpoints; models are not repetitions. Historical controls were already observed and their earlier failed attempts remain in private evidence, outside this selected table. Technical amendments and continuation make this an exploratory feasibility analysis. Preview/backend drift, provider defaults, a single clinical study and unknown training exposure limit external validity. No significance test or causal conclusion is justified.

The table retains all 16 metrics, including costs, tokens, elapsed time, tool failures, content guards and selected auxiliary derivation checks. Auxiliary checks do not cover comprehensive clinical correctness; their applicable denominator has not been adjudicated. Severity remains Unassigned where the report mapping was unavailable. P21 report usability means the validation was accepted, not zero findings or clinical correctness. Full execution evidence remains private; only aggregate measurements and hashes are published.

With authorized access to the private frozen evidence, regenerate the aggregate files using `pre_experiment.report_paired`, then `research_analysis.paired_provenance`, with the recovery source map and fresh-state qualification. Run `research_analysis.audit_paired --help` for the independent consistency check. The source map is required to select the actual OpenAI directory and preserve its original failure. The CSV and Excel values were checked against every JSON table cell; 16 rows, nine endpoints and 150 auxiliary records matched. The formal main-study freeze and independent design review still require separate completion before launch.
