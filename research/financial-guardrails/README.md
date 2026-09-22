# Financial Guardrails Research

Implement policies derived from Lakera's public documentation with NeMo Guardrails,
local models, rules, and custom classifiers. Evaluate the result on CNFinBench and
FinVault using HiPerGator and the available Navigator credit.

## Project documents

- [Execution plan](PLAN.md): architecture, model candidates, evaluation design,
  resource constraints, and verification gates.
- [Personal TODO](TODO.md): current tasks, prerequisites, and completion checks.

The project is in planning. No guardrail configuration, trained classifier, or
benchmark results have been produced yet.

## Organization

Keep project-specific work in this directory. Preserve the upstream NeMo package,
documentation, examples, and tests in their existing locations.

Create implementation directories only when they contain real work. Follow the
layout in the execution plan: policies, configurations, detectors, dataset adapters,
evaluation code, scripts, tests, and reports. Give the research application its own
environment and dependency lock when implementation starts.

Keep credentials, downloaded models, datasets, caches, and raw run outputs outside
version control. Store large artifacts on the approved HiPerGator storage tier;
track their versions and checksums in small manifests. Commit reviewed aggregate
reports and synthetic test fixtures only when their provenance and permissions
are clear.

Use relative links between project documents, update them when files move, and
commit each reviewed change as a focused checkpoint. Keep experiment revisions
fixed while upstream updates are integrated separately.
