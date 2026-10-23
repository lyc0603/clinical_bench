# Four-model exploratory pilot: 16 metrics, 12 endpoints

[Full comparison](metrics.md) · [Excel workbook](metrics.xlsx) · [CSV](metrics.csv) · [Typed measurements and provenance](metrics.json) · [200 auxiliary check records](auxiliary-checks.csv) · [DeepSeek evidence audit](extension-audit.json) · [Prior evidence audit](prior-evidence-audit.json) · [Table verification](table-verification.json)

DeepSeek was added in a separately frozen extension begun on 22 October 2026 and completed on 23 October (Pacific time). Its two fresh sessions supply three endpoints: a shared initial-only/self-review generation and an independent P21-feedback workflow. The [previous nine endpoints](../paired-2026-10-21/README.md) are preserved exactly, giving four models and three conditions in one 16-row table. Both review conditions use OpenCode; “ReAct” refers to P21 feedback here. These are excluded exploratory results; this task did not start the formal main study.

| Model | Initial-only pairs | Self-review initial → final pairs | P21-feedback initial → final pairs |
| --- | ---: | --- | --- |
| OpenAI GPT-6.1-Sol | 26 | 26 → 26 | 26 → 24 |
| Anthropic Sonnet 5.5 | 26 | 26 → 26 | 26 → 24 |
| Google Gemini 3.1 Pro Preview | 64 | 64 → 58 | 49 → 15 |
| DeepSeek Flash | 28 | 28 → 25 | 47 → 24 |

## DeepSeek interpretation

All four DeepSeek checkpoints delivered 13 readable datasets and accepted full-coverage P21 evaluations. All reproduced semantically in clean rebuilds. The P21-feedback final package did not reproduce byte for byte; this remains visible in metric 2 and is not reclassified. All four agent phases completed normally, with no recorded failed tool calls.

Self-review reduced dataset-rule pairs from 28 to 25 and finding instances from 47,926 to 4,118. It resolved three pairs and introduced none. The content guard detected no regression, so the guarded reduction is three. The selected NPI mean/baseline checks reported zero errors among 254 assessed records, but NPI coverage retained 20 extra expected-record comparison entries in both phases. This unresolved issue is disclosed separately rather than hidden by the zero numerical error counts. Selected TTE linkage errors were 0/152 in both phases.

P21 feedback reduced pairs from 47 to 24 and instances from 134,406 to 4,050. It resolved 23 pairs, introduced none and had no detected content regression; its guarded reduction is 23. Selected NPI mean/baseline errors were 0/234 and TTE linkage errors 0/152 in both phases, with no detected missing, extra or duplicate expected records. All 10 planned auxiliary checks were assessable in each DeepSeek checkpoint; the applicable denominator has not been adjudicated.

The workflows had different initial outputs: the feedback workflow already had no extra NPI records before repair. Its larger pair reduction and lower final count therefore cannot establish that feedback caused a better outcome than self-review. These are single examples, without a powered treatment-effect estimate or a justified model ranking. No detected content regression establishes only the result of the selected guard checks, not comprehensive derivation correctness.

## Cost and timing

| DeepSeek workflow | Generation estimate | Review estimate | Cumulative estimate | End-to-end time |
| --- | ---: | ---: | ---: | ---: |
| Initial-only snapshot | $0.4164 | Not applicable | $0.4164, shared below | 54.97 min |
| Same-session self-review | $0.4164 | $0.2047 | $0.6211 | 87.80 min |
| Independent P21 feedback | $0.3250 | $0.1099 | $0.4349 | 58.32 min |

The DeepSeek extension totals **$1.0560 estimated**, counting its shared generation once. Do not add initial-only to cumulative self-review cost. Across the three earlier paired sessions and the two DeepSeek sessions, the corresponding total is $12.3975; historical P21-feedback controls and readiness tests are excluded. Token totals accumulate across requests and include repeated/cache-read input; they are not a single prompt's length. Cache reads explain much of the low estimated cost.

DeepSeek estimates use the declared official peak USD rates as of 22 October: $0.30/M uncached input, $0.006/M cache reads and $1.20/M output. Actual off-peak billing may be lower; these are telemetry estimates rather than reconciled invoices. Provider accounting semantics and original workflow timing remain as recorded. See [official pricing](https://api-docs.deepseek.com/quick_start/pricing/).

## Frozen method, audit and retained failures

The [isolated extension](../../../pilot_extensions/README.md) used official `deepseek/deepseek-flash`, advertised as V4.1-Flash-1017 at configuration time. This mutable alias does not establish fixed backend weights. The pinned OpenCode 1.19.0 image, prepared clinical inputs, generation/review prompts, 4-CPU/8-GB agent limits, native evaluator, rebuild rules and single-processor clean-state P21 configuration were retained. General web tools remained disabled and the network gateway allowed only the official model host for this provider. Sampling/thinking behavior followed the declared adapter/provider defaults.

A nonclinical readiness attempt failed provider initialization before clinical generation. Its evidence was retained. The runtime-compatible OpenAI-compatible adapter, with DeepSeek's reasoning-content field declared, subsequently passed actual tool use, normal exported stop and same-session continuation. That passing receipt, extension code, unchanged main seal, input hashes and clean cache manifest were bound in a new extension lock. The existing P21 qualification covers 12 fixed checkpoints validated twice; it is an evaluator qualification, not a new DeepSeek performance trial. No completed clinical agent was rerun or replaced.

The [offline merger/auditor](../../../research_analysis/append_deepseek.py) checked the freeze, current evaluator/runtime/input/qualification identity, readiness hash, raw/exported histories, actual requested provider/model IDs, frozen prompts, workspace/checkpoint manifests, same-session continuation and initial-only receipt. The public audit reports hashes and aggregate statuses; clinical records, raw histories, P21 reports, credentials and licensed dictionaries remain private. This is local consistency verification rather than an external signed attestation.

The original OpenAI paired controller remains failed because of its original P21 technical error; its accepted reassessment remains separately labeled. Google's earlier self-review reproduction failure and increased finding instances also remain unchanged. The prior report explains that adjudication and its missing original OpenAI final checkpoint seal. Historical controls remain nonconcurrent and selected; the table is not a record of every earlier qualification attempt or all project expenditure.

With authorized private-evidence access, regenerate using `python -m research_analysis.append_deepseek --help`, supplying the preserved nine-endpoint JSON, DeepSeek run root, frozen base configuration and P21 qualification. Excel and CSV were checked against every JSON table cell, all 200 auxiliary entries were reconciled, and the original nine records matched exactly. The one-study scope, one example per model/condition, correlated paired endpoints, preview/alias drift and provider defaults limit inference. A formal study requires a separately current freeze and independent design review.
