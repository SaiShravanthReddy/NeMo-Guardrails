# Validation record

Date: 2026-09-22
Scope: first offline Lakera-inspired NeMo guardrails configuration

| Check | Result |
| --- | --- |
| `uv run --locked python -m financial_guardrails` | Passed: 4 of 4 smoke cases |
| `uv run --locked pytest -q` | Passed: 31 tests; three upstream deprecation warnings |
| `uv run --locked ruff check .` | Passed |
| `uv run --locked ruff format --check .` | Passed: 13 files already formatted before repository license headers were added |
| `uv run --locked ty check` | Passed |
| Repository pre-commit hooks on project files | Passed: YAML, EOF, whitespace, Ruff, formatting, license, and ty; zizmor skipped because no workflow files changed |
| `git diff --check` | Passed |

All functional tests are offline and make no LLM, Navigator, or other provider
requests. They validate the configured NeMo rails, rule decisions, redaction,
failure when a required action is skipped, and denial before unauthorized tool
execution. CNFinBench and FinVault were not run because their project datasets have
not yet been supplied; this record makes no benchmark-performance claim.
