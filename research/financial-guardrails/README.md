# Financial Guardrails Research

Implement policies derived from Lakera's public documentation with NeMo Guardrails,
local models, rules, and custom classifiers. Evaluate the result on CNFinBench and
FinVault using HiPerGator and the available Navigator credit.

## Project documents

- [Execution plan](PLAN.md): architecture, model candidates, evaluation design,
  resource constraints, and verification gates.
- [Personal TODO](TODO.md): current tasks, prerequisites, and completion checks.

The first offline guardrail configuration is implemented. It uses deterministic
rules and custom NeMo actions, makes no provider calls, and fails closed when a
required check does not run. It is a transparent baseline for later model-backed
detectors and benchmark evaluation; no benchmark results have been produced yet.

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

`FIN_GUARD_PROTECTED_VALUES` may contain a JSON list of secret canaries or other
application-owned values that must never be released. Keep real values in the
environment; do not add them to `config.yml` or version control.

This baseline supports buffered text and an example read-only tool boundary. Its
rules recognize selected explicit English and Chinese attacks. It is not a general
semantic moderation model, a complete PII detector, or a substitute for application
authentication and authorization. See the policy mapping before deployment.

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
