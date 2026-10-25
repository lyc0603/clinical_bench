# Temperature extension: capability audit, no experimental outcomes

On 24 October 2026 (Pacific time), the requested 0.2 / 0.6 / 1.0 settings were checked using nine tiny nonclinical direct API requests. This is a technical audit, not a temperature performance experiment. No clinical inputs were sent and no ADaM or P21 workflow started. The [existing 16-metric table](../four-model-2026-10-22/README.md) is unchanged.

| Model and mode | Temperature 0.2 | Temperature 0.6 | Temperature 1.0 | Interpretation |
| --- | --- | --- | --- | --- |
| GPT-6.1 Sol, reasoning low | HTTP 401 | HTTP 401 | HTTP 401 | Invalid credential; runtime parameter support not reached. Official documentation excludes temperature with reasoning and this model does not support reasoning none. |
| Claude Sonnet 5.5, default thinking | HTTP 400 | HTTP 400 | HTTP 200 | Non-default temperatures rejected as deprecated. Only 1.0 accepted; no three-level experiment is possible on this endpoint. |
| DeepSeek Flash, thinking enabled | HTTP 200 | HTTP 200 | HTTP 200 | Acceptance is not effectiveness: official documentation says thinking-mode temperature is ignored. |

All 16 experimental performance metrics are N/A for these probes. They must not be entered as model failures, zero findings, or new ADaM endpoints. No observed response difference can establish that temperature was applied.

## Next decision

Before any clinical run, either retain the original models and study a separately defined supported factor (such as reasoning effort), or define a temperature extension using explicitly selected temperature-capable models/modes. Changing DeepSeek to non-thinking would create a new mode and must be labeled separately from historical thinking-mode results. OpenAI credentials also require local correction. Do not silently change a model, reasoning mode, or parameter, or relabel a default-temperature repetition as a temperature treatment.

The requested phrase “once per temperature” also needs a frozen endpoint scope before execution: initial-only generation versus all three existing workflow conditions. Each temperature is exploratory with one repetition; no significance or universal optimal-temperature claim is justified.

## Evidence and reproduction

[Sanitized probe results](capability.json) include requested parameters, HTTP statuses and token usage where returned. Error messages and credentials are excluded. The [probe script](../../../research_analysis/probe_temperature.py) has no clinical-input argument and never starts Docker, P21, or the main experiment. Each rerun requires a fresh private directory; original attempts are preserved.

```sh
python -m research_analysis.probe_temperature --env-file /private/credentials.env --out /private/fresh-capability-audit --execute
```

Sources checked on 24 October 2026:

- [OpenAI sampling and reasoning compatibility](https://developers.openai.com/api/docs/guides/latest-model)
- [Claude Sonnet 5.5 parameter restrictions](https://platform.claude.com/docs/en/models/sonnet-5-5/overview)
- [DeepSeek thinking-mode parameters](https://api-docs.deepseek.com/guides/thinking_mode/)
