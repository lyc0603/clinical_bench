# DeepInfra nonclinical qualification

This extension qualifies `deepinfra/openai/gpt-oss-20b` and `deepinfra/openai/gpt-oss-120b` using the existing pinned OpenCode image. It does not launch clinical generation or the main study and does not modify the original sealed runner.

Both models use explicit temperature 1.0, medium reasoning effort, 131,072 context metadata and 16,384 maximum response tokens. The title helper is disabled. The native `@ai-sdk/deepinfra` adapter appends `/openai/chat/completions`, so its configured base URL is `https://api.deepinfra.com/v1`. The API key is provided only through the environment; never commit a credential.

The provider extension permits only `api.deepinfra.com` through the unchanged gateway and namespace firewall machinery. Existing denied webfetch, websearch and subagent permissions remain. Completion reuses all original exported-current-turn structural checks with a stop-only profile and adds exact provider/model identity and configuration checks. It does not relabel unknown reasons as success.

Run `python -m open_model_extensions.deepinfra_readiness transport --out <fresh-private-directory> --env-file <local-env>`. This uses a dummy credential, a local HTTP mock and Docker network none. It captures parameters and confirms that the only selected model, endpoint, temperature, reasoning effort, output limit and tool schema match the declaration. It establishes serialization, not provider sampling internals.

Then run the same module with `smoke --transport <transport-directory> --out <another-fresh-private-directory> --env-file <local-env> --execute`. Each model receives an empty input mount and two short nonclinical turns: write/read a marker through bash, then continue the same session and read it again. The receipt requires successful tools, normal completion, model identity, session continuity, usage telemetry, unchanged code/config and preserved evidence. A 300-second per-turn limit applies only to these short probes. Failed attempts remain private; no automatic clinical retry occurs.

Passing these checks does not establish long-context reliability, task accuracy, all sixteen research outcomes, fixed server-side weights or private deployment. Clinical input transfer to this new recipient requires the user's authorization before a separately frozen experiment can start. Reasoning token and invoice reconciliation must be recorded separately from telemetry estimates.
