# Clinical benchmark: current main experiment

The current design is **18 independent workflows** (3 models × 2 conditions ×
3 repetitions). Each workflow generates once and repairs once in the same
OpenCode session. Agent phases have no execution time cap. Web tools and direct
internet/DNS are blocked; only the assigned provider gateway is reachable.

Start with [the current protocol](docs/main-study-protocol.md) and
[the workflow and collaborator guide](docs/main-experiment-workflow.md).
[The scoring contract](main_experiment/scoring-rules.json) defines the separate
conformance, completeness, reconstruction and selected correctness endpoints.
Historical paired designs do not apply to this experiment.

## Setup and no-cost schedule preview

Keep clinical inputs, credentials, local config and all run evidence outside Git.
From the repository root:

```sh
python -m pip install -r main_experiment/requirements.txt
cp main_experiment/config.example.json main_experiment/config.local.json
cp .env.example .env.local
python -m main_experiment plan --config main_experiment/config.example.json
```

Edit private paths and provider credentials locally. Follow the workflow guide
for the reviewed image build, canonical input preparation, no-key network check,
local preflight and **three excluded provider smoke workflows**. Model IDs and
provider access require qualification; CI alone does not establish launch readiness.
Smokes must also verify both phases' exported completion evidence and actual
provider finish reasons before a freeze can be created.
Smokes and main runs incur API charges; planning and freezing invoke no model.

## Freeze the current main study

After all three qualification smokes match the current inputs/code/runtime:

```sh
python -m main_experiment freeze \
  --config main_experiment/config.local.json \
  --smokes /absolute/private/study/smokes \
  --out /absolute/private/study/main \
  --lock /absolute/private/study/main.freeze.json
python -m main_experiment run \
  --config main_experiment/config.local.json \
  --out /absolute/private/study/main \
  --lock /absolute/private/study/main.freeze.json --execute
python -m main_experiment report \
  --config main_experiment/config.local.json \
  --out /absolute/private/study/main
```

Use only the `main_experiment` freeze and runner for the current study. Any
change to frozen inputs, code, protocol, prompts, config or runtime requires new
qualification and a new lock. Preserve all 18 allocations, including missing
outputs and report-unavailable self-review fallbacks. A partial P21 report can
support repair; missing datasets cannot count as a finding reduction.

See the workflow guide for evidence layout, recovery and collaborator review.
An ordinary Python failure removes the `.running` concurrency guard; an abrupt
termination can leave it behind. In either case, failed/interrupted workflow
state still prevents automatic retry. Removing a guard does not reset an attempt.

## Tests

```sh
python -m unittest discover -s experiment -p 'test_*.py' -v
python -m unittest discover -s main_experiment -p 'test_*.py' -v
```

Both suites use synthetic fixtures. The separate Docker network CI job tests
blocked routes and provider TLS without keys, study inputs or model requests.
Actual provider and P21 smoke qualification is still required before launch.

## Historical materials

The `experiment/` runner, [pilot commands](docs/archive/legacy-pilot-readme.md),
[pilot protocol](docs/protocol.md) and
[superseded paired main-study proposal](docs/archive/legacy-paired-protocol.md)
are retained for provenance. They use a different design and cannot freeze the
current main experiment. The historical freezer requires an explicit
`--legacy-paired` flag to avoid accidental use.

No clinical data, credentials or P21 runtime are distributed here. The MIT
license covers repository code, not separately licensed study/vendor materials.

## Excluded exploratory pre-experiment

See the latest [unified exploratory results: 19 metrics across 24 endpoints](pre_experiment/results/supplementary-metrics-2026-10-28/README.md), with Excel, CSV, JSON, failure-stage distributions and an evidence audit. This retrospective analysis adds Dataset Delivery Rate, Variable Coverage and Failure-stage distribution to the unchanged [original sixteen-metric results](pre_experiment/results/open-models-2026-10-25/README.md). Original observations, failures and controller statuses are preserved; no model or validator was rerun. Missing delivery, observed execution failures and downstream blocked stages are distinguished. The table includes historical closed/API-model results, Gemini temperature probes and three independent conditions each for DeepInfra GPT-OSS-20B, GPT-OSS-120B and Llama 4 Scout. These exploratory, nonconcurrent endpoints are not all independent trials, and the new metrics were defined after outcomes were known. The formal main study and its frozen protocol remain unchanged.

The [earlier six-workflow comparison](pre_experiment/results/2026-10-21/README.md) remains archived with its original runtime-integrity rejections and follow-up.

The [DeepInfra open-weight extension](open_model_extensions/README.md) passed [complete nonclinical file-tool qualification](research_analysis/deepinfra-file-tools-readiness-2026-10-25.json) for gpt-oss-20b and gpt-oss-120b after provisioning a hash-pinned ripgrep executable. It verifies explicit temperature 1.0 and medium reasoning, offline request capture, bash/glob/grep/read, same-session continuation, normal completion and usage telemetry. The earlier bash-only qualification did not cover missing file-search dependencies; a pre-amendment batch is retained privately and excluded as unqualified environment evidence. These probes are not clinical outcome metrics. The original sealed main runner and Docker image remain unchanged. Only gpt-oss-20b has been run on clinical experiment inputs in this extension.

### P21 amendment: new qualification and freeze required

The [evaluator amendment](docs/p21-evaluator-amendment.md) now distinguishes client errors from immutable runtime changes and retains diagnostics. Existing pilot scores remain unchanged. The old main-study freeze does not authorize this changed evaluator: formal execution must wait for review, qualification and a new versioned freeze.

The [paired pilot workflow](pre_experiment/PAIRED-PILOT.md) and [validator continuation](pre_experiment/RECOVERY.md) document the qualified, separately frozen execution. The completed results describe the technical amendment and limits. Formal main-study launch requires its own current freeze and independent design review.
