# Validation record

Date: 2026-09-23
Scope: Open Lakera rules-only configuration and optional-model interfaces

| Check | Result |
| --- | --- |
| `uv run --locked python -m financial_guardrails` | Passed: 4 of 4 smoke cases |
| `uv run --locked pytest -q` | Passed: 65 tests; seven upstream deprecation warnings |
| `uv run --locked ruff check .` | Passed |
| `uv run --locked ruff format --check .` | Passed: 13 files already formatted before repository license headers were added |
| `uv run --locked ty check` | Passed |
| Repository pre-commit hooks on project files | Passed: YAML, EOF, whitespace, Ruff, formatting, license, and ty; zizmor skipped because no workflow files changed |
| `git diff --check` | Passed |

All functional tests are offline and make no LLM, Navigator, or provider requests.
They validate policies, event/verdict schemas, modes, aggregation, detector errors,
NeMo equivalence, retrieval, tool authorization, local-model contracts, and safe
audit metadata. Optional weights were not downloaded or executed. CNFinBench and
FinVault were not run because their project datasets have not yet been supplied;
this record makes no benchmark-performance claim.
