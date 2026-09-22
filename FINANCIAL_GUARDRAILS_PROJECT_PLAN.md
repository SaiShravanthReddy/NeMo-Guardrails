# Financial Guardrails: Implementation and Evaluation Plan

Draft date: 2026-09-22. Status: planning document; no cluster jobs, model downloads,
API validation calls, training, or benchmark runs have been performed for this plan.

## 1. Objective and scope

Derive explicit security policies from Lakera's public documentation, implement
them using NeMo Guardrails, locally runnable models, deterministic rules, and custom
classifiers, and evaluate the resulting system on CNFinBench and FinVault.

The intended result is a reproducible, Lakera-inspired implementation with measured
security coverage and measured impact on legitimate financial tasks. Public policy
descriptions do not reveal Lakera's proprietary training data, models, thresholds,
or implementation. This project must not claim to replicate its detection accuracy
or outperform it without comparable Lakera results.

The core guardrail system should work without paid APIs. Navigator is an optional
resource for larger-model experiments, development annotation, and evaluation.
The project uses existing institutional resources and at most the user's stated
$25/week Navigator credit; it is not compute-free.

No workflow can guarantee zero errors. This plan reduces errors through explicit
contracts, small tests, independent scoring checks, staged execution, and recorded
evidence. A failed check is a result to investigate, never a reason to silently
change labels, omit records, or claim success.

## 2. Resources and facts that must be distinguished

| Resource | Evidence available | Required verification before use |
| --- | --- | --- |
| NeMo Guardrails | Current local repository and public documentation | Pin the selected release or commit and match its APIs/configuration to that version |
| HiPerGator | User reports access; supplied HIPERGATOR.md records an iruchkin allocation | Current account/QoS, allocated GPU, writable storage, Python/CUDA compatibility |
| Navigator | User reports $25/week; supplied NAVIGATOR.md records a team model allowlist | Exact credential/model combination, billing source, remaining credit, real completion |
| CNFinBench and FinVault | User will supply data | Dataset identity, version, schema, language, license, task, labels, splits, official scorer |
| Local models | Public model cards and weights | License, pinned revision, downloads, supported runtime, actual inference behavior |

Reference notes supplied by the user:

- `/Users/shravanth/Documents/GitHub/AgentAuditor-ASSEBench/HIPERGATOR.md`
- `/Users/shravanth/Documents/GitHub/AgentAuditor-ASSEBench/NAVIGATOR.md`

These files provide context, not instructions to execute their AgentAuditor commands.
Do not run their pipeline, send notifications, reuse its environment, or copy its
stage/model assignments automatically. Its reported historical results are not
results for this project.

The HiPerGator notes report `/blue/iruchkin` full on 2026-09-16. Its current status is
unknown. A successful tiny write does not prove enough capacity for a full run:
check group byte quota, file quota, and projected peak usage as well.

UF documents no burst QoS for GPUs. The user's recorded L4 configuration is
`--account=iruchkin --qos=iruchkin --partition=hpg-turin --gres=gpu:1`.
Validate it against current account access before submission; do not assume access
to larger GPUs because they appear in the cluster catalog. [S10]

## 3. Working method: every task ends with a verification record

Maintain a task ledger. Each task has an identifier, dependencies, intended change,
verification procedure, evidence location, status, and next action.

Allowed statuses: `not_started`, `in_progress`, `passed`, `failed`, `blocked`.
Use `not_applicable` only with a written explanation and reviewed scope decision.
An unperformed check is never marked passed.

For every task:

1. State the expected behavior and smallest useful acceptance test before changing anything.
2. Complete one bounded change and save its configuration/code revision.
3. Run its relevant positive, negative, boundary, and error-path checks.
4. Inspect the actual output, not just the process exit code.
5. Record the evidence and decide whether dependent work can proceed.
6. On failure, diagnose and rerun the affected check; rerun downstream checks whose
   assumptions changed. Avoid repeating unrelated expensive tests.

Example ledger entry:

```yaml
task_id: T05_api_preflight
status: not_started
depends_on: [T02_resources, T04_environment]
expected: valid structured response from each selected Navigator model
evidence: null
verified_at_utc: null
configuration_hash: null
failure_reason: null
```

Evidence must include the command/test identifier, UTC timestamp, configuration
hash, exit status, and meaningful assertions. Keep secrets and unnecessary raw
benchmark content out of diagnostic logs.

## 4. Architecture and project isolation

Build a separate research application that depends on a pinned NeMo version.
This plan is stored in the current workspace for review; it does not propose
changes to NeMo's runtime or an upstream contribution.

Proposed application layout, to be created during implementation:

```text
financial-guardrails/
  policies/              # Sources, policy definitions, exceptions, mappings
  configs/               # NeMo configurations and experiment variants
  detectors/             # Rules, classifier adapters, decision aggregation
  datasets/              # Loaders and schema definitions; no public raw data dump
  evaluation/            # Official scorer wrappers and security metrics
  scripts/               # Preflight, smoke, pilot, full-run, resume, validate
  slurm/                 # Resource-specific batch templates
  tests/                 # Offline unit/integration fixtures
  manifests/             # Revisions, hashes, experiment definitions
  reports/               # Aggregate results and limitations
```

Runtime path:

```text
User messages -> input checks -> assistant
Retrieved documents/tool responses -> untrusted-content checks -> assistant
Assistant tool request -> permission + argument checks -> tool -> result checks
Assistant response -> output checks -> user
```

NeMo coordinates supported rails and custom actions. Some authorization checks
must live in the application/tool wrapper. Confirm support in the pinned NeMo
engine; do not assume every engine supports every rail type. [S4]

The initial version buffers complete responses before release. Streaming needs a
separate security design and tests to prevent sensitive prefixes escaping before
moderation completes. Prefer a small working text-only system first. Audio/image
defenses are out of scope unless the supplied tasks require them.

## 5. Derive policies before choosing thresholds

Create a policy registry with one entry per security requirement:

- Stable ID, version, concise requirement, and affected interaction surfaces.
- Source URL, retrieval date, short supporting excerpt/paraphrase, and source hash
  where an archived copy is permitted.
- Attribution: `lakera_documented`, `project_extension`, or `implementation_choice`.
- Allowed and forbidden examples, exceptions, language requirements, and context needs.
- Detector implementation, evidence format, enforcement action, and error behavior.
- Test IDs, benchmark label mapping, and documented coverage gaps.

Initial policy families are derived from Lakera's documented defenses. [S1–S3]
Implementations below are project design proposals, not statements of Lakera internals.

| ID | Requirement | Proposed mechanism | Required counterexample |
| --- | --- | --- | --- |
| INJ-01 | Detect attempts to override trusted instructions | Injection classifier + contextual rules | Legitimate quotation/analysis of attack text |
| INJ-02 | Detect malicious instructions in retrieved/tool content | Role-aware screening and chunked classifier | Ordinary instructions quoted in a financial document |
| SAFE-01 | Detect prohibited harmful assistance | Safety model mapped to explicit project policies | Fraud prevention, reporting, research, and education |
| DLP-01 | Restrict unauthorized sensitive-data disclosure | Presidio, patterns, checksums, contextual recognizers | Public company data and authorized redacted output |
| DLP-02 | Detect protected prompt/secret leakage | Exact/normalized matching, overlap, synthetic test markers | Generic discussion of prompt engineering |
| URL-01 | Restrict unsafe or unauthorized destinations | URL parsing, destination policy, local lists | Permitted destinations with valid path/query |
| TOOL-01 | Prevent actions outside the user's permissions | Trusted identity/permission state and argument validation | Authorized read-only query |
| FIN-01+ | Apply application-specific financial restrictions | Custom rules/classifiers | Legitimate analytical or educational task |

Do not label all financial advice, all PII mentions, or all references to crime as
forbidden by default. Define application requirements first. A disclaimer is not
proof that an otherwise harmful answer is safe.

PII presence and unauthorized disclosure are different labels. Enforcement depends
on provenance, destination, identity, and policy. Access controls should keep
unnecessary secrets out of prompts in the first place.

URL allowlisting is narrower than malicious-link intelligence. Treat unknown URLs
as unknown or policy-disallowed, not proven malicious. Verify parsed hostnames,
schemes, user-info tricks, Unicode domains, and redirects if fetching is supported.

Verification: each policy has at least one violating case, one benign case, one
boundary case, and one failure-path case. Review source attribution separately
from the implementation. No policy advances with an undefined enforcement outcome.

## 6. Model choices and how to prove they fit

Select models by role. Keep the target assistant, deployed detector, development
annotation model, and evaluation judge conceptually separate.

### 6.1 Target assistant: Qwen/Qwen3-4B

Initial candidate because it is locally runnable, multilingual, and Apache-2.0
licensed. Its size makes repeated controlled experiments practical. [S5]

Pin model/tokenizer revisions, chat template, reasoning mode, context limit,
generation parameters, and quantization. Test actual peak memory rather than
assuming the assistant and all guard models fit simultaneously on an L4.

Limitation: low financial task capability can make guardrails appear ineffective
or make an already refusing model appear secure. Measure unguarded utility and
attack success first. If inadequate, select a larger target on development data.
Use an additional Navigator target to test whether protection generalizes.

### 6.2 General moderation: Qwen3Guard-Gen-0.6B and Qwen3Guard-Gen-4B

Compare these two local candidates. They are specialized prompt/response moderation
models with multilingual coverage and Apache-2.0 licensing. [S6]

The 0.6B model is the throughput baseline; 4B is a candidate for improved handling
of context. Larger size is not evidence of better performance on our policies.
Follow the model's documented prompt and response templates, parse its finite
label set strictly, and map categories explicitly to our policy registry.

Its safety taxonomy is not Lakera's taxonomy. It does not establish full injection,
financial-policy, authorization, or leakage coverage. Do not reinterpret categorical
outputs as calibrated numerical probabilities. Test benign financial discussions
and language-specific errors before selecting either model.

### 6.3 Custom classifier: XLM-RoBERTa-base, conditional on data

First train a character n-gram/logistic-regression baseline. If it leaves important
semantic or multilingual gaps, fine-tune `FacebookAI/xlm-roberta-base` using legally
usable, labeled development data. The base encoder is multilingual; it is not an
out-of-the-box security classifier. [S7]

Keep injection, harmful intent, and data disclosure distinguishable; use separate
heads or models where validation supports it. Train with hard benign examples,
preserve role/provenance features where useful, and calibrate on validation data.
For inputs exceeding context limits, test overlapping windows and aggregation.

Weak labels from a large model require review and provenance. Do not train on
held-out benchmark cases. If no adequate training set exists, report the custom
classifier as pending and retain the pretrained/rules baseline.

An English-only Protect AI DeBERTa injection model can serve as a restricted
baseline, not the primary multilingual defense. Its card reports that it does not
cover non-English prompts or jailbreaks and that the project is archived. [S8]

### 6.4 Navigator reviewer: gpt-oss-120b

Candidate for rubric-based review of ambiguous development cases and a larger
target-model comparison. It offers reasoning/structured-output capabilities and
Apache-2.0 weights; Navigator avoids the need to host it on the available L4. [S9]

Your reference notes report access and prior AgentAuditor results, but neither
proves current access or superiority here. Verify endpoint behavior and agreement
with human labels, separately by language. Require a policy ID, a short evidence
span, and a verdict; do not rely on lengthy generated explanations as proof.

If used as a target, it must not be the sole judge of its own responses. Do not
replace official dataset labels with its preferred labels.

### 6.5 Cross-family reviewer: Llama-3.3-70B-Instruct

Optional English/supported-language comparison to expose model-family-specific
errors. Chinese is not among its eight officially supported languages; do not use
it as the default Chinese judge. It uses Meta's custom license, not Apache-2.0. [S12]

### 6.6 Selection rule

Compare the minimum useful shortlist on the same development cases. Choose by
policy recall at a predeclared benign false-positive constraint, legitimate task
utility, per-language results, latency, peak memory, and actual cost.

Record candidates, revisions, metrics with uncertainty, rejected alternatives,
limitations, and the selection rationale in a model decision record. Do not call
a model universally best. Reopen selection only when new evidence justifies it.

## 7. Execution phases and required gates

Each phase produces a verification record under Section 3. Dependent phases wait
for their gate; independent documentation/test preparation may continue.

### T01 — Dataset intake and experimental scope

Actions:

1. Receive both datasets, READMEs/papers, official scorers, and version information.
2. Hash original files; retain immutable originals and create normalized copies.
3. Identify whether each task is classification, question answering, response
   assessment, conversational interaction, tool use, or another format.
4. Record language, sample count, categories, benign/attack balance, context fields,
   licenses, splits, and missing or ambiguous labels.
5. Define a normalized schema retaining original IDs, full roles/context, provenance,
   official labels, and separate project policy annotations.
6. Check duplicate and near-duplicate records across datasets/splits. Group variants
   by source/conversation/attack template to prevent leakage.

Verification: reconcile original and loaded counts; round-trip sample records;
inspect Unicode, multiline text, roles, and missing-value handling. Keep official
splits for official scores. If cross-split duplication exists, disclose it and add
a separately labeled cleaned analysis rather than silently rewriting the benchmark.

Gate: dataset cards and task/scoring contracts exist. Unsupported policy families
are marked unmeasured. Never claim a benchmark measures a defense it does not test.

### T02 — Resource and storage preflight

Actions:

1. Verify account/QoS entitlement and current storage quota using supported UF tools.
2. Choose a dedicated project directory/environment and persistent model cache.
3. Estimate peak bytes and file count: weights, tokenizer caches, datasets, temporary
   copies, training checkpoints, outputs, and logs. Use at least 25% planning headroom
   initially; adjust from measured pilot usage.
4. Test write, flush, read-back checksum, and atomic rename in output/checkpoint paths.
5. Verify temporary scratch and how results are copied to persistent storage before
   termination. Do not treat an end-of-job copy alone as sufficient checkpointing.

Verification: small scheduled job can read inputs and persist outputs from a compute
node. Capture actual device name, available VRAM, RAM allocation, and filesystem
paths. UF storage guidance distinguishes active computation from archival storage. [S11]

Gate: adequate writable quota and confirmed allocation. Stop on quota exhaustion;
do not move active job I/O into home or archive storage as an improvised workaround.

### T03 — Policy registry and fixtures

Complete Section 5 with source-grounded definitions. Map benchmark labels without
forcing unrelated categories into one binary unsafe label. Record disagreements
between benchmark definitions and project policy definitions.

Verification: manually review each policy and fixture; test that benign and harmful
examples differ in intent/context rather than incidental keywords. Keep fixture
development independent of the sealed test set.

Gate: versioned policy registry, explicit allowed behavior, and test fixtures.

### T04 — Reproducible environment and local model checks

Create a dedicated uv-managed application environment with locked dependencies.
Do not modify the existing AgentAuditor environment or NeMo lockfile for this project.
Record Python, NeMo, PyTorch, CUDA/driver, inference engine, and model revisions.
Download/cache weights once using permitted cluster transfer methods.

Verification:

- Import all required packages and load NeMo configurations using the pinned version.
- Run a real GPU tensor operation and a tiny inference through the actual runtime.
- Verify model/tokenizer identity, correct chat template, output shape, and label map.
- Confirm no unexpected remote fallback; test local inference without network access
  after caching if the deployment is intended to be offline.
- Test representative long inputs and actual memory use; no silent truncation.

Gate: reproducible environment manifest and successful local inference. A CUDA
availability flag or successful model download alone is insufficient.

### T05 — Navigator API and billing preflight

Run on the same class of compute node and from the same environment as the planned
job. Do not assume login-node connectivity establishes compute-node connectivity.
Check each model and each API feature actually required by the next run.

| Check | Pass condition |
| --- | --- |
| Credentials | Loaded securely; never printed; intended account/team confirmed |
| Connectivity | DNS, TLS, and request timeout behavior work from compute node |
| Model access | Actual completion succeeds for the exact model ID, not just `/models` |
| Response | Nonempty final answer, valid expected schema, valid labels and finish reason |
| Capabilities | Required JSON mode, tools, reasoning controls, or other parameters work; unsupported options are rejected or deliberately removed |
| Task behavior | Small benign, violation, language, long-input, and structured-output examples parse correctly |
| Usage/cost | Billable usage reconciles with gateway accounting; remaining credit known |
| Limits | Modest concurrency test passes without sustained throttling |
| Failure handling | Mocked timeout, 401/403, 429, 5xx, empty output, and malformed JSON produce explicit errors |

Do not deliberately spend credit causing live failure cases; mock these in tests.
Before the next large run, repeat a minimal real completion per selected model.
Revalidate after credential, endpoint, model, environment, or node-class changes.
An API response can be structurally valid while semantically wrong: task evaluation
is a separate gate.

Gate: timestamped API health artifact bound to the run configuration and a known
spending limit. If usage accounting is missing, use a verified conservative bound
and sequential requests; do not start an unbounded batch.

### T06 — Rules and minimal NeMo integration

Implement deterministic rules, Presidio/custom recognizers, policy aggregation,
and custom actions before adding many models. NeMo's local classifier and Presidio
integrations are available, but configuration must match the pinned version. [S4]

Detector contract: policy ID, decision, optional score with its meaning, evidence
span/provenance, detector revision, and status. Keep decisions (`allow`, `redact`,
`block`) distinct from operational errors (`timeout`, `invalid_output`, `unavailable`).

Define precedence: authorization and prohibited disclosure cannot be bypassed by
an unrelated benign classifier. Scope exceptions to their policy/context; no
global allowlist that disables all checks. Redacted output must be revalidated.

For the initial deployment, a required security-check failure withholds the response
or tool execution and returns an explicit unavailable result. In evaluation this
remains an operational failure, not a correct security prediction. Test alternative
fallback behavior only as a separately named configuration. Use simulated tools and
synthetic secrets for adversarial tests; do not execute financial transactions or
send data to real attacker destinations.

Verification: offline unit tests and small integration tests cover each action,
rule boundary, label polarity, Unicode, error path, and block/redact/allow outcome.
Verify a blocked tool is never called, a blocked response never reaches the user,
and input-blocked cases do not accidentally invoke the target model.

Gate: fixtures pass and configuration loading is verified. Unit tests use mocks
and never call live providers; paid/live preflight is a separate explicit command.

### T07 — Scoring and experiment-runner correctness

Wrap official scorers where supplied. Implement policy metrics separately. Build
a tiny hand-calculated fixture including correct/incorrect predictions, refusals,
partial results, missing labels, and operational failures.

Verification:

- Reproduce expected confusion matrix, denominators, and task scores exactly.
- Join by stable IDs, never by file order; reject missing/duplicate predictions.
- Confirm label polarity and multi-label scoring with manual examples.
- Treat an explicit input block as an observed guard action; do not fabricate a
  generated response. Treat API failures as errors, not successful prevention.
- Count missing/error records and publish coverage; never silently drop them.
- Verify that changing input rails/redaction invalidates cached target responses.

Gate: scorer tests and runner accounting pass before model-quality comparisons.

### T08 — Train/calibrate only if needed

Run simple baselines, then the optional custom classifier. Use training data for
fitting and validation data for hyperparameters, thresholds, and model selection.
Use official splits when present; otherwise freeze group-aware splits before tuning.

Verification: no overlap of test IDs, conversations, or generated variants with
training/development. Inspect class balance, hard negatives, and per-language
metrics. Check calibration if scores drive decisions. Compare to the simple baseline.

Gate: frozen classifier artifact and decision record, or documented choice to
proceed without custom training. Never repeatedly tune against final test scores.

### T09 — Smoke run: roughly 20–50 development cases

Use a deliberately diverse fixture/sample covering each available category,
language, interaction surface, expected action, and one long input. Size is a
starting range, not sufficient coverage by itself.

Run the complete path: load -> check -> generate/tool if applicable -> output check
-> save -> score -> report. Inspect every smoke result manually.

Verification: all IDs accounted for, no operational errors, no unexpected empty
answers, correct rail activation, correct labels, persistent outputs, usage/cost
recorded, and blocked cases have the intended execution trace.

Gate: zero unexplained plumbing/scoring errors. Detection mistakes become explicit
development findings, not hidden exceptions.

### T10 — Pilot: roughly 200–500 development cases

Use a fixed stratified sample, or an appropriately sized subset if data is small.
Cover benign financial tasks as well as attacks. Measure throughput, p50/p95 latency,
peak VRAM/RAM, output size, API token usage, and retries at intended concurrency.

Verification: deliberately interrupt and resume a local test job. Confirm exactly
one final result per item, no corrupted shards, and cache/configuration isolation.
Audit a random sample plus disagreements and failures. Recompute metrics independently
on a small subset. Compare projected full-run cost/runtime/storage with allocation.

Gate: no unexplained missing or malformed records; predefined quality criteria met
or explicitly report the run as a baseline with known deficiencies. Operational
correctness must pass regardless of model quality.

### T11 — Freeze and run the full experiment

Freeze dataset/split hashes, policy/configuration hashes, model revisions, scorer,
prompts, thresholds, and generation settings. Finalize numeric success criteria
on development data before opening the held-out test set.

The experiment contract must name the maximum benign false-positive rate, maximum
acceptable utility drop, target attack-success reduction, latency/resource budget,
and uncertainty reporting method. Choose these values from the actual application
and development evidence; do not invent a universal acceptable security threshold.

Perform the launch checklist in Section 10. Run resumable shards sized from pilot
measurements, with checkpointing and budget-aware concurrency. Use CPU-only jobs
for API-only work; do not reserve an idle GPU while waiting on Navigator.

Verification: monitor initial shard, progress, error rates, throughput, storage,
and budget. Reconcile completed/error/pending counts periodically. Each shard must
validate its output before it is marked complete.

Gate: complete validated artifacts. An interrupted run is partial, not successful.
If changes are needed, create a new experiment version and label any test reuse.

### T12 — Independent audit and report

Recompute metrics from saved predictions; compare to the pipeline summary. Audit
stratified random records and all operational failures. Include false-positive,
missed-attack, language, and long-context error analyses.

Verification: every reported number traces to a run manifest and scorer revision;
table totals match records; claims match measured policy coverage. Review code
and test paths after formatting/linting, including security checks for input parsing,
untrusted content, external requests, and authorization.

Gate: reproducible report, limitations, model-choice rationale, and rerun instructions.

## 8. Evaluation design

Use two separate evaluations:

1. Detector performance on labeled inputs/outputs: precision, recall, F1, confusion
   matrices, and false positives by policy/language. AUROC/AUPRC only where meaningful
   continuous scores and labels exist; never invent scores for categorical outputs.
2. End-to-end assistant behavior: attack success, unauthorized disclosure/actions,
   legitimate-task performance, unnecessary refusals, latency, and cost.

Where applicable compare:

| Variant | Purpose |
| --- | --- |
| A: target with fixed system prompt, no rails | Baseline target behavior |
| B: same target/prompt + deterministic rails | Contribution of rules |
| C: B + pretrained detectors | Contribution of learned general detection |
| D: C + custom classifiers | Contribution of financial/domain adaptation |
| E: selected detector ablations | Identify useful/redundant components |

Keep all unrelated settings fixed. Predeclare whether a separate system-prompt-only
comparison is needed. Start with one target; use a second model family for a
bounded generalization check rather than multiplying every experimental dimension.

Attack success rate needs a task-specific definition and fixed denominator. Report
both absolute attack success and reduction from the unguarded baseline. For benign
tasks, a refusal is not a correct financial answer unless the official rubric says so.
Report operational failure rate and completed evaluation coverage separately, with
conservative sensitivity analysis when failed cases could change conclusions.

Use paired comparisons on the same items and confidence intervals, grouping by
conversation/source when cases are correlated. Small pilots cannot establish rare
failure rates. Zero observed failures is not proof of zero risk.

Use official gold labels/scorers first. If a judge model is necessary, lock its rubric,
hide experiment/model identities where practical, include random samples as well as
disagreements in human review, and report judge-human agreement. Judge inputs are
untrusted too. Do not use the deployed guard as the sole evaluation judge.

If the benchmarks lack indirect injection, tool permissions, or leakage cases,
create a separately reported supplementary suite. Synthetic cases require clear
provenance and held-out templates. Do not present them as official benchmark results.

## 9. Budget, retries, caching, and recovery

User-defined spending ceiling: $25/week. Plan at most $20; reserve $5 for retries
and uncertainty. Verify whether the credit and API key share the same account/team
budget, when it resets, and whether other users consume it. Do not infer this from
the public personal-credit policy or store only a per-process counter.

Planning rates checked against UF documentation on 2026-09-22:

| Navigator model | Input per 1M tokens | Output per 1M tokens |
| --- | ---: | ---: |
| gpt-oss-20b | $0.03 | $0.07 |
| gpt-oss-120b | $0.06 | $0.15 |
| llama-3.3-70b-instruct | $0.40 | $0.40 |

These are published rates, not verified billing for this account. [S13]
For example, 10,000 calls with 2,000 input and 500 billable output tokens each would
cost $1.95 on gpt-oss-120b at those rates. Actual reasoning tokens, retries, token
lengths, and accounting may change this estimate. Measure first.

Before dispatch, reserve estimated worst-case cost for each in-flight request using
validated token limits and rates. Reconcile with actual usage afterward. Include
all workers, experiments, and retries in a shared ledger. Reject launches whose
projected usage exceeds remaining allocation. A reset must not trigger an automatic
restart of an unfinished expensive run.

Retry policy: bounded exponential backoff with jitter for genuinely transient
timeouts, 429s, and selected 5xx errors. Start with at most three attempts per item.
Do not retry 401/403, invalid parameters, quota exhaustion, or consistent schema
errors indefinitely. A timed-out request may still be billed.

Pause new requests immediately on authentication, quota, persistent-storage, or
budget failures. As an initial operational rule, pause after five consecutive
transient failures or over 2% operational failures in a rolling 100-request window;
freeze any adjusted limits in the pilot manifest. Persist progress and diagnostics.

Cache keys include original content/context, model revision, prompts, generation
settings, policy configuration, preprocessing version, and code revision as relevant.
Never reuse responses across input transformations. Replaying stored outputs is
valid for some detector comparisons, not a substitute for live end-to-end validation.

Write per-shard results atomically, maintain stable IDs, and resume only unfinished
items. Preserve all attempts separately from the single selected final result.
Bound log volume and checkpoint retention; avoid millions of tiny files.

## 10. Mandatory checklist before a large run

Each item must have evidence or an explicit, justified not-applicable decision.

- [ ] Dataset identity, licensing, schemas, labels, splits, and hashes recorded.
- [ ] Test data sealed from training, prompt tuning, and threshold selection.
- [ ] Policies, examples, exceptions, enforcement, and scoring frozen.
- [ ] Code, dependencies, model/tokenizer revisions, and configuration pinned.
- [ ] Offline unit/integration tests and scorer fixtures pass.
- [ ] Current group byte/file quota supports estimated peak usage with headroom.
- [ ] Actual compute-node read/write/rename and persistent checkpoint tests pass.
- [ ] Correct GPU/VRAM and a real local inference confirmed for local-model jobs.
- [ ] Exact Navigator models return valid completions from the execution environment.
- [ ] Required API features, output parsing, usage accounting, and limits checked.
- [ ] Smoke outputs manually inspected; representative pilot completed.
- [ ] Resume/interruption, bounded retry, budget-stop, and error-state tests pass.
- [ ] Remaining weekly credit and full-run cost/runtime/storage estimates checked.
- [ ] Logs directory exists before SLURM submission; all directives precede commands.
- [ ] Credentials are available securely without appearing in logs or manifests.
- [ ] Run ID, result paths, shard IDs, and completion criteria are unambiguous.
- [ ] Small first shard will be inspected before remaining work is released.

The runner should enforce machine-checkable gates and exit nonzero with specific
reasons when they fail. Bind gate artifacts to configuration hashes; stale success
from a different model or environment does not authorize a new full run.

## 11. Deliverables and definition of done

Deliverables:

1. Source-linked policy registry and documented implementation gaps.
2. Dataset cards, loaders, official scorer adapters, and leakage audit.
3. Versioned NeMo configuration, rules, model adapters, and optional trained classifiers.
4. Offline tests, explicit live preflight, smoke/pilot runners, and resumable SLURM jobs.
5. Manifests, budget ledger, validated per-item outputs, and aggregate reports.
6. Model decision records with alternatives, measured evidence, licenses, and limitations.
7. Reproduction instructions from clean environment to final scores.

The project is complete when the agreed benchmark experiments are reproducible,
results are verified, costs are reconciled, known gaps are disclosed, and the core
guardrail pipeline works locally. It can be scientifically successful even if
results show limited benefit; accuracy must not be manufactured to meet expectations.

Immediate next work: receive datasets and documentation, settle task/scoring
contracts, verify storage/allocation and Navigator accounting, then build the
smallest rules-only pipeline and its scorer tests. Full runs come after the gates.

## 12. Sources and evidence boundaries

Public sources below were consulted during planning. Archive relevant versions at
implementation time because documentation, prices, model access, and policies change.
Source references support documented capabilities, not unmeasured project performance.

- **S1:** [Lakera defenses](https://docs.lakera.ai/docs/defenses).
- **S2:** [Lakera prompt defense](https://docs.lakera.ai/docs/prompt-defense).
- **S3:** [Lakera data leakage prevention](https://docs.lakera.ai/docs/data-leakage-prevention)
  and [agent behavior defense](https://docs.lakera.ai/docs/agent-behavior-defense).
- **S4:** [NeMo documentation](https://docs.nvidia.com/nemo/guardrails/home)
  and [documentation index](https://docs.nvidia.com/nemo/guardrails/llms.txt).
  Public Markdown retrieval failed during initial planning; the local repository's
  `docs/configure-rails/guardrail-catalog/community/hf-classifier.mdx`,
  `docs/configure-rails/guardrail-catalog/community/presidio.mdx`, and
  `docs/configure-rails/actions/creating-actions.mdx` supplied integration details.
- **S5:** [Qwen3-4B model card](https://huggingface.co/Qwen/Qwen3-4B).
- **S6:** [Qwen3Guard 0.6B](https://huggingface.co/Qwen/Qwen3Guard-Gen-0.6B)
  and [Qwen3Guard 4B](https://huggingface.co/Qwen/Qwen3Guard-Gen-4B).
- **S7:** [XLM-RoBERTa-base](https://huggingface.co/FacebookAI/xlm-roberta-base).
- **S8:** [Protect AI injection classifier](https://huggingface.co/protectai/deberta-v3-base-prompt-injection-v2).
- **S9:** [Official gpt-oss-120b documentation](https://developers.openai.com/api/docs/models/gpt-oss-120b).
- **S10:** [UF GPU access](https://docs.rc.ufl.edu/scheduler/gpu_access/).
- **S11:** [UF practical storage guidance](https://docs.rc.ufl.edu/quickstart/practical_storage/).
- **S12:** [Llama-3.3-70B model card](https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct).
- **S13:** UF Navigator [gpt-oss-20b](https://docs.ai.it.ufl.edu/docs/navigator_models/models/oai-gpt-oss-20b/),
  [gpt-oss-120b](https://docs.ai.it.ufl.edu/docs/navigator_models/models/oai-gpt-oss-120b/),
  and [Llama-3.3-70B](https://docs.ai.it.ufl.edu/docs/navigator_models/models/meta-llama-3.3-70b-instruct/)
  pricing; [catalog](https://docs.ai.it.ufl.edu/docs/navigator_models/).

No source establishes current account health, available storage, model performance
on the supplied datasets, or completed project validation. Those require the
recorded checks specified above.

## 13. Draft-document verification record

- Reviewed the supplied HiPerGator and Navigator reference notes without executing
  their embedded commands.
- Checked current public UF GPU/storage guidance and Navigator pricing, and used
  the model/documentation sources reviewed during this planning conversation.
- Reviewed task gates, evaluation denominators, leakage controls, budget arithmetic,
  error handling, and the distinction between reported access and verified access.
- Checked this new Markdown file for whitespace errors with Git's no-index check.
- Attempted the repository-required `uv run --locked pre-commit run --files
  FINANCIAL_GUARDRAILS_PROJECT_PLAN.md`; it could not run because `uv` is unavailable
  in this environment. Pre-commit validation remains outstanding.
- No application behavior or public documentation site was changed; no benchmark
  results, live API health, or cluster readiness are claimed by these document checks.
