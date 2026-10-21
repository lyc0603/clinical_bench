# P21 runtime follow-up (offline evidence)

The original 12 checkpoint logs were inspected without rerunning agents or changing scores. [Aggregate log audit](p21-log-audit.json) records hashes and exception/completion-marker counts.

| Condition | Model | Initial callback errors | Final callback errors | Initial / final qualified P21 status |
| --- | --- | --- | --- | --- |
| P21 feedback | OpenAI | 0 | 0 | valid / valid |
| P21 feedback | Anthropic | 0 | 0 | valid / valid |
| P21 feedback | Google | 0 | 0 | valid / valid |
| Self review | OpenAI | 3 | 0 | unavailable / valid |
| Self review | Anthropic | 2 | 0 | unavailable / valid |
| Self review | Google | 6 | 4 | unavailable / unavailable |

All 12 logs contain one `Validation: Process completed.` marker. Every unavailable checkpoint has `NoSuchElementException` callback exceptions; none of the eight valid checkpoints does. This association does not establish whether findings are complete or correct. Successful completion text and a parseable report are insufficient evidence that these exceptions are harmless. The eight accepted original executions returned code 5; this observation alone is not a documented interpretation of that code.

The code hashes the copied runtime cache before and after validation, exempts `lib/engines/app.data`, then rejects any other difference. A prior retained diagnostic changed the client log as well as `app.data`. The original evaluator discards the temporary cache after rejection and does not preserve its manifest diff or execution metadata in the failed conformance result. Thus an error log change can mask the specific underlying error behind a generic runtime-drift message.

Two additional local diagnostic attempts were blocked by network availability in the execution sandbox. They produced no report and logged failed engine metadata download, failed health check and the client's internet-required error. They are retained separately in private diagnostics, excluded from all study results. This also demonstrates why a generic drift message should not be treated as a unique diagnosis. Subsequent network-enabled diagnostic execution was rejected by automatic approval review and has not run; explicit authorization is pending because the client's outbound payload is not fully characterized.

## Proposed amendment for review, not yet applied to the sealed evaluator

1. Always retain before/after runtime manifests, changed paths, execution return code/timeout, stdout and client logs, including failures. Preserve copied runtime state when validation fails.
2. Distinguish immutable engine/configuration/dictionary changes from explicitly enumerated mutable state/log paths. A mutable log change alone should not be described as executable or configuration drift. Unknown paths remain a rejection.
3. Independently detect client errors, including callback exceptions. Keep affected reports unavailable until their effect is resolved or a justified rule is independently validated; simply exempting logs must not promote them to valid.
4. Investigate callback behavior using separate diagnostics on fixed existing artifacts. Repeated finding agreement may aid investigation but cannot prove exceptions harmless. Do not select a successful retry as a replacement observation.
5. Apply any approved evaluator change consistently across conditions under a versioned amendment and a new qualification/freeze. Retain original scores and publish any retrospective rescoring separately.

`pre_experiment/diagnose_p21.py` invokes the existing evaluator while disabling only temporary-cache cleanup, retains diagnostic artifacts and checks that source datasets/cache are unchanged. It does not import credentials or call model APIs. Its repeated report counts remain unqualified and never rewrite checkpoint evaluations. Network-enabled use requires authorization for P21 connectivity. No sealed main file, lock, score or formal schedule has changed.
