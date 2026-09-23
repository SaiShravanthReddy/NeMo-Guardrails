# Open Lakera for NeMo Guardrails

Implement policies derived from Lakera's public documentation with NeMo Guardrails,
local models, rules, and custom classifiers. The core pipeline uses no paid APIs.
Future evaluation will use CNFinBench and FinVault after their files are supplied.

## Project documents

- [Execution plan](PLAN.md): architecture, model candidates, evaluation design,
  resource constraints, and verification gates.
- [Personal TODO](TODO.md): current tasks, prerequisites, and completion checks.
- [Architecture](ARCHITECTURE.md): event/verdict contracts, precedence, modes, and failures.
- [NeMo hooks](NEMO_HOOKS.md): exact supported integration points and limitations.
- [Model decision](MODELS.md): pinned optional models, licenses, size, and hardware.

The implementation includes deterministic defenses, versioned policies, role-aware
events, structured verdicts, detect/enforce modes, custom NeMo actions, retrieval
screening, and a guarded tool boundary. Optional local-model adapters are disabled
by default. No benchmark results have been produced.

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

Use relative links between project documents, update them when files move, and
commit each reviewed change as a focused checkpoint. Keep experiment revisions
fixed while upstream updates are integrated separately.
