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
dataset files remain ignored by Git. At that checkpoint, dataset-specific adapters,
LLM-judge execution, calibration, scoring, and benchmark runs were still pending.

## Blocker-removal update

Date: 2026-10-01

- Added a provider-independent policy-judge detector and the exact versioned policy
  text supplied to it. Tests cover allow/block results, malformed output, unknown
  policy IDs, timeout behavior, and direct/NeMo agreement using offline fakes.
- Loaded all 642 CNFinBench and 1,043 FinVault records through strict adapters.
  CNFinBench contains 15,408 ordinary messages. FinVault contains 1,043 ordinary
  messages, 4,838 tool calls, and 4,838 tool results.
- Added binary metrics that keep execution failures separate and require callers to
  state which source label is positive.
- Added application-boundary screening for tool descriptions because this fork does
  not expose tool descriptions as a standalone `check_async` rail type.
- Full offline project suite: 88 passed with nine upstream deprecation warnings.
- Ruff check, Ruff format check, and ty check passed.

No live LLM, external provider, model download, or benchmark evaluation was used in
these checks. Selecting and validating the live judge remains pending.

Source-converter review confirmed that label `1` is unsafe for both exports. It also
confirmed that FinVault full label `0` combines benign and defended cases, while
label `1` represents successful attacks. This prevents using the full label directly
as an attack-attempt interception label without a separately documented derived view.

## Dual-backend update

Date: 2026-10-01

- Selected NaviGator `gpt-oss-120b` and local HiPerGator
  `Qwen/Qwen3-8B-AWQ` at immutable revision
  `4da05a8edb55c6046cce958586c33b61da07bb79`.
- Added a shared OpenAI-compatible client with environment-only credentials,
  HTTPS or loopback URL validation, bounded responses, strict response extraction,
  and provider-error redaction.
- Added offline tests for request shape, credential requirements, endpoint safety,
  configuration validation, provider failures, and local model revision loading.
- Full offline project suite: 97 passed with nine upstream deprecation warnings.
- Ruff check, Ruff format check, ty, and repository pre-commit passed. The SLURM
  script passed `bash -n`.

No NaviGator request, model download, GPU allocation, or benchmark inference was
performed. The two live fixture preflights remain required before any pilot.

## Metric collection update

Date: 2026-10-01

- Added a bounded `risk_score` to the judge contract and propagated it through
  detector results and final verdicts. Decision/score inconsistencies fail closed.
- Added classification, ranking, threshold, calibration, operations, slice, paired,
  and grouped-bootstrap metrics without adding a statistics dependency.
- Added content-free case telemetry and atomic run artifacts with strict manifests.
- Added backend telemetry for latency, provider token usage, estimated NaviGator
  cost, and sanitized failure codes.
- Full offline project suite: 115 passed with nine upstream deprecation warnings.
- Ruff, Ruff format, and ty passed on the changed Python files.

No metric in this update is a benchmark result. Sanitization quality, task utility,
authorization correctness, and attack prevention remain unavailable until their
required ground truth or interactive environment exists.

## Static evaluation and HiPerGator handoff

Date: 2026-10-01

- Safely parsed all 4,838 recorded FinVault actions without importing or executing
  any named tool.
- Generated group-disjoint splits for all 642 CNFinBench and 1,043 FinVault cases.
- Completed rules-only pilot replays: 48 CNFinBench and 64 FinVault cases, with no
  detector failures. These are engineering checks of the runner, not final efficacy
  claims.
- Completed rules-only full static replays over all 642 CNFinBench and 1,043
  FinVault cases with no detector failures. The initial FinVault replay exposed
  the missing benchmark tool policy; the reviewed 197-tool policy supersedes it.
- The local readiness check verified dataset checksums, metadata, adapters, action
  parsing, the pinned Qwen revision, and both SLURM scripts.

## FinVault tool-policy review

Date: 2026-10-01

- Reconciled the supplied 203-tool draft against the exact evaluation export: 197
  unique tools and 4,838 recorded calls.
- Removed six tools absent from the evaluation file and recomputed all counts and
  argument inventories.
- Added conditional blocking for explicit bypass, override, skip, concealment,
  under-reporting, and dual-contract boolean arguments across 27 tools.
- The full rules-only replay completed all 1,043 cases without detector failures.
  Its scores are diagnostic baseline measurements, not commercial Lakera results.

## HiPerGator deployment correction

Date: 2026-10-01

The first local-model preflight (`44275641`) failed before serving because
FlashInfer attempted JIT compilation and the isolated vLLM environment did not
contain `ninja`. The environment setup now pins `ninja==1.13.0`; readiness and both
GPU job scripts verify its executable before GPU initialization. No model verdict
or benchmark result was produced by the failed job.

The first login-node readiness retry incorrectly required `nvidia-smi`. HiPerGator
provides that executable inside GPU allocations, so the login check now verifies
`sbatch`, vLLM, and `ninja`; the GPU job remains responsible for verifying the
allocated NVIDIA device before starting the server.

The first NaviGator CNFinBench cascade completed inference but failed while creating
its artifact because the manifest schema accepted only scalar generation settings;
the backend uses a nested `response_format` object. The schema now accepts recursive
JSON values and has a live-backend-shaped regression test. Explicit checkpoint and
inference-commit options allow the completed content-free checkpoint to be finalized
without repeating provider calls.

The second local-model preflight (`44279980`) found the pinned `ninja` executable
but vLLM's FlashInfer child process could not resolve it because the isolated
environment's `bin` directory was absent from `PATH`. Both GPU scripts now prepend
that directory, verify `command -v ninja` resolves to the pinned executable, and run
`ninja --version` before starting vLLM.

The third local-model preflight (`44280869`) loaded Qwen3-8B-AWQ successfully and
started vLLM. Its safe fixture then returned a syntactically valid but internally
contradictory allow verdict, which the strict response validator rejected. The judge
prompt now states the required allow fields explicitly, and both backends use
deterministic sampling settings before the next two-fixture preflight.
