# Evaluation metrics and retained fields

Every expensive inference is retained as one content-free `EvaluationRecord`. This
lets reports select metrics later without repeating NaviGator calls or local GPU
inference. Records contain identifiers, labels, decisions, risk scores, all matched
policy IDs, the policy IDs from the primary decision-producing verdict, categories,
surfaces, timing, token usage, estimated cost, GPU measurements, detector failures,
retry counts, judge/rules routing, detection turns, and declared slice values. They
never contain prompts, conversations, model responses, secrets, or evidence
excerpts.

## Separate evaluation tasks

Each artifact contains three explicit task bundles in addition to the legacy
top-level metrics, which remain the attack-attempt metrics for compatibility:

- `attack_attempt` evaluates the benchmark unsafe/malicious label against any
  guardrail intervention.
- `attack_success` evaluates the confirmed dataset-specific outcome annotation
  against an intervention derived only from output, tool-call, and tool-result
  surfaces: FinVault's `attack_success`, or CNFinBench harmful-conversation HICS
  below 50.
- `attack_success_for_attempted_attacks` is the same outcome task restricted to
  records whose benchmark label indicates an attempted attack.

For attack-attempt detection, `block`, `sanitize`, and
`require_confirmation` count as interventions under the agreed protocol. Every
report also shows the action distribution separately: automatic interventions
(`block + sanitize`), confirmation requests, allows, and audit-only decisions.
This prevents a legitimate high-impact banking action that appropriately pauses
for confirmation from being interpreted as equivalent to an automatic block.

CNFinBench harmless conversations and harmful conversations with HICS exactly 50
have no attack-success label and are marked unavailable rather than treated as
false. FinVault normal and attack conversations retain their supplied outcome label.
For every task bundle, missing outcome predictions caused by outcome-stage detector
errors remain failures and reduce coverage; they are never converted to allow.

## Metrics implemented now

### Classification

- Confusion matrix: true positive, true negative, false positive, and false negative.
- Total, completed, failures, and completed-case coverage.
- Accuracy, precision, recall, specificity, positive F1, and negative F1.
- False-positive, false-negative, false-discovery, and false-omission rates.
- Negative predictive value, balanced accuracy, and Matthews correlation coefficient.

### Ranking and threshold analysis

These require the LLM judge's `risk_score`, which is an unsafe-risk ranking score
rather than a calibrated probability.

- AUROC and AUPRC.
- Normalized partial AUROC through 5% false-positive rate.
- Recall at 1% and 5% false-positive rates.
- Precision at 90% recall.
- Precision among the highest-scoring 10% of cases.
- Complete ROC/precision-recall operating points and class prevalence.

The implemented AUPRC is the step-wise average-precision integral. Rules-only runs
without continuous scores retain classification metrics but do not fabricate ranking
scores.

Each attack-attempt and attack-success task bundle reports `risk_score_coverage`.
AUROC, AUPRC, and threshold-derived ranking metrics are withheld unless coverage is
complete for every eligible, completed record in that task. This prevents a failed
or malformed judge response from silently changing the population used for a
ranking result.

### Calibration

- Brier score and log loss.
- Expected and maximum calibration error.
- Ten-bin reliability data containing bin counts, mean scores, and positive rates.

Calibration numbers can be computed for diagnosis, but the judge score must not be
called a probability until calibration is fitted on a development split and checked
on held-out data.

### Operations and cost

- Decision, risk-category, policy, and surface counts, including automatic
  intervention and confirmation-burden rates.
- Judge invocation and deterministic-rule intervention rates.
- Detector errors, backend failures, and retries.
- Judge-invoked conversations, logical judge attempts, repair attempts, observed
  backend calls, and a check that logical attempts match observed call telemetry.
- p50, p90, p95, and p99 latency; p50 and p95 time to first token when available.
- Input/output tokens, NaviGator estimated cost, and cost per true positive.
- Peak GPU memory, total GPU seconds, and cases per minute.
- Dangerous actions observed, detections before execution, and their rate when turn
  annotations exist.
- Annotation coverage and rates for attack success, legitimate-task completion,
  sanitization correctness, authorization correctness, confirmation appropriateness,
  unauthorized disclosure, and unauthorized action. Missing annotations stay
  unavailable and are never treated as false.

The shared NaviGator/local backend emits content-free latency, token, estimated-cost,
and failure telemetry. The current non-streaming client cannot measure time to first
token, so that field remains empty unless a later streaming runner supplies it.

Per-conversation latency starts after the backend is configured and ends after one
case's messages have been screened. It includes rule evaluation, judge calls, and
bounded judge-output repair attempts for that case. It excludes scheduler queueing,
model startup, model loading, and unrelated batch work. Render p50/p95 from one or
more artifacts with:

```bash
uv run --locked python -m scripts.report_latency outputs/<artifact>.json
```

Render all protocol-defined result tables from one or more artifacts without
repeating inference:

```bash
uv run --locked python -m scripts.report_evaluation outputs/<artifact>.json
```

Print the stored bootstrap confidence intervals for attack-attempt metrics:

```bash
uv run --locked python -m scripts.report_confidence_intervals outputs/<artifact>.json
```

The command reports only intervals already computed in the artifact. It never
reruns inference, and unavailable intervals remain unavailable rather than being
estimated from a different population.

Use retained development-set scores to print candidate attack-attempt thresholds
under fixed false-positive-rate caps:

```bash
uv run --locked python -m scripts.report_risk_thresholds outputs/<development-artifact>.json
```

This report is retrospective and does not alter stored verdicts. Choose a
candidate only from development data, validate it on calibration data, and never
use the final split to select a threshold.

### Slices, uncertainty, and comparisons

- The full metric bundle can be recomputed for any recorded slice, such as risk
  type, scenario, ambiguity, language, surface, conversation length, or outcome.
- Seeded percentile bootstrap confidence intervals cover accuracy, precision,
  recall, specificity, F1, balanced accuracy, MCC, AUROC, and AUPRC. Grouped
  resampling is supported for correlated variants.
- Paired configurations report agreement, Cohen's kappa, benign/unsafe disagreement,
  unique detections, policy/category agreement, risk-score Pearson and Spearman
  correlation, metric deltas, and exact McNemar testing.

## Reproducibility artifacts

Each completed run is written atomically as a validated `EvaluationArtifact`. Its
manifest fixes dataset and metadata hashes, record count, code commit, policy hashes,
backend/model/revision, judge mode, positive label, threshold, generation settings,
software versions, hardware, and token prices. The artifact contains case records,
aggregate metrics, confidence intervals, and optional slice metrics.

## Metrics requiring additional ground truth

The record structure can retain the annotations needed for later analyses, but the
following cannot be inferred responsibly from the supplied static labels:

- Sanitization correctness or retained utility requires expected redacted spans or
  human review.
- Legitimate-task completion and answer quality require task-specific reference
  answers or a separately validated evaluator.
- True attack prevention, unauthorized-action prevention, and attack-success
  reduction require an interactive environment or verified execution outcomes.
- Confirmation appropriateness and authorization correctness require trusted
  identity, permission, and confirmation annotations.
- Fairness or language comparisons require reliable demographic/language metadata
  and sufficient sample sizes.

These metrics must remain unavailable rather than be replaced with proxy labels.
