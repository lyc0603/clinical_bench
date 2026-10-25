# GPT-OSS-20B exploratory results

The unified report contains **16 metrics across 18 endpoints**. It preserves all fifteen previously published endpoints unchanged and adds one independent DeepInfra GPT-OSS-20B workflow for each of initial-only, self-review and P21 feedback.

- [Excel workbook](metrics.xlsx): complete comparison plus typed endpoint data.
- [All sixteen metrics in one table](metrics.md).
- [CSV](metrics.csv) and [JSON](metrics.json).
- [Endpoint evidence audit](gpt-oss-audit.json) and [artifact checksums](SHA256SUMS).

## Observed outcomes

| Condition | Session workflow completed | Complete thirteen-dataset package | Usable terminal P21 report | Semantic rebuild | Selected-run API cost estimate (USD) | End-to-end minutes |
|---|---|---|---|---|---:|---:|
| Initial-only | Yes | No | No | Fail | 0.0010 | 0.67 |
| Self-review | Yes | No | No | Fail | 0.0015 | 1.25 |
| P21 feedback | Yes | No | No | Fail | 0.0013 | 1.09 |

Normal model/session completion does not mean successful ADaM delivery. None of these three workflows produced a complete package. P21 evaluations did not produce qualified usable reports; finding counts are **unavailable**, not zero. No conformance improvement can be calculated. The P21-feedback initial report was unusable, so the existing protocol's self-review fallback was used; this endpoint does not demonstrate the effect of receiving P21 findings.

Initial-only produced reconstruction scaffolding rather than the required dataset package. Self-review's initial turn included a glob request to nonexistent relative `inputs` (the supplied mount is `/inputs`) and an edit whose old text did not match; its repair turn made no tool calls. These observations describe the retained selected runs, not all possible outcomes of the model.

## Design and environment amendment

The model is `deepinfra/openai/gpt-oss-20b`, with temperature 1.0, medium reasoning, 131,072 context metadata and 16,384 maximum response tokens. Three fresh independent generation sessions ran serially in seeded order initial-only, P21 feedback, self-review. There was one repair for each repair condition, no repair for initial-only and no agent time cap. Original frozen inputs, prompts, Docker image, host evaluator, P21 configuration and provider-only firewall machinery were reused. General web search and subagents remained denied. The title helper was disabled.

An earlier batch exposed a missing ripgrep dependency in the original image. It was stopped, retained privately and excluded as an unqualified environment attempt. The controller then provisioned a hash-pinned Linux ripgrep executable before model access and added it to PATH. Fresh nonclinical tests exercised bash, glob, grep, read, same-session continuation and normal completion for both hosted models. A new freeze preceded all three selected clinical generations. The original image and host evaluator were not changed. See [complete file-tool qualification](../../../research_analysis/deepinfra-file-tools-readiness-2026-10-25.json), [adapter details](../../../open_model_extensions/README.md) and [three-condition workflow](../../../open_model_experiment/README.md). The earlier [bash-only qualification](../../../research_analysis/deepinfra-readiness-2026-10-25.json) is historical evidence and was insufficient to qualify file-search dependencies.

The failed relative-path glob in the selected self-review run is separate from the earlier missing-binary issue: the binary was provisioned, checked and exercised successfully in qualification; the selected invocation requested a directory that does not exist. No successful replacement was substituted for this model tool error.

## Interpretation and reporting

There is one workflow per condition. This supports feasibility and descriptive observations, not significance tests, causal feedback comparisons or general conclusions about open-weight models. The three new initial generations are independent; some historical initial-only/self-review endpoints share generation. Initial-only here is not the initial checkpoint of either new repair workflow. The hosted endpoint does not independently pin weights, numerical precision or server implementation, and is not private local deployment.

Costs and times cover the selected workflows only, excluding nonclinical qualification and the earlier unqualified environment batch. Costs are native telemetry estimates, not invoices. When native tool telemetry is null for a normal no-tool turn, zero is reported only after current-turn exported messages independently establish that no tool parts exist; each normalization is recorded in JSON and the raw log remains unchanged. Other missing quantities stay unavailable. No automatic generation retries occurred.

The offline [report merger](../../../research_analysis/append_gpt_oss_20b.py) verified the freeze, adapter/runner/tool hashes, qualifications, independent session identities, within-workflow continuity, prompts, sampling and immutable checkpoint manifests. The [workbook builder](../../../research_analysis/artifacts/gemini_temperature.mjs) exports the same sixteen metrics. Only aggregate results and sanitized evidence are public; credentials, clinical records, generated clinical artifacts, dictionaries and raw sessions remain private. The formal main study was not started.
