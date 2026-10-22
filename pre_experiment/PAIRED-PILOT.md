# New paired initial-only and self-review pre-experiment

Status: scripts implemented and tested offline. Actual P21 qualification has not run. No new model call has started. This batch is excluded from the main study and separate from the previous nonconcurrent six-example pilot.

Each model generates one new initial package. Its immutable initial checkpoint is the initial-only endpoint. The same session then performs one self-review, producing the second endpoint. There are three generation sessions and six paired endpoints, not six independent generations. Initial-only incurs generation cost only; self-review cumulative cost includes generation plus review. The shared generation cost must not be counted twice as actual batch spending. Repair-only metrics are not applicable to initial-only, not zero. Analyses must account for the pairing and one observation per model, without a powered treatment-effect claim. The formal 18-workflow main-study design is unchanged.

The runner retains `initial-only.json` after the initial evaluation even if review subsequently fails. It links the initial checkpoint and hashes its evaluation and workspace. This endpoint shares source evidence with self-review; no data are copied back into a live session. P21 output and evaluator diagnostics remain host-only and are not supplied as self-review feedback. Frozen generate/self-review prompts and existing network restrictions are reused.

A previously passing smoke is not sufficient for this batch. The qualification script tests all 12 fixed historical checkpoints (three models × two conditions × initial/final), twice each, under the installed evaluator. All 24 diagnostic validations must be accepted by the evaluator with complete coverage and matching pair sets and aggregate counts across repeats. Parseable reports rejected by a runtime gate do not qualify. This tests a fixed artifact panel; it cannot guarantee that new model outputs will never trigger client exceptions.

## Execution order

Use the existing dedicated Python environment, configured Docker context and private input/config paths. All evidence and lock paths below must be outside the Git checkout. Obtain authorization for P21 client connectivity before running the qualification command; the client may contact external services. No qualification or model command below has been executed as part of this code update.

```sh
# 1. Existing-artifact P21 qualification. No model calls; 24 P21 validations.
python -m pre_experiment.qualify_p21 \
  --config /private/study/config.local.json \
  --baseline-root /private/study/main-study-current \
  --self-review-root /private/study/excluded-self-review-previous \
  --out /private/study/p21-qualification-new --execute-p21

# 2. New pilot-specific lock. Old main-study lock cannot be reused.
python -m pre_experiment.paired_pilot freeze \
  --config /private/study/config.local.json \
  --qualification /private/study/p21-qualification-new/qualification.json \
  --lock /private/study/paired-pilot-new.lock.json

# 3. Paid execution only after qualification and review.
python -m pre_experiment.paired_pilot run \
  --config /private/study/config.local.json \
  --lock /private/study/paired-pilot-new.lock.json \
  --env-file /private/credentials.env \
  --out /private/study/paired-pilot-new --execute
```

The qualification receipt binds the current inputs, configuration, runtime, evaluator and pilot tools. The new lock also binds the endpoint design and tools. Checks run before and after each model workflow. Changes require a new qualification and a new lock; earlier locks and results are retained. All providers run serially with no agent execution time cap. Existing technical timeouts remain for P21 and reconstruction.

Any model failure or unusable P21 endpoint stops scheduling for adjudication, preserving all attempts and the `.running` marker. An initial-only receipt remains available if that endpoint was produced. The run is not silently retried, a technical failure is not counted as zero findings, and a failed provider is not dropped from the planned denominator. A usable partial report remains distinguishable from complete coverage. A reconstruction failure remains an observed artifact-quality outcome; do not fix model-generated code inside the evaluator.

The old six-example table must not be overwritten. Keep the new endpoint receipts, workflow states and initial/final evaluation files as the source for a separate paired results table. It must mark repair metrics not applicable to initial-only and disclose shared initial cost/timing, any unavailable scores and all failed attempts. The existing historical comparison exporter is for the prior independent pilot, not this paired design.

## Remaining qualification issue

The evaluator fix distinguishes mutable logs from immutable changes and rejects actual client errors independently. It has not fixed the P21 Java callback exception. If the fixed-artifact panel fails, inspect retained diagnostics and resolve/adjudicate that issue before paying for another generation batch. Do not weaken the gate merely to obtain scores. Source clinical data, raw logs, runtime caches, dictionaries and credentials stay private.

## Offline aggregate reporting

After execution, build a separate nine-endpoint table without touching the old six-example table:

```sh
python -m pre_experiment.report_paired \
  --paired-root /private/study/paired-pilot-new \
  --baseline-root /private/study/main-study-current \
  --qualification-root /private/study/p21-qualification-new \
  --out /private/study/paired-pilot-report
```

This exports 16 rows to Markdown, CSV and JSON with model/condition columns. Initial-only terminal scores and costs come only from the initial checkpoint. Repair outcomes are not applicable. Historical P21 conformance scores are taken from the accepted current qualification evidence under the same evaluator settings; original scores remain in the historical files. Other historical measurements remain from the original run. Missing or failed attempts remain visible. Do not label an empty planned table as completed results.

The new batch uses the declared P21 single-processor Java option after a separately retained concurrency diagnostic. The configuration and runtime seal bind this option; the model containers retain their original resource limits. The original multi-processor qualification failed and is preserved. The complete qualification panel must pass with this declared setting before new model calls.
