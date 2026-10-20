> ARCHIVED: superseded paired-design proposal (9 pairs, 27 phase invocations).
> Do not use for the current main study. See [the current protocol](../main-study-protocol.md)
> and [workflow](../main-experiment-workflow.md).

# Main-study protocol v2

## Question and scope

Does one round of P21-guided repair improve ADaM conformance beyond one round of self-review, and do selected independent derivation checks show different effects?

Three explicit provider/model IDs, three independent generations per model, one repair per branch: 9 paired trials and 27 agent calls. The pilot is excluded from main-study estimates. This is an exploratory single-study experiment, not a powered model ranking or a certification of submission readiness.

## Frozen models and inputs

Use the exact API IDs in the sealed config, never CLI defaults, latest aliases or automatic substitutions. The planned selection is openai/gpt-6.1-sol (retained from pilot), anthropic/claude-sonnet-4-6 and google/gemini-3.1-pro-preview. These are explicit study choices rather than a claim about all three native CLIs' defaults. [Anthropic model versioning](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions) and [Google model documentation](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-pro-preview) document the latter two IDs. Preview backends can change despite an unchanged ID; retain requested/reported IDs and dates, and do not claim immutable model weights.

Allowlisted frozen SDTM, SAP and legacy Define metadata are identical for all models. The study intentionally supplies legacy ADaM metadata. No reference ADaM, pilot agent code, repaired output or independent evaluator is supplied to agents. Required datasets are the 13 domains in config.json. Hash every input file and the exact three rendered prompts before the first main-study call.

## Execution and budget

Use the pinned Docker image ID, OpenCode version, image library versions, host evaluator Python/library versions, Java binary, P21 client/engine/configuration/CT hashes. The seal also covers runner, independent checker, scoring rules, protocol text, prompts and randomized trial schedule. Changes require a new version and separate output directory. Each P21 call uses a disposable copy of the pinned cache. Writable engine-index bookkeeping is excluded from the after-call binary/rule comparison; any other runtime/rule drift invalidates that validation. The canonical shared cache stays unchanged.

Per call: 1,800 seconds, 4 CPUs and 8 GiB configured Docker memory; 13.5 maximum agent hours across 27 calls. Each branch receives exactly one fresh repair session. Tokens, tools and cost are recorded when available; there is no hard token/cost/tool cap. Equal wall-time limits do not guarantee equal tokens or compute. Sampling and reasoning settings use provider defaults with no explicit overrides; these defaults and remote backend state are uncontrolled limitations. The schedule seed is 20261011, not a model-generation seed.

Both branches copy identical initial artifacts. Self-review receives no P21 or independent-check feedback. P21 feedback receives only the preceding P21 report and its metrics. Independent checks remain evaluator-only. Rebuilds have 1,800-second limits and P21 calls 900-second limits. No score-driven early stopping, extra repair calls, silent retries or replacement models. Interrupted attempts remain recorded and require explicit adjudication before any new run.

## Outcome A: P21 conformance

Primary conformance outcome: number of dataset-rule pairs with findings. Within-trial reduction = initial minus final. Paired feedback advantage = final self-review minus final P21-feedback count. Positive values favor P21 feedback. Record finding instances, distinct rules, newly appearing rules, record counts, package completion, byte reproducibility, elapsed time and reported usage separately.

Pins: client 1.0.9, FDA 2508.1, ADaMIG 1.3, ADaM Model 2.1, ADaM/SDTM CT 2026-03-27; AE/DM/EX support. ADaM validation uses Define metadata; it is not standalone Define-XML certification. MedDRA not configured is the sole allowed qualification. MedDRA-dependent checks are outside scope.

Conformance paired eligibility requires completed initial and both repairs, all required domains and Define, fresh qualified P21 reports, identical qualification status and byte-identical independent rebuilds. Missing/invalid reports and failed runs never count as zero findings. Report all 9 planned trial denominators, completed counts and eligible counts alongside eligible-pair summaries.

## Outcome B: selected independent derivation correctness

Report errors and assessable denominators separately by each frozen check in legacy-paired-scoring-rules.json; never combine these with P21 into one score. No overall clinical accuracy percentage is defined. Primary independent checks cover NPI available Week4–24 means and baseline covariates, and exact TTE predecessor links. Coverage checks identify missing, extra or duplicate subjects. TTE event-status/date checks are conditional on exported treatment-emergent/query flags. Duration and censor checks test implemented conventions and are exploratory.

The host checker reads exported XPT and raw frozen SDTM and never executes generated analysis programs. NPI independently selects nonmissing source NPTOT within SAP windows (Week4 22–35, then 14-day increments through Week24 162–175), closest target, earlier-date tie; averages available selected values. Baseline uses elapsed day <1, closest to target day1. Randomization anchor is earliest complete SV VISITNUM=3, with DM.RFSTDTC fallback; same-date sequence ties use QSSEQ. These source/tie conventions require clinical confirmation; population filtering and ANCOVA are outside scope.

Representation contract from supplied study metadata: NPI summary PARAMCD=NPTOTMN and AVISITN=98; dermatologic TTE PARAMCD=TTDE, declared SRCDOM=ADAE, SRCVAR=ASTDT; SRCSEQ must identify final ADAE ASEQ and the selected AESEQ. The checker must distinguish different events on the same date. Unsupported representations/missing fields are unavailable, not automatically incorrect or successful. The main-study code can use other sponsor-specific field names elsewhere.

Correctness-check comparability is separate from P21 eligibility: require the check to be scored in all three stages, its relevant coverage checks to pass, and assessed denominators to agree. Retain unavailable/failing coverage outcomes in reports. Report initial, self-review and feedback errors per check and descriptive paired differences only for comparable checks. Do not cherry-pick stages or exclude failures from completion denominators. The checker does not independently medically adjudicate the dermatologic PT list, establish censoring/day-count conventions, or certify every ADaM derivation.

## Analysis and reporting

For each model report all planned/completed/eligible trials, initial and final conformance counts, paired differences and individual trial trajectories. With only three generations per model, present descriptive means/medians and ranges; do not claim statistical power, definitive model rankings or generalization across studies. Independent derivation errors/denominators and missing coverage appear in a separate results file and table. Report the unchanged-ID preview-backend limitation and any observed provider failures or drift.

## Launch gate and amendments

Freeze is not a paid experiment launch. Run the no-inference preflight using the sealed config, verify provider keys and exact model catalog entries, then assess account access at launch. Never paste keys into config, protocol or Git. If an ID is unavailable, budgets change, or any frozen file/runtime drifts, create protocol v2 before main-study calls. Do not overwrite this protocol or mix versions.

## Pre-launch amendment

Version 2 supersedes the locally sealed v1 before any main-study calls. The only design amendment isolates P21 cache bookkeeping and detects binary/rule drift during validation. Models, prompts, inputs, budgets and independent scoring rules remain the same. Version 1 is retained as a superseded record and must not be launched.
