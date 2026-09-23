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

Status: implementation passed locally on 2026-09-23 with 65 offline tests.
HiPerGator model execution and dataset-specific adapters remain externally gated.

- [x] Add versioned machine-readable policy configuration.
- [x] Add role-aware events and structured verdicts.
- [x] Add deterministic aggregation and detect/enforce modes.
- [x] Add retrieval, tool-call, tool-result, and output boundary checks.
- [x] Add agent permissions, resource scope, confirmations, and destructive-action denial.
- [x] Add optional pinned local-model interfaces and failure tests.
- [x] Add claim-level coverage, architecture, hook, and model documentation.
- [x] Add direct/NeMo equivalence and end-to-end smoke verification.
- [ ] Run selected model weights on `hpg-turin` and record measured memory, latency,
  and fixture quality. Requires HiPerGator access during execution.
- [ ] Build CNFinBench and FinVault adapters after the dataset files are supplied.
