# P21 diagnostic and integrity amendment

Status: implemented in code; not yet qualified or frozen for the main study.

This amendment changes evaluator failure classification and evidence retention. It does not repair the P21 Java client, establish that its callback exceptions are harmless, or replace any recorded observation. The original pilot outputs and freeze lock remain historical evidence.

## Behavior

The evaluator permits changes only to `lib/engines/app.data` and the exact client-log path `lib/p21-client-1.0.9.log`. These changes are recorded. Any other added, removed or changed cache file remains an integrity failure. Configuration, engines, dictionaries and unknown log paths are not exempted.

Client error markers are checked independently in newly written client-log content and captured stdout. ERROR messages, uncaught thread exceptions and Java/net exception markers reject the report as `client_runtime_error`, even if a report exists or stdout says processing completed. This is a conservative technical gate, not a claim that all software failures can be detected by log scanning. Existing report configuration, installation-warning and dataset-coverage checks remain active. Existing exit-code handling is unchanged; execution metadata is now retained for failed gates as well as successful parses.

Failure codes distinguish immutable runtime changes (`runtime_integrity`), client errors (`client_runtime_error`), timeouts (`timeout`), missing reports (`missing_report`) and other evaluation errors (`evaluation_error`). Report parser rejection remains visible in its existing conformance status.

Every invocation saves `p21-runtime-before.json`, `p21-runtime-after.json`, `p21-diagnostics.json`, stdout and the client log when present. Failed or unusable validations retain their copied cache in `p21-failed-runtime/`; successful validations remove the disposable copy. Retained caches can be large and contain licensed runtime/dictionary material: keep these existing private experiment directories private and do not commit them. The source cache is never modified by this evaluator.

A pre-existing report or diagnostics file is rejected before execution. Use a fresh directory for an explicitly authorized diagnostic; do not overwrite a checkpoint or select a successful retry as its replacement score.

## Effect on the existing pre-experiment

The six-example table, all original evaluations and the old freeze are unchanged. This amendment would classify the observed callback exceptions as client errors rather than generic cache drift. It does not promote their reports to scored observations. No new model call or network-enabled P21 run was performed to qualify this amendment.

## Required before formal main-study launch

1. Independently review the revised rules and unresolved client callback exceptions.
2. Qualify the installed client/evaluator on fixed existing artifacts in separate evidence directories; resolve or explicitly adjudicate exceptions. Network-enabled client diagnostics require authorization for client connectivity.
3. Apply qualification rules consistently to both conditions and all providers. Record any retrospective rescoring separately, retaining all original values and failure denominators.
4. Run preflight and create a new versioned freeze lock and appropriately bound receipts. Do not overwrite the previous lock or bypass its mismatch. The changed evaluator/test/workflow-document hashes intentionally invalidate that old code seal.
5. Launch the main study only after review and fresh qualification/freeze pass.

Unit tests use synthetic artifacts and mocked client execution. They cover benign log mutation, client-error rejection despite a report, actual immutable-file drift, timeout/missing-report classification, evidence retention and refusal to overwrite previous evaluations. They do not substitute for testing the actual P21 client.

## Declared single-processor validation mode

Network-authorized qualification reproduced callback exceptions on an unchanged historical OpenAI package: one run was accepted, the other rejected despite identical report aggregates. The attempt was stopped and retained. A separate two-repeat diagnostic on the prior Google initial package using `-XX:ActiveProcessorCount=1` had no client errors and identical full-coverage aggregates (77 pairs, 945842 instances, 10 rules). This supports investigating a concurrency-dependent exception; it does not establish the internal root cause or prove every output safe.

The evaluator accepts an explicit `p21.java_options` setting of `[]` or `["-XX:ActiveProcessorCount=1"]`. The actual argument is passed before `-jar` and recorded in the runtime seal and configuration. New paired qualification and execution use the latter uniformly, retaining all client-error gates. This affects host P21 only; model/container CPU resources and agent prompts are unchanged. Full fixed-artifact qualification is required after this amendment. Previously rejected results are not promoted.
