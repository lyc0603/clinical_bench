# Excluded self review pre experiment

Before any main-study execution, add one fresh self-review workflow per provider
to the three already observed P21-feedback qualification smokes. Both conditions
use the same OpenCode framework; “ReAct” is not a separate intervention label.
The six completed examples, or their retained failures, are an exploratory
nonconcurrent pre-experiment. They do not estimate a powered treatment effect
and must never be counted among the 18 main-study workflows.

The self-review starts are independent. Do not fork a session that has seen P21
feedback, reuse an initial package, select a successful retry, or replace a failed
attempt. Each provider gets one initial generation and one same-session review
using the existing frozen prompts, inputs, runtime and evaluator. No agent time
limit is introduced. Scheduling stops after a failure for explicit adjudication.
Previously observed qualification results and earlier failed attempts remain
disclosed; the table of selected completed smokes is not all project expenditure.

The launcher verifies the existing main freeze before and after each workflow
and saves its own plan, code hash and source-lock binding outside the repository.
It does not modify the main runner, its sealed files, main schedule or lock.
The separate launcher is not itself part of that earlier main-study seal.

```sh
python -m pre_experiment.run_self_review \
  --config /private/study/config.local.json \
  --env-file /private/credentials.env \
  --lock /private/study/freeze-main.json \
  --out /private/study/excluded-self-review --execute
```

Use the same 16-row reporting layout for all six examples, preserving every
original reporting item via the two documented row combinations. Show unavailable
values, guard flags, conditional correctness, timing, normalized token buckets
and estimated costs explicitly. Never publish credentials, patient-level source
data or dictionary files. Results do not authorize main-study launch before
independent review of the scientific design.
