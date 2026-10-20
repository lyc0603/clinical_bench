> Historical pilot protocol. For the revised main experiment, use
> [the independent-session workflow](main-experiment-workflow.md).

# Pilot protocol

## Question

Does P21 feedback improve study-level ADaM conformance beyond equal-time
self-review, and how does this effect differ across provider models?

## Pilot and main experiment

Pilot: one provider model, one independent generation, one repair iteration in
each branch. This is an infrastructure and usability check, not a model ranking.
Main experiment: three models, three independent generations each, one repair
iteration per branch. This requires 27 agent calls, plus rebuilds and validations.
Do not claim statistical power from this sample size. A second study would be
needed for stronger generalization evidence.

## Inputs and runtime

Use an allowlisted snapshot of SDTM, SAP and legacy metadata. No prior agent
programs, repaired outputs, investigations or reference ADaM are supplied.
Legacy Define contains ADaM metadata and is deliberately provided to all models;
the task is not generation from SAP alone. Requirements are the same 13 ADaM
domains across models. Pin the actual image ID, standards/CT, validator binaries,
configuration, model IDs, prompts, budgets and source hashes before the main run.

## Branches

Both branches copy the same initial package. Self-review never receives P21
reports, scores or diagnostics. The feedback branch receives the preceding
P21 report and scores. Both receive a fixed number of equal-time agent calls;
there is no early stopping based on hidden scores. Agent containers do not mount
the evaluator, host home, credentials directory or other trial outputs. API keys
are supplied only through the relevant provider's environment variables.

Execution uses fresh Docker-local volumes per call. Frozen inputs are copied
into a volume mounted read-only by the agent; the workspace has a separate
writable volume. Outputs are copied back after completion or timeout, preserving
deletions. This avoids small-file-operation overhead on macOS shared mounts.
The runtime, runner and image hashes must remain fixed within a study run.

## Evaluation

Primary endpoint: reduction in the number of dataset-rule pairs with findings.
Paired feedback advantage = final self-review pairs minus final feedback pairs.
Positive values favor feedback. Secondary outcomes: finding instances, distinct
rules, package completion, new rules, record-count changes, reproducibility,
reported tokens/cost and agent wall time. Retain failures and denominators; do
not rank models solely by eligible-attempt averages.

P21 configuration: Java client 1.0.9, FDA 2508.1, ADaMIG 1.3, CT 2026-03-27,
with AE/DM/EX support. This runner performs ADaM validation with Define metadata,
not an independent standalone Define-XML validation. `MedDRA not configured`
is an explicitly allowed qualification in the example configuration, and thus
MedDRA-dependent coding checks are outside scope. Other installation warnings
invalidate scoring. Compared packages must have identical qualification status.

Missing domains or reports, mismatched configuration and failed agent calls
are failures, never zero-findings successes. Nonzero P21 exit codes are retained;
report evidence determines whether validation completed. Findings can overlap,
and raw instance counts are not percentages of incorrect records.

Rebuild all artifacts in a separate network-disabled container after deleting
generated outputs. Exact XPT and Define byte hashes must match. This is strict
reproducibility, including timestamps; choose deterministic production writing.
Record-count changes require review and are not automatically good or bad.
The evaluator does not certify analysis-value preservation or SAP correctness.

## Pilot acceptance

- Input and code hashes are recorded.
- Both branches start with identical output hashes.
- Only the feedback branch sees reports.
- All requested domains are processed and fresh P21 reports are produced.
- Rebuild succeeds and reproduces artifacts.
- Each stage retains trajectories and usage (or explicit missing usage).
- Paired summaries are generated; invalid attempts remain visible.

If model defaults, timeouts or reproduction criteria need adjustment, do so using
pilot evidence and freeze a new protocol before the main experiment. Never mix
pilot runs with the final study results.

## Current main study (separate from this pilot)

The current main study uses [the current protocol](main-study-protocol.md),
[the independent-workflow guide](main-experiment-workflow.md) and
[the current scoring contract](../main_experiment/scoring-rules.json).
Use `python -m main_experiment freeze`; this pilot's paired design and freezer
must not be used for the current study. The superseded paired main-study
proposal is retained only in [the archive](archive/legacy-paired-protocol.md).
