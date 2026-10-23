# Excluded DeepSeek extension

Add one official `deepseek/deepseek-flash` paired initial-only/self-review session and one independent P21-feedback session. Run them serially, once each, with no agent time cap, automatic retries or replacement of failed attempts. The formal three-model protocol and all previous evidence stay unchanged. The API alias was advertised as V4.1-Flash-1017 on 22 October 2026; it is mutable and does not establish fixed backend weights.

Use the existing pinned image, prepared inputs, frozen prompts, P21 single-processor clean-state configuration, native evaluator, rebuild limits and content guards. A new extension lock binds the previously accepted 24-checkpoint-validation qualification, unchanged main seal, cache source, extension code and a new nonclinical DeepSeek readiness receipt. It does not relabel the old qualification as a DeepSeek model qualification. Readiness demonstrates actual DeepSeek identity, tool use, exported normal stop and same-session continuation without clinical inputs.

The adapter adds only `api.deepseek.com` to its own gateway allowlist. The original namespace firewall and denied web tools remain active. Explicit provider metadata uses the pinned runtime's OpenAI-compatible adapter with the DeepSeek reasoning-content field declared; readiness must demonstrate tool round-trip interoperability. Sampling and thinking settings are left at provider/adapter defaults, with reasoning support declared. Completion reuses all structural checks from the sealed main assessor's stop-only profile and independently verifies actual DeepSeek provider/model IDs. Other finishes, pending tools and provider errors fail. No history is relabeled.

The configured token prices are the official peak USD rates on 22 October: uncached input $0.30/M, cache read $0.006/M and output $1.20/M. Telemetry cost is therefore a peak-rate estimate, not a billed amount; official off-peak rates are lower. Report missing usage as unavailable. Keep readiness costs separate from experimental endpoint costs. Initial-only and self-review share generation; do not double-count it. The new P21-feedback initial package is independent, and comparisons with previously observed models remain nonconcurrent and exploratory.

```sh
python -m pilot_extensions.deepseek smoke --base-config /private/config.json --p21-qualification /private/qualification/qualification.json --env-file /private/credentials.env --out /private/deepseek-readiness --execute
python -m pilot_extensions.deepseek freeze --base-config /private/config.json --p21-qualification /private/qualification/qualification.json --smoke /private/deepseek-readiness --lock /private/deepseek.lock.json
python -m pilot_extensions.deepseek run --base-config /private/config.json --p21-qualification /private/qualification/qualification.json --lock /private/deepseek.lock.json --env-file /private/credentials.env --out /private/deepseek-pilot --execute
```

Credentials go only in the local environment file. Private execution evidence stays outside Git. Publish only aggregate measurements, hashes and technical adjudication. Preserve original controller failures separately from accepted later rescoring. These results do not authorize formal main-study launch.
