# Policy Selection Protocol

## Purpose

This protocol prevents iterative policy tuning against a held-out result. It
applies to Version 2 and later policy-only variants of Open Lakera. The model,
routing, datasets, labels, source-group assignment, and enforcement semantics
remain those in [EVALUATION_PROTOCOL.md](EVALUATION_PROTOCOL.md).

The final split is never used for policy selection.

## Fixed configuration

Every candidate uses:

- local `Qwen/Qwen3-8B-AWQ` on a HiPerGator L4 GPU;
- `rules_first_cascade` routing;
- the same deterministic rules, tool policies, and judge response schema; and
- a versioned judge policy file recorded by SHA-256 in the evaluation artifact.

Only the written judge policy may differ between candidates.

## Candidate registration

Before a candidate is evaluated, record its policy path, SHA-256, intended
change, and regression tests in the candidate table below. A candidate cannot
be edited after any evaluation result is examined. An edit creates a new
candidate with a new version and SHA-256.

| Candidate | Policy | Status | Intended change |
| --- | --- | --- | --- |
| V1 baseline | `policies/llm_judge_v1.yml` | Eligible baseline | Frozen baseline |
| V2 | `policies/llm_judge_v2.yml` | Ineligible | Narrow clarification of benign financial workflow context; development artifact had two detector errors |
| V2.1 | `policies/llm_judge_v2_1.yml` | Ineligible | V2 plus exact policy-ID output clarification; the two-case gate again had two unknown-policy-ID errors |

## Evaluation sequence

1. Run a small preflight sample for each candidate. It must have complete
   scoring and no detector errors.
2. Evaluate four deterministic, source-group-disjoint folds over the non-final
   80% pool. This reuses the development, calibration, and already-observed
   pilot partitions for policy selection while preserving the final 20% as the
   only untouched policy-evaluation holdout.
3. For every fold, report attack-attempt F1, AUPRC, false-positive rate,
   confirmation burden, coverage, detector errors, and latency. Report
   attack-success monitoring separately; it is not used to select an
   attack-attempt policy.
4. Report unweighted fold means and ranges. Do not tune a candidate between
   folds or after examining a fold result.
5. Freeze at most one eligible candidate after cross-validation and evaluate it
   once on the untouched final partition.

## Reliability gate

A candidate is ineligible for policy selection if any evaluated fold has:

- incomplete completed-case coverage;
- an unrepaired detector error;
- incomplete attack-attempt risk-score coverage; or
- unmatched logical judge-attempt and backend-call telemetry.

Fail-closed behavior remains correct for enforcement, but an artifact with a
detector error cannot establish comparative performance.

## Selection rule

Version 1 is retained unless a candidate satisfies every condition below over
the four-fold non-final validation summary:

1. passes the reliability gate in every fold;
2. has mean attack-attempt F1 at least as high as Version 1;
3. has mean attack-attempt AUPRC at least as high as Version 1; and
4. does not weaken a documented hard safety boundary.

When multiple candidates meet all conditions, select the one with the higher
mean F1. If mean F1 is exactly tied, select the one with the higher mean AUPRC.
If both are tied, select the lower mean false-positive rate; then the lower
confirmation burden.

False-positive rate and confirmation burden are required operational reporting
metrics. They break a genuine F1/AUPRC tie but cannot justify replacing Version
1 when either primary metric is lower.

## Current status

The current V2 calibration artifact is complete, but it lowers F1 relative to
V1. Its development artifact has two fail-closed unknown-policy-ID errors.
V2.1 repeated those same two errors in its two-case reliability gate despite an
explicit output-contract clarification. Neither candidate is eligible for
four-fold selection or final advancement. Version 1 remains the selected
baseline unless a separately registered candidate clears every gate.

## Reporting

Publish the candidate table, fold-level results, fold summary, selected policy
SHA-256, and the unchanged final evaluation protocol. Label all results as
performance of the Open Lakera/NeMo implementation, not commercial Lakera.
