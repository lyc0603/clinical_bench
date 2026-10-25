# Exploratory results with Gemini temperature sensitivity

The unified table contains **16 metrics across 15 endpoints**: the twelve previously published model/condition endpoints, preserved unchanged, plus three independent Gemini 3.1 Pro Preview initial-only temperature results.

- [Excel workbook](metrics.xlsx): complete comparison and typed endpoint data.
- [Full comparison table](metrics.md): all sixteen metrics in one table.
- [CSV](metrics.csv) and [JSON](metrics.json): reusable results.
- [Evidence audit](temperature-audit.json): frozen-setting and endpoint checks.
- [File checksums](SHA256SUMS): published artifact integrity.

## Temperature results

| Temperature | P21 dataset-rule pairs | Finding instances | Distinct rules | Semantic rebuild | API cost estimate (USD) | End-to-end minutes |
|---|---:|---:|---:|---|---:|---:|
| 0.2 | 80 | 10,483 | 13 | Pass | 0.5592 | 5.03 |
| 0.6 | 79 | 707,266 | 12 | Pass | 0.7752 | 13.12 |
| 1.0 | 89 | 837,426 | 11 | Fail | 0.7736 | 19.67 |

All three selected sessions ended normally, delivered thirteen readable datasets and required deliverables, and produced usable P21 reports with full dataset coverage. None reproduced exact output bytes. Session completion and P21 report availability do not imply successful semantic reproduction or clinical correctness.

The primary finding measure is dataset-rule pairs. Finding instances count repeated occurrences and should not be interpreted as independent errors. P21 conformance does not establish clinical derivation correctness. Auxiliary checks cover selected conditional derivations only.

## Design and provenance

There is one selected independent result per temperature, with no repair phase. This is an exploratory sensitivity comparison, excluded from the formal main study. It cannot establish an optimal temperature or statistically reliable differences. Historical model/condition results are nonconcurrent contextual controls; initial-only and self-review endpoints in the historical paired runs share generation.

The three temperatures use the same frozen inputs, generation prompt, evaluator, Docker image, provider-only egress policy and pinned OpenCode defaults. The title helper is disabled in all three new endpoints. The Gemini preview endpoint is mutable; request-capture verification establishes serialized parameters, not server-side sampling internals. See [execution settings](../../../temperature_extensions/README.md) and [nonclinical qualification evidence](../../../research_analysis/gemini-temperature-readiness.json).

Temperature 0.6 uses the user-authorized fresh rerun after an API spending-cap interruption. The interrupted attempt is excluded from this table; raw evidence remains private. Reported costs and times cover the selected attempts only, not total campaign spending or qualification calls. No automatic generation retries occurred. Original twelve-endpoint records and raw evidence were not overwritten.

The offline report generator audits the original freeze, qualification evidence, provider/model identity, sampling settings, prompts, workspace/checkpoint hashes and endpoint receipts. Only aggregate metrics and sanitized evidence are published. Credentials, clinical records, generated clinical datasets, validator dictionaries and raw session histories remain private.

Regeneration uses [the offline merger](../../../research_analysis/append_gemini_temperature.py) with `--replacement-06` and the locally retained evidence, followed by [the workbook builder](../../../research_analysis/artifacts/gemini_temperature.mjs). No model inference or new P21 validation is performed during reporting.
