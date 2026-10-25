# Open-model exploratory pilot: 16 metrics across 24 endpoints

The table preserves the previous eighteen endpoints exactly and adds six independent workflows: GPT-OSS-120B and Llama 4 Scout, each with initial-only, self-review and P21-feedback once. This is exploratory work, excluded from the formal main study.

[Excel](metrics.xlsx) · [All 16 metrics](metrics.md) · [CSV](metrics.csv) · [Machine-readable results](metrics.json) · [GPT-OSS-120B audit](gpt-oss-audit.json) · [Scout audit](llama-scout-audit.json) · [Endpoint identity and qualification diagnostics](../../../research_analysis/deepinfra-new-models-readiness-2026-10-25.json)

## New results

| Model | Condition | Process/session | Complete ADaM package | Terminal P21 findings | Agent seconds, both phases | Estimated API cost, both phases |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gpt_oss_120b | initial_only | Completed | No | Unavailable | 6.79 | $0.00049869 |
| gpt_oss_120b | self_review | Completed | No | Unavailable | 15.68 | $0.00085308 |
| gpt_oss_120b | p21_feedback | Completed | No | Unavailable | 23.69 | $0.00114692 |
| llama_4_scout | initial_only | Completed | No | Unavailable | 7.38 | $0.00133820 |
| llama_4_scout | self_review | Completed | No | Unavailable | 19.78 | $0.00140470 |
| llama_4_scout | p21_feedback | Completed | No | Unavailable | 20.27 | $0.00144680 |

All six sessions ended normally, but none delivered the complete thirteen-dataset package or required deliverables. No endpoint has a usable terminal P21 report. P21 logged missing Define-XML/input errors; these findings are unavailable, not zero conformance findings. The two feedback workflows both received the declared self-review fallback because their initial reports were unusable. They did not receive usable P21 feedback, so these runs cannot estimate the benefit of actual validator feedback. No semantic or byte-level rebuild success is established.

Each workflow has a fresh initial session; repair continues that same workflow's session. The three conditions are not paired by a common generation. Historical endpoints include different dependence structures and nonconcurrent environments. One attempt per cell supports feasibility observations, not significance tests or causal model-size/feedback rankings. Low costs reflect early termination without task completion. Estimates exclude qualification/diagnostic probes and are not invoices.

## Exact configuration and retained diagnostics

- Provider: DeepInfra. GPT-OSS-120B endpoint `openai/gpt-oss-120b`, temperature 1, requested medium reasoning, 131,072 context metadata and 16,384 maximum response tokens.
- Llama endpoint `meta-llama/Llama-4-Scout-17B-16E-Instruct`, temperature 1, no reasoning-effort setting, 327,680 hosted context metadata and 16,384 maximum response tokens. Scout is a Llama 4 open-weight model under Meta's Llama 4 license; hosted inference does not constitute private local deployment.
- Maverick returned 404. Its FP8 alias returned a Gemma model identity in a nonclinical probe and was excluded. Scout and GPT-OSS-120B direct probes returned their exact requested identities. Exported session identities were also audited, but these checks do not independently pin server-side weights or prove the identity of every underlying response.
- Scout's first nonclinical readiness attempt failed with empty glob/grep arguments and a text-only bash operation. A synthetic offline streaming fixture preserved final-frame tool arguments, providing no evidence of argument loss in that tested case. A second nonclinical diagnostic with explicit required tool arguments passed bash/glob/grep/read and same-session continuation. Both attempts are retained and disclosed. Clinical prompts were not changed and no clinical workflow was retried.
- Original Docker image, evaluator, frozen clinical inputs and prompts are reused. A hash-pinned ripgrep binary is provisioned before each model session; general web search, web fetching and subagents remain denied. Clinical phases have no time cap. The 300-second limit applies only to short nonclinical readiness turns.
- Both pilots verify their frozen runner/adapter/settings/evidence hashes before each workflow and after the batch. The earlier unqualified glob-dependency batch mentioned in the frozen GPT-OSS runner documentation belongs to the historical GPT-OSS-20B lineage; it is not a discarded GPT-OSS-120B clinical run.
- Native missing tool telemetry is interpreted as zero only when the exported normal current turn has no tool parts; every such reporting interpretation is recorded and raw files remain unchanged. Requested reasoning settings and token telemetry do not establish equivalent reasoning budgets across models.

## Verification and privacy

All sixteen metrics are present for every endpoint, including explicit unavailable/not-applicable entries. The prior eighteen records remain unchanged. Private histories, prompt/config receipts, workspace and checkpoint manifests, independent session IDs, repair continuity, evaluator receipts and initial-only receipts were checked. SHA256SUMS binds the public deliverables. Clinical files, raw conversations, P21 reports, dictionaries and API keys are not published.

The intermediate twenty-one-endpoint report is retained privately; its hash is recorded in Scout's provenance. It can be regenerated by `research_analysis.append_gpt_oss_120b` from the prior eighteen-endpoint report and the retained private receipts, then extended by `research_analysis.append_llama_scout`.
