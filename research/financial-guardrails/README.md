# Open Lakera for NeMo Guardrails

Implement policies derived from Lakera's public documentation with NeMo Guardrails,
local models, rules, and custom classifiers. The core pipeline uses no paid APIs.
The supplied CNFinBench and FinVault exports are staged locally outside Git and
have passed integrity, schema, and adapter checks. The live execution runner,
leakage-safe splits, checkpoints, and pilots remain to be completed before evaluation.

## Project documents

- [Execution plan](PLAN.md): architecture, model candidates, evaluation design,
  resource constraints, and verification gates.
- [Personal TODO](TODO.md): current tasks, prerequisites, and completion checks.
- [Architecture](ARCHITECTURE.md): event/verdict contracts, precedence, modes, and failures.
- [NeMo hooks](NEMO_HOOKS.md): exact supported integration points and limitations.
- [Model decision](MODELS.md): pinned optional models, licenses, size, and hardware.
- [Judge runbook](JUDGE_RUNBOOK.md): selected NaviGator and HiPerGator backends,
  matched experiment conditions, and preflight commands.

The implementation includes deterministic defenses, versioned policies, role-aware
events, structured verdicts, detect/enforce modes, custom NeMo actions, retrieval
screening, and a guarded tool boundary. Optional local-model adapters are disabled
by default. No benchmark results have been produced.

The policy-reading LLM judge contract is implemented in
[`financial_guardrails/judge.py`](financial_guardrails/judge.py). Its exact written
policy is [`policies/llm_judge_v1.yml`](policies/llm_judge_v1.yml). It validates a
strict JSON response, rejects unknown policy IDs, applies a timeout, and enters the
same deterministic aggregation path as every other detector. The selected backends
are NaviGator `gpt-oss-120b` and local HiPerGator `Qwen/Qwen3-8B-AWQ`. They share
one OpenAI-compatible client and remain disabled in the default profile, so offline
commands make no model calls.

## Run the offline baseline

From this directory, with `uv` installed:

```bash
uv sync --locked
uv run --locked python -m financial_guardrails
uv run --locked pytest -q
```

The configuration entry point is [`config/config.yml`](config/config.yml), its
Colang rails are in [`config/rails.co`](config/rails.co), and the implementation is
in [`financial_guardrails/`](financial_guardrails/). The source-linked behavior and
known gaps are recorded in [`policies/POLICY_MAPPING.md`](policies/POLICY_MAPPING.md).

`OPEN_LAKERA_PROTECTED_VALUES` may contain a JSON list of secret canaries or other
application-owned values that must never be released. Keep real values in the
environment; do not add them to `config.yml` or version control.

Detect mode records metadata and preserves content:

```python
from financial_guardrails import FinancialGuard, Mode

guard = FinancialGuard(mode=Mode.DETECT)
```

Install the optional model runtime with `uv sync --locked --extra local-models`.
Runtime adapters only load pinned files already present in the local Hugging Face
cache. Downloading, GPU validation, and calibration are separate explicit steps;
the rules-only test suite never downloads weights or calls hosted inference.

This project buffers complete text. It is not a complete PII product, URL reputation
service, or substitute for host authentication and authorization. Review the
coverage matrix before deployment.

## Organization

Keep project-specific work in this directory. Preserve the upstream NeMo package,
documentation, examples, and tests in their existing locations.

Create implementation directories only when they contain real work. Follow the
layout in the execution plan as later stages add dataset adapters, evaluation code,
scripts, manifests, and reports. This research application has its own project file
and dependency lock.

Keep credentials, downloaded models, datasets, caches, and raw run outputs outside
version control. Store large artifacts on the approved HiPerGator storage tier;
track their versions and checksums in small manifests. Commit reviewed aggregate
reports and synthetic test fixtures only when their provenance and permissions
are clear.

The supplied exports are loaded with `cnfinbench_adapter` and `finvault_adapter`.
The FinVault adapter preserves agent actions as tool calls and environment messages
as tool results. It does not execute those actions. The binary metric helper requires
the positive label to be specified explicitly and reports detector failures outside
the confusion matrix.

Use relative links between project documents, update them when files move, and
commit each reviewed change as a focused checkpoint. Keep experiment revisions
fixed while upstream updates are integrated separately.
