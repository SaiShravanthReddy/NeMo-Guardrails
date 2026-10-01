# Personal TODO

## 1. Create the Lakera-inspired NeMo guardrails file

- [x] Deliver a reviewed, runnable NeMo guardrails configuration implementing the
  selected policies derived from Lakera's public documentation.

Status: passed locally on 2026-09-22. The smoke check, 31 focused tests, and
repository pre-commit validation pass.

Interpretation: a NeMo configuration with a source-linked policy mapping. The entry
file will be `config.yml`; custom detectors may also need Python actions, prompts,
and Colang files. A single YAML file is not enough to implement every defense.
This is an independent implementation, not Lakera's proprietary product.

### Prerequisites, in order

1. [x] Choose the first version's scope: text input/output checks and, if the
   application invokes tools, checks before tool execution. List deferred defenses.
   Verify: each selected defense has a defined place in the application.
2. [x] Write the policy mapping from Lakera documentation to intended behavior:
   allowed examples, violations, exceptions, and allow/redact/block actions.
   Keep financial application rules separate from Lakera-derived requirements.
   Verify: review each policy against its source and a benign counterexample.
3. [x] Pin the NeMo version and choose the integration engine. Decide which checks
   use built-in rails and which need custom actions or application-level checks.
   Verify: a minimal configuration loads and the intended checks actually execute.
4. [x] Select only the detectors required for the first version and confirm their
   language coverage, licenses, dependencies, and hardware needs.
   Verify: each selected detector produces valid results on small local fixtures.
   Check Navigator only if this configuration uses it; check `hpg-turin` and storage
   before running local GPU detectors there.
5. [x] Prepare small offline test fixtures for allowed requests, blocked requests,
   redaction, malformed/empty detector output, and detector failure.
   Verify: expected decisions are reviewed independently of detector predictions.

### Completion checks

- [x] Configuration and supporting files are implemented with source-linked policies.
- [x] Benign and violating fixtures produce the intended decisions.
- [x] Invalid detector output cannot silently allow a request; skipped rails are detected.
- [x] Tool checks prevent execution when blocked, if tools are in scope.
- [x] Setup instructions state model requirements, limitations, and deferred policies.
- [x] Validation results are recorded in `VALIDATION.md` and the work is committed
  as a focused checkpoint.

CNFinBench and FinVault data are not prerequisites for a first configuration.
They are needed later for benchmark adapters, calibration, and performance claims.
Full benchmark runs and transformer fine-tuning are not prerequisites for this task.

## Maintenance

Keep completed tasks checked, add new tasks below the existing tasks, and record
actual blockers without marking unperformed verification as passed.

## 2. Expand the baseline into Open Lakera

Status: implementation passed locally on 2026-10-01 with 88 offline tests.
The supplied datasets passed local readability, checksum, schema, and record-count
checks. Dataset adapters are implemented; live HiPerGator model execution remains pending.

- [x] Add versioned machine-readable policy configuration.
- [x] Add role-aware events and structured verdicts.
- [x] Add deterministic aggregation and detect/enforce modes.
- [x] Add retrieval, tool-call, tool-result, and output boundary checks.
- [x] Add agent permissions, resource scope, confirmations, and destructive-action denial.
- [x] Add optional pinned local-model interfaces and failure tests.
- [x] Add claim-level coverage, architecture, hook, and model documentation.
- [x] Add direct/NeMo equivalence and end-to-end smoke verification.
- [x] Receive and inspect `cnfinbench-pooled` (642 records) and
  `finvault-v5-fixed-full` (1,043 records), including their metadata sidecars.
- [x] Keep benchmark data outside Git and verify that local copies match the
  HiPerGator SHA-256 checksums.
- [x] Add daily fork synchronization for `develop` and this research branch, with
  tests required before the research branch is pushed.
- [x] Add a provider-independent LLM-judge prompt, written policy, structured
  response validation, timeout, malformed-response handling, and fail-closed tests.
- [x] Verify that the same optional judge detector runs through direct and NeMo paths.
- [x] Build and validate CNFinBench and FinVault adapters over every supplied record,
  preserving FinVault tool calls and tool results.
- [x] Add failure-aware binary metrics that require an explicit positive label.
- [x] Verify from the source converters that label `1` means unsafe in both supplied
  exports and document the FinVault outcome-versus-interception mismatch.
- [x] Add an application hook for screening untrusted tool descriptions.
- [x] Define two LLM-judge conditions: judge every applicable interaction and judge
  only cases unresolved by deterministic rules.
- [x] Define two separately reported FinVault tasks: completed-outcome safety and
  runtime malicious-attempt interception.
- [ ] Confirm whether the required LLM judge will run locally on HiPerGator or
  through Navigator, and confirm the judge model and policy rubric with the team.
- [ ] Implement and validate the selected live judge backend without logging raw
  benchmark content or sending sensitive data to an unapproved service.
- [ ] Run selected model weights on `hpg-turin` and record measured memory, latency,
  and fixture quality. Requires HiPerGator access during execution.
- [ ] Convert preserved FinVault action strings into validated tool names and
  arguments only after the static-replay versus interactive-protocol decision.
- [ ] Define leakage-safe development, calibration, and final evaluation splits.
- [ ] Add result manifests, checkpointing, latency measurements, and resource usage
  to the evaluation runner.
- [ ] Run CPU and API/GPU preflight checks, then a small stratified pilot. Review
  outputs before approving a full benchmark run.
- [ ] Run the approved full evaluations and produce a reproducible aggregate report.
