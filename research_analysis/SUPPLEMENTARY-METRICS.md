# Retrospective delivery, variable coverage and failure-stage analysis

These three exploratory metrics were requested on 28 October 2026, after pilot outcomes were available. They extend the public 16-metric, 24-endpoint report without replacing any of its existing measurements. No generation, repair, rebuild or validator is rerun. This analysis does not alter the frozen main-study protocol or eligibility rules.

## Definitions

17. **Dataset Delivery Rate:** number of the thirteen expected lowercase XPT files that are readable, divided by thirteen. Missing and unreadable datasets do not contribute; extra datasets cannot increase the numerator. Readable empty datasets still count as delivered, so this is not record completeness or task success. Readability uses an existing full-read evaluator profile for a file verified against its retained manifest, plus a fresh metadata read; otherwise the analysis attempts a full read.
18. **Variable Coverage:** number of expected dataset-variable pairs with both the exact, case-sensitive name and the specified Numeric/Character XPT storage class, divided by 531 from the frozen specification inventory. Each expected variable counts once within its dataset; value-level metadata entries do not add variables. Missing datasets contribute zero. If a file exists but cannot be read, its schema is unknown and the exact overall coverage rate is unavailable; the confirmed matched count is retained. Lengths, formats, variable labels, values, subject records and derivation correctness are outside this metric. SAS dates belong to numeric storage for this purpose.
19. **Failure-stage distribution:** nonexclusive phase-level indicators for input reading, code execution, dataset export, Define-XML generation, rebuilding and P21 validation. Each endpoint contributes at most one count to each stage/status within a phase, regardless of repeated error events. Initial, final and terminal views have separate denominators; terminal means initial for an initial-only endpoint and final otherwise. The views must not be added together.

Failure statuses are deliberately distinct:

- `failed`: direct observed execution failure or failure to deliver a required output. Missing expected datasets are a dataset-delivery failure, not proof that an export command was executed and failed. Missing or malformed/non-ODM XML is a Define-XML delivery failure; a parseable ODM document is not proof of complete Define-XML conformance.
- `blocked`: rebuild entry point or validator prerequisites are missing. Downstream blockage is not an independent root cause.
- `no_failure_observed`: no failure was found by the limited checks, not proof of clinical correctness or comprehensive stage success.
- `not_observed`: no code execution was observed in the phase.
- `usable_report`: the original evaluator accepted the P21 report. A usable report can contain conformance findings; those findings remain in the original metrics and are not validator execution failures.
- `unavailable`: required evidence is absent or insufficient.

Input-reading and code-execution errors require actual current-phase tool events. Historical final history exports contain earlier messages, so the classifier uses each phase's JSONL tool events and deduplicates tool-part IDs. It considers actual tool errors and recorded nonzero execution exits, not an assistant's claim that a command ran. Tool-schema errors that cannot be assigned to the six stages remain `unclassified_tool_errors`; provider/controller failures remain a separate flag. An observed error still counts when the agent later recovers within that phase.

P21 classification uses the original evaluation, including its original failure code. Later host reassessment can produce a usable report, as already shown in metric 3, without erasing the original failure. These are different observations.

## Source integrity and missing evidence

The analysis resolves every endpoint to a private source folder and checks all original report receipt hashes, except externally stored current-revalidation entries that are not used by the new metrics. All measured datasets, Define-XML and rebuild entry-point files are checked against the saved workspace manifest; tool logs are checked against the checkpoint manifest where a completed checkpoint exists. Newly used evidence hashes are published. Existing evaluation/agent/state receipt hashes remain unchanged. No unrelated cache files need to be read or republished.

Where a failed controller nevertheless retained an evaluated workspace, its observed delivery and schema can be assessed. This is not reclassification as a successful workflow. Missing snapshots remain unavailable, not zero. Retained raw data and logs are never changed by the analysis.

## Interpretation

The distribution describes the table's endpoints, not independent trials: some historical initial-only and self-review columns share an initial generation. Settings and environments also differ across historical extensions. Stages are nonexclusive and can reflect downstream consequences. Do not sum stage counts into a total failure rate or treat the pooled endpoints as independent samples. The original sixteen metrics remain the authority for P21 counts, auxiliary checks, costs and workflow completion.

## Reproduction

Use the pinned evaluator Python environment with `pyreadstat` and `lxml`. Provide a private JSON source map containing an ordered list of objects with `index` (0–23) and `source` (absolute retained workflow directory). The script verifies original receipt hashes before using each source.

```
python -m research_analysis.supplementary_metrics \
  --previous pre_experiment/results/open-models-2026-10-25/metrics.json \
  --source-map /private/path/source-map.json \
  --specifications /private/path/prepared-inputs/specifications.json \
  --out /path/to/new-report-directory
```

The output directory must be new. The existing artifact-tool workbook builder accepts either sixteen or nineteen metrics. Its nineteen-metric output adds typed coverage numerators/denominators, formula-calculated rates and a failure-stage distribution sheet. Only aggregate metrics, file hashes and sanitized audit data may be published; clinical records, raw logs, specifications and credentials stay private.
