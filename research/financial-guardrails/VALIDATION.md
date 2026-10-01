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
audit metadata. Optional weights were not downloaded or executed. At the time of
this validation, CNFinBench and FinVault had not yet been supplied or run; this
record makes no benchmark-performance claim.

## Dataset intake update

Date: 2026-09-30

The supplied files were inspected locally without logging record contents. This is
an intake check, not a benchmark run.

| Dataset | Records | Labels | SHA-256 |
| --- | ---: | --- | --- |
| `cnfinbench-pooled.json` | 642 | 435 label 0; 207 label 1 | `9762ddbb3b4504cc523688956e3ecfdfa25bf5eb355949c5c5762aff5dead908` |
| `finvault-v5-fixed-full.json` | 1,043 | 510 label 0; 533 label 1 | `743ff07b0604fb55094046a68b5c3afa327f2b3c31c3c80fab3737b7f033cbe6` |

Both datasets contain unique case IDs and nested conversations whose messages use
`role` and `content`. Each metadata sidecar has one entry per dataset record. The
dataset files remain ignored by Git. Dataset-specific adapters, LLM-judge execution,
calibration, scoring, and benchmark runs are still pending.
