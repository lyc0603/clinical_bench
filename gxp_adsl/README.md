# Independent ADSL Process-DAG architecture pilot

This is a GxP-Agent-inspired architecture implementation on this repository's frozen benchmark, not the authors' original software or a replication of their numerical results. References: [GxP-Agent](https://arxiv.org/html/2608.16890v1), particularly the direct per-node experimental setup in section 5.1. No author repository code is copied.

## Scope and departures

- One excluded exploratory run, ADSL only: 49 specified variables and the GEN01 randomized population from the frozen study. It is not appended to the full-study 13-dataset metric table and does not change the formal main-study lock.
- Python/pandas/pyreadstat in the existing hash-pinned Docker image replaces R/pharmaverse. Intermediate artifacts are safe table-oriented JSON dataframes, not RDS or Python pickle. This tests the fixed process decomposition and validation architecture, not an admiral implementation.
- The model is the current benchmark's Claude Sonnet 5.5 through Anthropic Messages API, not the paper's Sonnet 4.6. Provider-default sampling/ reasoning settings and max_tokens 32768 are recorded. Hosted weights are not pinned.
- Fifteen fixed serial nodes replace free-form task planning. Node ownership covers every required variable once; nodes receive a narrow variable specification, upstream schema, actual SDTM schemas and relevant frozen rules. Direct fresh-context model calls generate each node's code. There is no OpenCode/LangGraph planning loop, model tool-use loop, LLM router or delegated subagent.
- Date/flag steps are reordered to meet our actual dependencies: screening/onset dates precede duration; EFFFL precedes completion flags. Source-specific dose quantities and disease duration belong to explicit nodes. Both changes are adaptations, not claims about the paper's precise DAG.

## Pipeline

`ingest → merge_dm → treatment variables → treatment dates → study dates → duration → population flags → disposition → completion → demographics → site → baselines → validate → metadata → export`

The controller checks exact eligible subject identities, one row per subject, cumulative expected variables and types, selected population/duration invariants, and protection of earlier derived values and program/artifact bytes. A candidate starts from the last accepted snapshot. Each node has at most two attempts (first plus one local code/QC correction). Failed attempts remain private and inspectable; exhausted failure blocks dependents. Provider errors, mismatched identity or uncertain completion stop scheduling without automatic API retry. No manual clinical code edits occur during a frozen run.

Character comparisons treat SAS missing/blank values and trailing storage padding as equivalent; numeric comparisons permit only serialization-level tolerance (rtol/atol 1e-12). This normalization does not waive name/type checks or clinical value errors. Define-XML version checking accepts the standard MetaDataVersion attribute location; parsing is not comprehensive XML schema validation.

Only the final export writes ADSL and Define-XML. The controller packages accepted node programs and a deterministic replay entry point. Independent offline reconstruction then compares the delivered XPT/Define-XML semantically and by bytes. Original clean-cache P21 evaluation is reused with expected_datasets set to ADSL; P21 findings are not returned to the model. Direct-source checks on selected DM predecessors and the SV Visit 3 anchor provide limited auxiliary evidence, not a complete independent derivation oracle. Structural checks and code execution do not establish value correctness or GxP compliance.

## Isolation and input boundary

The model receives frozen specification/schema context and may receive a bounded execution-error excerpt on local repair. API credentials stay in the host request headers and are never written in prompts or logs. Generated code runs with no network, dropped capabilities, four CPUs and 8 GiB memory. It can read only its copied source package and candidate workspace, not host evaluator code, reference ADaM, other experiments or credentials. The selected source package contains DM/SV/EX/DS/QS/VS/SC/MH, SAP and the ADSL-relevant specification subset. The final host P21 wrapper uses original frozen support inputs and dictionary configuration. Clinical inputs and outputs, requests, responses and logs remain private.

There is no overall agent repair-time cap. The 300-second HTTP timeout protects against an uncertain API transport; it does not trigger a retry. The original 1800-second offline execution/rebuild timeout is retained. Validation/reconstruction timeouts and infrastructure failures remain explicit.

## Reproduction

Use the existing evaluator Python environment. First run `python -m unittest gxp_adsl.test_gxp`. Short exact-model nonclinical connection and offline sandbox round-trip receipts are required before preparation. `prepare-freeze` requires `--base-config`, `--connection-receipt`, `--runtime-receipt`, `--root` (new private directory), and `--env-file`; `run` requires the same private root and environment file plus `--execute`. The freeze binds selected inputs, source provenance, schema context, model settings, node plan, system prompt, wrapper, pilot code, reused main code, runtime image, P21 cache and original validator support inputs. Code/input hashes are checked before each node. Never overwrite a previous attempt root or change code midway; a new implementation needs a separate freeze and run.

Public reporting should contain aggregate process/coverage/rebuild/P21 measurements and sanitized evidence hashes only. Do not combine this ADSL-only attempt with historical full-study endpoints, make inferential claims from one run, or interpret success on the gates as comprehensive clinical correctness. API tokens are recorded natively; monetary cost is unavailable unless a separately verified rate model is supplied.

The first retained run (2026-10-28) used max_tokens 8192 and stopped at validate with max_tokens after 12 accepted nodes. Its code, receipts and aggregate report remain retained. The revised run (2026-10-31) raises only the output allowance to 32768; all nodes are regenerated in a new frozen root. This is an explicit exploratory implementation revision, not an automatic retry or replacement of the first outcome.

## Controller repair — 2026-11-01 (not yet run)

After both retained failed development attempts, each node prompt now enumerates exact case-sensitive source paths (e.g. `/inputs/Input/dm.xpt`). The system prompt requests concise executable code and reinforces lowercase filenames. The parser accepts plain Python or one complete Python/py/unlabelled fenced block with optional surrounding explanation. Multiple blocks, unsupported languages, mismatched or incomplete fences and empty blocks are rejected. Code extraction happens inside the existing local QC attempt, so format errors consume the same two-attempt allowance. Provider truncation or identity mismatch still stops scheduling without automatic retry. Output allowance remains 32768.

Thirteen synthetic unit tests cover these contracts and the pre-existing structural/integrity checks. A retained failed response is checked offline only for successful extraction and syntax; this is not a clinical execution or a revised outcome. The original code from each measured attempt is archived privately with that run before edits. No prior freeze, state, response, accepted artifact or reported outcome is overwritten.

These changes alter the implementation and prompt, and can affect completion, tokens and cost. They do not alter the 49-variable specification, eligible population, clinical rules, two-attempt budget, final independent rebuild or P21 standard. Re-freeze in a new root before any further paid run. Keep the earlier failures visible; do not pool implementation revisions as prespecified repetitions, reuse earlier successful nodes, or claim this repair demonstrates clinical correctness. No new clinical API call is part of this repair.

## Export path repair — 2026-11-01 (not yet run)

The retained repaired run reached export but failed twice because its XML was written at `output/adam/define.xml`, outside the frozen evaluator contract. The export task now explicitly requires `output/adam/datasets/define.xml` beside `adsl.xpt`, with a relative XPT leaf href of `adsl.xpt`. A shared OUTPUT_FILES mapping supplies the exact deliverable paths to node prompts and controller checks. Missing XML errors identify the required path and, when present, the historical alternative path; malformed XML at the correct path is reported separately. No fallback promotion or automatic file relocation is performed.

All fourteen synthetic tests pass, including correct-path export, historical wrong-path rejection, malformed XML distinction and prompt/check path agreement. Before code edits, the measured run's original sources were archived privately and verified against its freeze. Prior failed receipts and artifacts remain unchanged. This is a prompt/controller revision requiring a new freeze and run, not a change to clinical rules or the existing failed result. No paid generation, independent clinical rebuild or P21 validation was performed as part of this repair.
