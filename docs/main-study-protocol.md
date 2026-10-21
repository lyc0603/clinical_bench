# Current main-study protocol

This is the current scientific protocol. [The workflow guide](main-experiment-workflow.md)
contains setup, qualification, freeze, execution and recovery commands.
Use **`python -m main_experiment`** for every current main-study operation.
Historical paired designs and their freeze script are archived and must not be
used to freeze this experiment.

## Design and allocation

Three prespecified models × two conditions × three repetitions give **18
independent workflows**. Each workflow has its own generation, followed by one
repair in the **same persistent OpenCode session**: at most 36 agent phase
invocations, not a fixed number of provider API requests. There are no shared
initial generations and no paired comparison between conditions. Both groups
use the same initial prompt; the condition is disclosed only after checkpointing.

The default schedule seed is **20261018**, as recorded in
[the configuration](../main_experiment/config.example.json). It shuffles workflow
order; it is not a provider sampling seed. The actual config and schedule are
sealed before execution. Any intentional seed change requires a new freeze.

Agent execution has **no time cap** (`phase_seconds: null`), in generation or in
any repair path. Each agent has 4 CPUs and 8 GB memory. Rebuilds retain a separate
1,800-second limit; P21 retains a 900-second limit. There is no fixed maximum
agent runtime, token consumption or API cost. No silent retries, model swaps,
additional repairs or score-driven early stopping are allowed.

## Prespecified model selection

The planned models are `openai/gpt-6.1-sol`,
`anthropic/claude-sonnet-5-5` and `google/gemini-3.1-pro-preview`.
Sonnet 5.5 replaces Sonnet 4.6 in the current configuration at the investigators’
request before main-study execution. It represents the current Sonnet generation
at this selection date (2026-10-19), rather than an application default or a claim
of equal capability or compute across providers. See the
[official Sonnet 5.5 documentation](https://platform.claude.com/docs/en/models/sonnet-5-5/overview).
The actual API/model availability and tool compatibility must pass the excluded
provider qualification; this configuration update alone does not establish them.
All previous smoke receipts and freeze locks must be regenerated before launch.
Retain requested/reported model IDs, parameters and execution dates; the preview
backend does not imply immutable weights. Do not mix model versions within the
main study or substitute models automatically.

## Inputs and derivation conventions

Frozen inputs are the canonical 22 source XPT files, SAP.pdf and exported
specifications.json. TS uses Windows-1252. Input preparation records the original
workbook hash and explicit ADVS.TRTA predecessor correction. The workbook is not
silently modified; proposals and alternate Dataset-JSON copies are excluded.
Agents receive no reference ADaM or independent evaluator/results.

NPI randomization uses a unique distinct complete **SV VISITNUM=3** date, with
**no DM.RFSTDTC fallback**. Baseline selection uses **WDAY <= 1**; ties use distance
to target, earlier date, then QSSEQ. The selected source checks, tolerances and
qualifications are defined in
[the current scoring contract](../main_experiment/scoring-rules.json) and
[the evaluator](../main_experiment/derivation.py).

P21 pins are client 1.0.9, FDA engine 2508.1, ADaMIG 1.3 and CT
2026-03-27. **English MedDRA 8.0 is mandatory**, with hashed PT/SOC/LLT/HLT/HLGT
files. Missing dictionary configuration is not an allowed report qualification.
Masked HLT/HLGT provenance remains an explicit study limitation.

## Equal repair opportunity and separate outcomes

Both conditions receive one repair opportunity regardless of initial delivery
completeness. Self review sees only its own artifacts and supplied inputs.
P21 feedback receives only a usable initial P21 report, including a partial
report. If no usable report exists, it receives a standard report-unavailable
message and continues self review. Its original group assignment is retained.
No independent correctness result or installation diagnostic reaches the agent.

Report usability requires a fresh parseable report, pinned versions, no
installation problems and a nonempty validated subset of actual produced domains.
It does not require all 13 planned datasets. Delivery completeness and validation
coverage are separate endpoints. Missing/invalid results are unavailable, never
zero findings. Reduced dataset coverage cannot count as conformance improvement.

Retain all **18 planned workflows**, nine per condition, including failures,
fallbacks and unavailable endpoints. Report completion, dataset coverage,
complete deliverables, reconstruction and selected correctness separately.
Within-workflow finding reductions require complete deliverables and full usable
validation at both checkpoints. Partial-report counts are descriptive only.
No composite conformance/correctness score or paired condition analysis is used.
Semantic reconstruction and byte equality are separate endpoints; only ODM
CreationDateTime is normalized in Define XML.

## Isolation, qualification and freeze

Web tools are denied. Agent IPv4/IPv6 egress is restricted to the assigned
provider gateway and TCP localhost; direct web, downloads and DNS are blocked.
Gateway policy/rules/probes and connection decisions are retained. TLS payloads
are not inspected, so provider-native search arguments are governed by the tool
settings and prompt rather than payload filtering. Provider smoke qualification
must verify the actual pinned OpenCode image. No unrestricted-network fallback
is permitted.

Require three excluded provider qualification smokes before
**`python -m main_experiment freeze`**. The lock covers canonical inputs and
provenance, current protocol/workflow documents, code, prompts, scoring rules,
schedule, config, image and validation runtime/dictionaries. Changing a pin
requires fresh qualification and a new lock. The current runner verifies this
lock before scheduling; historical paired-protocol locks are incompatible.

## Agent completion qualification

Completion requires successful process/session evidence and an exported, completed
**new** assistant turn with a normal finish under the provider-specific
[completion policy](../main_experiment/completion-policy.json). A missing final
stdout `step_finish` can be reconciled against stored session evidence; unknown,
conflicting, truncated or unfinished turns are not silently accepted. Repair must
extend the pre-invocation history. Outputs are still scored independently.

Both smoke phases must record raw/normalized finish reasons and the current
policy hash. Freeze rejects receipts lacking that provider-specific proof.
No synthetic test is a substitute for qualifying the actual pinned OpenCode/API
combination. See the workflow guide for the exact evidence and failure checks.

## Failure recovery

`.running` is an exclusive **controller concurrency guard**, not the record of
whether an attempt may be retried. A normal return, Python exception, SystemExit
or KeyboardInterrupt that unwinds `finally` removes this guard. SIGKILL,
`os._exit`, power loss or another termination that bypasses `finally` can leave it
behind. Before removing a leftover guard, verify no controller is still active.

Workflow `state.json`, sealed checkpoints and the bound freeze lock independently
prevent silent retries. A failed, started or interrupted workflow requires human
adjudication even if `.running` was cleaned up. Removing `.running` alone never
authorizes retrying an agent phase. Completed workflows are skipped only after
their checkpoint manifests are verified.

Historical materials: [paired protocol](archive/legacy-paired-protocol.md),
[paired scoring rules](archive/legacy-paired-scoring-rules.json),
[pilot commands](archive/legacy-pilot-readme.md). These document superseded designs,
not alternatives for the current main study.

## Content-loss safeguards

Each checkpoint retains a host-only content profile for every planned dataset:
row counts, columns, nonmissing counts, hashed subject identities and hashed
subject/PARAMCD identities with record counts. Blank strings count as missing.
The agent receives neither these profiles nor guard findings. Repair opportunity
and group assignment are unchanged.

Reports retain raw complete-delivery/full-validation P21 pair reductions, but
`guarded_pair_reduction` and `improved_without_detected_regression` are unavailable
when screening detects an empty dataset, row/column/value/subject/parameter
coverage loss, increased independent NPI errors, reduced assessed NPI coverage,
or missing screening evidence. Flags remain in the original allocation and all
planned denominators; no automatic waiver or extra repair is authorized.
Legitimate duplicate removal can trigger a conservative review flag. Such flags
are not proof of misconduct or incorrect derivation and cannot silently be
reclassified as successful improvement. Report raw conformance, guard flags and
unavailable counts separately.

This screening detects selected losses, not arbitrary value corruption or errors
already present at both checkpoints. TTE conditional consistency is not treated
as an independent correctness oracle. No detected regression is not full ADaM
correctness or submission readiness. Changes require fresh smoke qualification
and freeze; old evaluations lacking profiles cannot receive guarded success.

## P21 version evidence

The ADaM Model 2.1 target is a specification convention, not an independently
reported P21 runtime version. Qualification checks the report's actual FDA engine,
client, CT, MedDRA and exact ADaM-IG 1.3 configuration filename. The seal also
parses and hashes the installed configuration declaring ADaM-IG version 1.3.
Do not require or claim a base-model version string absent from this report.
This corrects a false report-rejection rule, not any clinical finding.

## Prospective amendment: technical smoke eligibility (2026-10-20)

Before any main-study workflow, smoke eligibility is aligned with the primary
P21 conformance objective. Both checkpoints must have all required deliverables,
a usable full-coverage P21 report and successful semantic reconstruction. Existing
normal completion, provider identity and same-session requirements remain in force.
Auxiliary NPI/TTE errors or unavailable checks and content-loss flags remain
reported outcomes; they do not exclude a provider. Coverage guards still restrict
claims of effective improvement. Apply this rule equally to all providers and
conditions; retain all 18 main workflows in the planned denominator.

This amendment follows inspection of excluded Google smoke evidence; it is not
a correction of its generated programs. Preserve the original failed receipt and
all checkpoint artifacts. Do not rerun until a favorable outcome is obtained.
The amendment changes the seal: old receipts cannot freeze the revised study.
Offline technical reassessment alone is not a current-seal qualification receipt.
Any evidence reuse requires an explicit, audited migration establishing unchanged
inputs, prompts, model/runtime, completion policy and evaluation implementation;
otherwise obtain fresh excluded smokes. No main workflow may start with stale
receipts or without a new freeze lock.
