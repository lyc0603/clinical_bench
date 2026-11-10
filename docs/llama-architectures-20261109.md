# Llama 4 Scout architecture extension

Two new independent exploratory attempts use DeepInfra's
`meta-llama/Llama-4-Scout-17B-16E-Instruct`: the existing 73-node GxP
adaptation and the existing variable-based AI-431 adaptation. Both target all
13 datasets and 531 specified variables. This is an independent adaptation,
not an execution of author-supplied code or a numerical replication.

The user authorized DeepInfra processing and both runs. The same input-only
source, qualified runtime image, prompts, gates, 32,768 output-token cap,
provider-default sampling and two attempts per task are retained. GxP uses
two dataset branches; AI-431 uses three variable workers. Neither receives
P21 repair feedback or historical generated programs. Code runs without
network access or credentials. Each run has its own frozen root and archive.

The only preclinical experimental code changes add an issuer-bound Llama
profile and permit that exact profile in the preparation helper. Reporting
changes append outcomes to the previous table. No clinical derivation,
prompt, gate, repair budget or formal main-study seal is changed.

Synthetic readiness verifies connectivity and returned model identity; it
does not establish compatibility with the full clinical prompt. In this
GxP attempt the service rejected the first request with HTTP 400. It reported
a 131,072 context limit, at least 98,305 input tokens and a 32,768 output
reservation. The input value is a lower bound, not an exact token count.
No prompt truncation or output-budget reduction is applied after observing
the outcome. Usage without a successful native receipt remains unknown.

All failures remain separate from historical outcomes. The publisher
requires two completed attempt reports, verified private evidence archives,
all 19 metric definitions and exact preservation of all 13 historical
records. Generated clinical material remains private. One attempt per
architecture supports descriptive feasibility observations only.

Preparation, execution and reporting entry points:

- `research_analysis.prepare_architecture_followup`
- `research_analysis.run_architecture_followups`
- `research_analysis.publish_llama_architectures`
- `research_analysis/build_architecture_followups.mjs`

The final results are linked from the repository README. Missing P21 scores
mean no evaluable terminal package was reached, not a successful validation
with zero findings.

AI-431 ended after 889.41 seconds: 48 variable tasks exhausted local attempts and the second VISNUMEN request timed out after 300.12 seconds. No dataset was delivered. The original reporting process then failed to import missing host pyreadstat. Reporting alone was recovered using pyreadstat 1.3.6 and narwhals 2.28.0 in a separate dependency directory. There were no terminal XPT files to decode. Original reporting state and log are retained; no clinical request was repeated.
