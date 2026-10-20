# Main experiment: independent generation and one same-session repair

This is the operational guide for [the current scientific protocol](main-study-protocol.md). The
`experiment/` runner and its protocol documents describe the earlier pilot.
Use `python -m main_experiment` for the revised main study.

**Implementation status:** offline protocol and synthetic scoring tests are
implemented. Real-provider sessions, the Docker image and P21/MedDRA integration
must pass three excluded smoke workflows on the experiment machine before
freezing or starting the main study. A passing CI job is not that qualification.

## Design to review

There are **18 independent workflows**: three exact provider/model IDs × two
conditions × three repetitions. Each workflow has its own initial generation;
there is no shared initial output between conditions. A deterministic shuffled
schedule is saved in the freeze manifest. Each workflow gets one generation
and one repair, with 4 CPUs and 8 GB memory and no agent execution time cap (`phase_seconds: null`). The maximum
is 36 agent phase invocations; total agent runtime and API cost have no fixed
upper bound. An agent phase can make many provider requests. External rebuild
and P21 validation retain their separate timeouts. Agents run until they finish,
fail, or are manually interrupted.

| Condition | Initial prompt | Repair history | Repair feedback |
|---|---|---|---|
| Self review | Identical generation prompt | Same OpenCode session | Own files and logs |
| P21 feedback | Identical generation prompt | Same OpenCode session | Own files/logs and its initial P21 XLSX only |

```mermaid
flowchart TD
  A[Private frozen source XPT + SAP + specs] --> B[Prepare canonical agent package]
  B --> C[Plan and local preflight: no model calls]
  C --> D[Excluded end-to-end smoke for each provider]
  D --> E[Freeze inputs, code, prompts, schedule and runtime]
  E --> F[Fresh container and generation session]
  F --> G[Pause container; seal initial checkpoint]
  G --> H[Controller: offline rebuild, P21, selected correctness]
  H --> I{Assigned condition}
  I -->|Self review| J[Resume same session without scores]
  I -->|Feedback| K[Provide usable full or partial report; otherwise self-review fallback]
  J --> L[Seal final checkpoint and evaluate externally]
  K --> L
  L --> M[Retain separate endpoints and all planned denominators]
```

Conditions are controller-side assignments. The initial prompt, workspace paths
and container environment do not reveal the assigned condition. Condition-specific
instructions appear only after the initial checkpoint. The repair uses explicit
`--session ID`; the controller checks the returned ID and that exported message
IDs preserve and extend the initial history. It never uses `--continue` or forks.
The persistent state volume holds OpenCode history; it is absent from evaluation.

## Code map for comments

| File | Review focus |
|---|---|
| [config.example.json](../main_experiment/config.example.json) | Exact models, budgets, datasets, local paths |
| [core.py](../main_experiment/core.py) | Design guards, input preparation, schedule and fingerprints |
| [prompts](../main_experiment/prompts/) | Identical generation and condition-specific repair instructions |
| [backend.py](../main_experiment/backend.py) | Docker boundaries, timeouts, sessions and raw telemetry |
| [completion.py](../main_experiment/completion.py), [completion-policy.json](../main_experiment/completion-policy.json) | Current-turn completion proof and provider-specific reason policy |
| [egress.py](../main_experiment/egress.py), [network/](../main_experiment/network/) | Mandatory provider-only gateway, namespace rules and bypass probes |
| [runner.py](../main_experiment/runner.py) | Checkpoints, feedback delivery, failures and reporting |
| [evaluate.py](../main_experiment/evaluate.py) | Offline rebuild, semantic/byte reproduction and P21 isolation |
| [derivation.py](../main_experiment/derivation.py) | Selected source-derived correctness checks |
| [scoring-rules.json](../main_experiment/scoring-rules.json) | Endpoints and qualifications |
| [test_main.py](../main_experiment/test_main.py), [test_scoring.py](../main_experiment/test_scoring.py) | Synthetic correct/corrupted examples |

## Local setup and input preparation

Run commands from the repository root. Keep all actual data, configuration,
credentials, dictionary files, transcripts, reports and results **outside Git**.
The example paths below are placeholders; substitute your private paths.

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r main_experiment/requirements.txt
cp main_experiment/config.example.json main_experiment/config.local.json
cp .env.example .env.local
```

Edit `config.local.json` to set absolute input, Java, P21-cache and dictionary
paths. Set `phase_seconds` to `null` in existing local configurations. Previous
smoke receipts and freeze locks must be regenerated after this protocol change.
Set the three provider keys in `.env.local` using literal `KEY=value` entries. Never commit or paste keys into review comments. The controller passes
only the selected provider's credential into each agent phase.

Build with an explicitly reviewed OpenCode release, then record it in your
experiment notes. The image's resolved content ID and CLI version are frozen;
no automatic upgrade or model substitution occurs.

```sh
docker build --build-arg OPENCODE_VERSION=1.19.0 \
  -t adam-experiment:main -f main_experiment/Dockerfile .
```

The release above is a candidate pin, **not a claim of qualified provider access**.
Preflight checks CLI capabilities and catalog membership; the excluded smoke
checks actual provider access and event/export compatibility.

```sh
python -m main_experiment prepare-inputs \
  --source /private/study/FinalizedInput/MainExperiment-Input \
  --out /private/study/prepared-inputs --fix-trta-predecessor
```

Preparation creates a new package with 22 authoritative XPT files, SAP.pdf and a
cell-value JSON export of all specification sheets. Dataset-JSON duplicates and
the proposal are not agent inputs. It excludes `.DS_Store`. TS's source encoding
is explicitly Windows-1252. The source workbook remains untouched.

The explicit correction flag changes the known ADVS.TRTA character predecessor
from `ADSL.TRT01AN` to `ADSL.TRT01A` in cells H16/J16/P16 of the exported specs.
Without the flag, preparation fails on this inconsistency. A sibling provenance
JSON records the original workbook hash, before/after cells and package hashes;
it is controller-only. Do not give the contradictory original workbook alongside
the corrected export. Review the exported specs and provenance before freeze.

## Review, qualify, freeze, execute

Planning does not need Docker, credentials or study files:

```sh
python -m main_experiment plan --config main_experiment/config.example.json
python -m unittest discover -s main_experiment -p 'test_*.py' -v
python -m unittest discover -s experiment -p 'test_*.py' -v
```

Local preflight reads input/runtime hashes, verifies all five MedDRA files,
checks credentials are present and inspects the image's OpenCode catalog/help.
It does not invoke a model, upload data, or prove provider account entitlement.

```sh
python -m main_experiment preflight
```

The next commands **incur API charges and send authorized study inputs to the
selected provider**. Each excluded smoke is a fresh generation plus a feedback
repair, including external rebuild/P21/correctness. Run once per provider:

```sh
python -m main_experiment smoke --model openai --out /private/study/smokes --execute
python -m main_experiment smoke --model anthropic --out /private/study/smokes --execute
python -m main_experiment smoke --model google --out /private/study/smokes --execute
python -m main_experiment freeze --smokes /private/study/smokes \
  --out /private/study/main --lock /private/study/main.freeze.json
python -m main_experiment run --out /private/study/main \
  --lock /private/study/main.freeze.json --execute
python -m main_experiment report --out /private/study/main
```

Freeze requires one qualifying receipt per provider matching the current
code/config/input/runtime fingerprint. Qualification requires completed reports,
semantic reproduction and assessable selected correctness checks at both smoke
checkpoints; correctness error counts need not be zero. It is deliberately strict
about unavailable checks. Inspect raw histories, session continuity, feedback
isolation, P21 dictionary recognition and runtime versions as part of local
qualification. Changing code, prompts, config, inputs, protocol/workflow documents, image, Java, dictionaries
or P21 rules invalidates the receipts and lock. A failed smoke is retained;
use a separately named smoke output directory for a deliberately adjudicated
replacement and document why. Never silently replace an attempt.

Main output is bound to the full freeze lock. The controller skips only completed
and sealed workflows. An old `feedback_unavailable` attempt is not treated as completed
under this revised protocol; no historical skipped repair is silently rerun.
A failed, interrupted or uncertain agent invocation stops scheduling. There are
no automatic retries, extra repairs, shortened inference budgets or model swaps.
`.running` is a concurrency guard: normal completion, caught/uncaught Python
exceptions, SystemExit and KeyboardInterrupt that unwind `finally` remove it.
An abrupt termination that bypasses `finally` (SIGKILL, `os._exit`, power loss)
can leave it behind. Confirm no controller remains active before removing it.
Failed/started/interrupted workflow states still require adjudication even when
the guard was cleaned up; removing `.running` does not authorize retrying a phase.
Do not delete attempt folders to obtain a better result. Record administrative
decisions in the private study log.

Every workflow receives the same one-repair, same-session opportunity without an agent execution
time limit, including the report-unavailable self-review fallback.
Missing datasets do not cancel feedback-group repair. `report_usable` checks fresh
parseable validation, pinned versions, no installation problems and agreement
between reported domains and a nonempty subset of actual produced domains.
Produced but unvalidated domains remain explicit coverage gaps. It does not require all
13 planned domains. A usable subset report has `status=valid_partial` and is
provided with a reminder that unreported required datasets still need completion.

If no usable report exists, the feedback group receives only the standard message
that the validation report is unavailable and continues self review. No invalid
report, installation details or independent correctness results are supplied.
`state.json` records `p21_report` versus `self_review_fallback`; both finish as
completed workflows when both agent phases complete. Self-review controls never
receive validator information. Infrastructure/ambiguous agent failures retain the
same stop-and-adjudicate policy in both conditions; no extra attempt is added.

This updates the intervention to a policy of offering usable feedback when
available. The primary analysis retains all 18 allocations, including fallback
workflows, rather than selecting only successful report recipients. Qualification
smokes still require complete assessable endpoints; smoke qualification is separate
from the repair opportunity rule within every smoke/main workflow. Code and prompt
changes invalidate previous freeze locks and smoke receipts.

## Agent completion and provider smoke evidence

A successful process exit or a final text message alone does not establish a
completed agent turn. The controller no longer requires the last stdout
`step_finish` string to be `stop`/`end_turn`. Instead it exports the actual session
and requires all of the following:

- Exit code zero, no timeout and no explicit provider error event.
- One matching session ID, preserved message history, and a newly added user turn
  followed by a completed assistant message bound to that user.
- A positive assistant completion timestamp and a known normal exported finish
  reason from message metadata and/or its final stored step-finish part.
- No exported message error or pending/unrecognized tool state in the new turn.
  Tool execution errors that were handled by the agent remain separate telemetry.

For repair, a pre-invocation export establishes the message-ID baseline. A stale
initial completion cannot satisfy the repair check. JSONL step events are linked
to the final exported assistant/part when possible. Earlier tool-call steps do
not override a completed later turn. If the final stdout event is missing but
the exported current turn proves completion, the phase can finish normally:
this performs no additional agent invocation or inference retry. Conflicting
current-part evidence, unknown terminal reasons, truncation, filter/error/tool-only
finishes or insufficient export metadata still stop for adjudication.

[The versioned policy](../main_experiment/completion-policy.json) normalizes case,
whitespace and underscores, with provider-specific normal reason allowlists.
It does not automatically learn arbitrary successful-looking strings. Schema or
reason changes require explicit policy review, fresh qualification and a new freeze.
A historical [OpenCode issue](https://github.com/anomalyco/opencode/issues/26855)
reported missing final JSONL events in an earlier release; it is not evidence that
the currently pinned image has that bug. Actual pinned-provider compatibility must
be established by the excluded smokes.

Each completed phase saves `completion.json`, raw `agent.jsonl`, `history.json`,
and completion details in `agent.json`; repair also saves `history-before.json`.
Evidence includes raw event/export reasons, normalized reason, current user and
assistant IDs, completion timestamp, missing-stdout flag and policy hash. Exported
usage is retained separately from stream usage; do not add the two sources together.
The event-only `event_terminal_hint` is diagnostic, never the workflow acceptance
criterion. Completion says that an agent turn ended normally, not that its ADaM
outputs are complete or correct; external scoring remains independent.

Every provider's smoke receipt must include normal completion evidence for both
initial and repair phases. `freeze` rejects receipts missing these fields, with
another provider's identity or with a stale policy hash. Synthetic tests cover the
parser/gates only; they do not substitute for real API qualification. Existing
receipts and locks must be regenerated after this change. No paid provider smoke
or main run is launched by these tests.

## Evidence and metrics

Each workflow directory contains controller `state.json`, a stopped container
identity, the live workspace, and `initial/` and `final/` checkpoints. Checkpoints
include the rendered prompt, raw JSONL events, exported session history, agent
execution metadata, workspace hashes, a sealed copy of outputs, evaluation JSON,
P21 report/log and an independent clean rebuild. The container is paused during
checkpointing and external evaluation. Checkpoint manifests detect later changes;
they are not a cryptographic signature or an OS write-protection mechanism.
Stopped containers and state volumes are retained for audit; remove them manually
only after retention requirements are met. They may contain sensitive data.

* **Conformance:** completed P21 dataset-rule pairs, severity details and record
  counts. Fresh reports with findings can be usable even with partial dataset
  coverage. Missing/invalid reports are unavailable, never zero findings.
  `dataset_set_complete`, `deliverables_complete`, missing/extra files and validated
  domains are separate endpoints. Invalid report counts are retained as diagnostics
  under `observed_*`, while scoring fields are null. P21 client 1.0.9, FDA engine 2508.1, ADaMIG 1.3,
  and CT 2026-03-27 are the runtime qualification targets. Model 2.1 is a
  specification target, not independently reported by P21. CLI and rules are
  hashed; confirm all reported versions during smoke.
* **Correctness:** selected source checks are separate from conformance. NPI uses
  randomized DM arms and a unique distinct complete SV VISITNUM=3 date, with no DM
  fallback. Baseline includes WDAY <=1; ties use distance, date, QSSEQ. TTE coverage
  uses POP01 source exposure evidence, including placebo dose >=0. Exact event
  predecessors and follow-up bounds are checked. Missing/extra/duplicate coverage
  components remain explicit. These checks do not certify every ADaM derivation.
* **Qualifications:** dermatologic and treatment-emergent flags remain conditional
  on generated ADAE. TTE duration +1 and RFENDTC censoring are experiment conventions.
  English MedDRA 8.0 is required, with hashed PT/SOC/LLT/HLT/HLGT files; masked HLT/
  HLGT/source provenance is not independently confirmed. No missing-dictionary
  allowance is passed to the report parser.
* **Reproduction:** rebuild runs offline with only programs and read-only source
  inputs. Semantic equality checks exact ordered values, labels, types, widths
  and canonical Define XML, ignoring only root ODM CreationDateTime. It is
  conservative, not a general clinical equivalence engine. Byte SHA256 equality
  is reported separately. Neither endpoint uses numeric rounding to hide changes.
* **Execution:** raw step-level input/output/reasoning/cache token fields, costs,
  finish reasons and tool events are retained. Re-emitted step IDs are deduplicated;
  unknown telemetry is null. `agent.json` seconds measure active phase wall time;
  workflow timestamps include controller time. Provider billing may differ.

`results.json` retains all 18 scheduled workflows and both checkpoints, including
unavailable endpoints. `summary.md` shows completion status. Within-workflow
initial-to-final reductions are reported only when both checkpoints have complete
deliverables and full usable validation coverage. A decrease caused by missing
datasets cannot become a finding reduction. Partial-report counts remain descriptive.
`condition_summary` retains nine planned workflows per condition and reports
completion, final complete deliverables, report availability and fallback counts;
not-yet-observed deliverables stay explicitly unavailable. Condition
comparisons must treat initial generations as independent; do not reuse the
pilot's paired-branch analysis or combine correctness and conformance into a
single score. Group-level statistical analysis is left to the prespecified
analysis plan; the controller exports the underlying endpoints.

## Isolation limits and collaborator acceptance

Agent containers mount only their live workspace, read-only prepared inputs and
their own persistent state. Controller code, hidden scores, references, P21 cache
and the repository are absent. Rebuild containers have no network. Agent containers
use a provider-only CONNECT gateway plus IPv4/IPv6 OUTPUT rules in the agent's
own network namespace. Shell commands cannot bypass these rules by clearing proxy
variables, using a numeric IP, alternate DNS or UDP/QUIC. Only gateway TCP 8080
and TCP localhost for the local OpenCode server are allowed. Browsing tools,
default plugins, model-catalog refreshes, auto updates and LSP downloads are
also disabled. Package installation during a run is unavailable; install all
required dependencies in the reviewed image before qualification.

The gateway permits HTTPS 443 only for the assigned provider: `api.openai.com`,
`api.anthropic.com` or `generativelanguage.googleapis.com`. It checks exact host
names, matching TLS SNI and public upstream DNS addresses. There are no wildcard
domains, OAuth/login hosts, search engines, GitHub or package registries on the
allowlist. Redirects to other hosts fail. The gateway has no study mounts or keys.
It retains connection decisions without recording TLS payloads, headers or keys.

A short-lived NET_ADMIN helper installs rules **only in the agent container's
network namespace**; the agent has no capabilities and cannot change those rules.
No host networking, Docker socket or host firewall modification is used. Failure
to install IPv4/IPv6 rules or pass bypass probes stops the workflow before any
model invocation. The same policy is mandatory for both conditions and all
repetitions. Gateway, helper code and policy are covered by the freeze fingerprint;
rebuild the image and repeat qualification after this change. Old smoke receipts
and locks cannot be reused.

Each workflow records `egress-policy.json`, `egress-rules.json`,
`egress-probes.json` and `egress-gateway.jsonl` outside the agent workspace.
A separate no-key Docker integration check tests denied direct HTTP/HTTPS and DNS,
denied non-provider CONNECT and mismatched SNI, plus successful provider TLS
handshakes. It sends no HTTP API request, credentials, prompts or study inputs:

```sh
python -m main_experiment.network_check --image adam-experiment:main \
  --out /private/study/network-check
```

GitHub CI runs this check with a minimal Python/iptables image and retains its
synthetic evidence. Local provider smoke tests must still validate the actual
pinned OpenCode image, proxy compatibility and API access. There is no fallback
to unrestricted networking if the model runtime needs an unapproved endpoint.

This is an outbound host restriction, not TLS interception: allowed API traffic
stays encrypted, so the gateway does not inspect model prompts, API paths or
provider-native search/grounding arguments. The prescribed OpenCode run has no
browsing tools, and the prompt prohibits requesting provider-native search.
Do not claim this eliminates model training-data memorization, controls the
provider's internal infrastructure or protects against a compromised Docker host.

Before approving a main launch, collaborators should comment on:

- Whether the independent 18-workflow design, budgets and statistical comparison
  match the final proposal.
- The exact model IDs, prompts, canonical input export and TRTA correction.
- Correctness scope, coverage denominators, failure policy and MedDRA qualifications.
- Local smoke evidence for all providers, CLI session exports, P21 versions,
  dictionary use, feedback isolation and clean offline reconstruction.
- Data-governance authorization for provider uploads and evidence retention.

Use PR review comments on the files in the code map. CI uses synthetic data only;
GitHub Actions never receives provider keys or clinical inputs and never runs the
main experiment.

Runtime references: [OpenCode CLI](https://opencode.ai/docs/cli/) documents explicit
session continuation and export; [P21 Community CLI](https://help.pinnacle21.certara.net/en/articles/9737181-validate-with-p21-community-cli)
documents ADaM validation and the MedDRA version argument. Those upstream pages
are references; the local smoke qualifies the pinned installation.

Network references: [OpenCode proxy support](https://opencode.ai/docs/network/) and
[Docker container networking/capabilities](https://docs.docker.com/engine/containers/run/).

## Main-study runtime ownership

The main runner uses its own `support.py` (evidence utilities and P21 report
parsing), `rebuild.py` (offline Docker reconstruction), Dockerfile and pinned
evaluator requirements under `main_experiment/`. It does not import the pilot
runner. The main seal covers these files, not `experiment/experiment.py` or the
pilot build/dependency files. Pilot-only edits therefore do not invalidate a
main-study seal. Main runtime edits still require fresh qualification and freeze.
After this extraction, rebuild using the main Dockerfile and regenerate smoke
receipts and the freeze lock before launch. Historical pilot files remain archived
for their own workflow and are not synchronized with the main runtime.

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

### Large session export transport

Local OpenCode 1.19.0 qualification exposed truncated JSON when a large session
was exported through a stdout pipe. The controller now redirects each initial,
final and pre-repair export to a unique regular file in the private state volume,
copies it to the host and retains raw bytes alongside parsed history. Invalid
JSON still fails completion; no model retry or relaxed completion rule is used.
The diagnostic failed smoke remains preserved and does not qualify. This code
change requires new smoke receipts and freeze.

P21 report qualification uses reported version evidence and the pinned
`ADaM-IG 1.3 (FDA).xml` configuration. The seal verifies that configuration's
standard metadata and hash. Base ADaM Model 2.1 is a specification target; the
local P21 summary does not independently report it. Requiring the literal `2.1`
in that summary was a false qualification failure and has been removed.
All other report usability and complete-delivery requirements remain in force.
