# Version 3 Design and Evaluation Protocol

## Status

**Draft for preregistration.** The team approved the Version 3 direction on
2026-10-23. Runtime implementation and comparative evaluation must not begin
until the open selection tolerances in this document are confirmed and this
design is frozen.

Version 1 remains the selected baseline. Version 2 and Version 2.1 remain
rejected candidates and their results must not be overwritten.

## Objective

Version 3 addresses the principal Version 1 failure: FinVault attack-attempt
recall was 100%, but the final false-positive rate was also 100%. The goal is
to reduce false positives through authorization-aware decisions rather than
through dataset-specific score thresholds, repeated prompt tuning, or weaker
hard safety boundaries.

Version 3 keeps the selected local model and routing fixed:

- model: `Qwen/Qwen3-8B-AWQ` at the pinned repository revision;
- backend: local vLLM on HiPerGator;
- routing: `rules_first_cascade`; and
- benchmark adapters and source labels: unchanged unless a separately reviewed
  protocol amendment corrects a demonstrated label defect.

## Fundamental design change

### Separate threat assessment from control action

Earlier versions used an intervention (`block`, `sanitize`, or
`require_confirmation`) as the binary attack-attempt prediction. That conflates
two questions: whether an event is malicious and whether a legitimate but
high-impact action needs human approval.

Version 3 produces both:

```text
threat_assessment: benign | suspicious | malicious
control_action: allow | sanitize | require_confirmation | block | log_only
```

A legitimate payout can therefore be assessed as `benign` while its control
action remains `require_confirmation`. The confirmation still prevents
automatic execution, but it is reported as safety friction rather than a
malicious prediction.

For binary attack-attempt metrics, `suspicious` and `malicious` are positive;
`benign` is negative. Control-action counts and confirmation burden are
reported separately. A legacy intervention-as-prediction table is retained so
Version 3 can be compared transparently with Version 1, but it is not the
Version 3 threat-classification endpoint.

### Trusted authorization context

Tool authorization is evaluated against an immutable application-provided
context containing:

- the user's declared goal, recorded as user intent rather than inherently safe
  authority;
- allowed tools and operations;
- allowed resources and transaction limits;
- required prerequisites and their trusted completion state; and
- trusted event IDs that authorize a consequential action.

Retrieved text, tool descriptions, tool results, and model output remain
untrusted. They can provide evidence but cannot grant permission, expand scope,
change transaction limits, or mark a prerequisite complete without a trusted
application event.

The static FinVault replay does not contain every production authorization
field. Missing authorization must be represented explicitly; it must not be
inferred from the benchmark label or silently treated as approval.

### Narrow deterministic boundaries

Deterministic checks remain authoritative for conditions that do not require
semantic interpretation:

- unknown or denied tools;
- arguments absent from the declared schema;
- explicit bypass, override, or control-disabling arguments;
- unauthorized resource or recipient scope;
- credential, payment-card, protected account/routing, or system-instruction
  disclosure; and
- destructive privilege changes or transfers that violate an explicit limit.

Tool sensitivity alone is not evidence of an attack. Context-dependent calls
proceed to authorization assessment unless a hard boundary is triggered.

## LLM judge contracts

### Schema-constrained generation

The backend must use a provider-supported JSON Schema, not only JSON-object
mode. The schema enumerates every output field, decision, risk category, and
allowed policy ID. A bounded preflight must verify support in the pinned vLLM
version before the feature is used in evaluation.

Application validation then checks semantic relationships that JSON Schema
cannot establish, including whether the policy category matches the selected
policy and whether evidence supports the decision. A semantic failure receives
one repair attempt. A second failure becomes an explicit detector error and
fails closed. The system never retries until a convenient verdict appears.

### Separate attempt and outcome judgments

Attack-attempt assessment examines user intent, observed conversation context,
and proposed actions. Attack-success assessment examines the ordered output,
tool-call, and tool-result sequence and asks whether an unauthorized harmful
effect or disclosure occurred.

The outcome judge has its own schema, policy text, risk score, and error status.
It must not derive its prediction from the case-level intervention decision or
from the maximum attempt-risk score.

## Human-reviewed development evidence

Before policy implementation, create a stratified development-only review set
covering:

- normal read-only workflows;
- normal high-impact workflows;
- malicious tool deviations;
- untrusted tool-result instructions;
- explicit hard-boundary violations; and
- ambiguous traces with missing authorization context.

Reviewers label threat assessment and appropriate control action separately.
Model suggestions are review aids, not ground truth. Raw traces remain private
and outside Git; only aggregate, content-free review statistics may be committed.

## Evaluation protocol

### Reliability gate

Every candidate must demonstrate:

- 100% completed-case coverage;
- zero unresolved detector errors;
- complete attack-attempt and attack-success score coverage for eligible cases;
- exact logical-attempt/backend-call telemetry agreement; and
- no execution of recorded benchmark tool calls.

A bounded 12-to-20-case live gate is required before any larger HiPerGator run.

### Candidate evaluation

1. Register the candidate policy, code commit, model revision, schemas, and
   configuration hashes before inference.
2. Run grouped, source-disjoint four-fold validation over non-final data.
3. Report paired Version 1/Version 3 results for every fold.
4. Do not modify a candidate after viewing any fold result; a modification is a
   newly registered candidate.
5. Freeze at most one qualifying candidate.
6. Evaluate the frozen candidate once on a new independent holdout. Previously
   examined final data is diagnostic for Version 3 and cannot support a new
   definitive final claim.

### Required metrics

Report attack attempt and attack success separately:

- precision, recall, F1, balanced accuracy, and false-positive rate;
- AUROC and AUPRC when score coverage is complete;
- paired confidence intervals and fold means/ranges;
- coverage and detector errors;
- allow, sanitize, confirmation, block, and log-only counts;
- confirmation burden;
- p50 and p95 per-conversation latency; and
- tokens, backend calls, retries, and cost.

### Selection rule requiring final confirmation

The team has approved false-positive reduction as the primary Version 3 goal,
while preserving attack detection. Before implementation, confirm numerical
values for both of these preregistered constraints:

1. the minimum absolute and paired-significance reduction required in FinVault
   false-positive rate; and
2. the maximum permitted loss in attack recall, F1, and AUPRC.

Version 3 cannot be selected solely because one metric improves. It must pass
the reliability gate, preserve every hard boundary, meet the agreed FinVault
constraints, and avoid a material CNFinBench regression.

## Verification order

1. Unit-test threat/action independence and fail-closed schema validation.
2. Test authorization provenance and prove that untrusted content cannot grant
   authority.
3. Test safe, malicious, high-impact, missing-context, and ambiguous workflows.
4. Verify direct-engine and NeMo-action agreement.
5. Verify structured-output support with a small local vLLM preflight.
6. Run the bounded live reliability gate.
7. Run grouped cross-validation only after all earlier checks pass.

## Claims boundary

This is an Open Lakera/NeMo implementation informed by Lakera's public defense
descriptions. It is not commercial Lakera. Static replay measures classification
and pre-execution intervention behavior; it does not demonstrate real-world
attack prevention, successful human confirmation, recovery, or tool effects.
