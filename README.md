# clinical_bench

A pilot benchmark of **LLM-generated ADaM conformance and Pinnacle 21-guided
repair**. One common OpenCode agent is used across provider models. The experiment
does not compare the native Codex, Claude Code, and Gemini CLI applications.

Each model generates an initial package from SDTM, SAP and supplied metadata.
Two copies of that package enter equal-time repair branches:

| Branch | Agent feedback | External evaluation |
|---|---|---|
| Self-review | Source materials, code and execution logs | P21, hidden from agent |
| P21-guided ReAct | Above plus preceding P21 findings | P21 |

Both branches modify production programs and regenerate artifacts. P21 evaluates
the initial and subsequent packages; only the feedback branch receives reports.

## Quick start

1. Copy `.env.example` to `.env.local`, set local source/runtime paths, and enter
   provider API keys there. The runner loads this file automatically. It is ignored
   by Git. Keep its permissions private: `chmod 600 .env.local`.
2. Copy `experiment/config.example.json` to `experiment/config.local.json` and set
   exact API model IDs available in your account. For a pilot retain one model,
   set `repetitions` to 1 and `repair_iterations` to 1.
3. Start Docker (or use the optional isolated Colima setup below).
4. Build the common image with an explicitly selected OpenCode version:

```sh
docker build -f experiment/Dockerfile \
  --build-arg OPENCODE_VERSION=1.19.0 \
  -t adam-experiment:1 .
python3 experiment/experiment.py doctor
python3 experiment/experiment.py plan --out /absolute/private/path/pilot-01
python3 experiment/experiment.py preflight --out /absolute/private/path/pilot-01
python3 experiment/experiment.py run --out /absolute/private/path/pilot-01
```

`doctor`, `plan` and `preflight` make no paid model calls and do not run P21.
Preflight checks model names against the pinned agent's provider catalog without
submitting study data; account access is subsequently established by the pilot.
The run output directory must be outside the code repository. Reuse the same
configuration and output path to resume completed stages. Interrupted stages are
retained for adjudication; failed attempts are not silently retried.

Optional Mac Docker engine:

```sh
colima start clinical-bench --cpu 4 --memory 10 --disk 40 \
  --activate=false --ssh-config=false
DOCKER_CONTEXT=colima-clinical-bench docker info
```

Set `DOCKER_CONTEXT=colima-clinical-bench` in `.env.local` for the runner. Shell
Docker commands also need that environment variable when the default context is
different. Use `colima stop clinical-bench` to stop the experiment VM.

## Outputs

- `results.csv`: all iterations, status, findings, counts, timing and reported usage.
- `paired_results.json`: initial/final paired comparisons, new findings and counts.
- `summary.md`: completed/eligible pairs and mean feedback advantage per model.
- Frozen inputs, runtime hashes, prompts, trajectories, programs and raw reports.

## Scope and readiness

This is a conformance pilot, **not a measure of SAP derivation correctness or
submission readiness**. Read [the protocol](docs/protocol.md) before running.
Offline tests use synthetic workbooks and mocked agents; they require neither
clinical data, provider credentials, nor P21. They do not establish end-to-end
readiness. A real one-model pilot must pass before launching the full experiment.

Time limits are enforced; token usage is recorded but not hard-capped. Native CLI
defaults are not necessarily API model names: verify exact IDs before freezing
the main experiment. Agent sessions are fresh per iteration; context is carried
through workspace artifacts and notes. Shell internet access is not firewall
restricted, so this implementation is not a certified closed-book benchmark.

No study inputs, credentials, raw transcripts or P21 runtime are distributed here.
The repository's MIT license applies to its code, not separately licensed study
materials or vendor software.

## Tests

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s experiment -p 'test_*.py' -v
```

CLI reference: [OpenCode](https://opencode.ai/docs/cli/).
