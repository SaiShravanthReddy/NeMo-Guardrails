# Version 3 Status and Next Steps

## Current status

Version 3 is implemented and its current candidate has completed non-final
four-fold cross-validation on FinVault. CNFinBench Version 3 cross-validation
jobs have been submitted for both Version 2 and Version 3 and are currently
running; their outputs are not yet verified. Until they finish and pass
artifact checks, the two-dataset evaluation is incomplete. The FinVault result
is a useful diagnostic, but it is **not a qualifying replacement for Version
1** and must not be evaluated on the held-out final split.

The evaluated candidate is commit `3cfc1c7f2`. It used static, cleaned
conversation inputs only: benchmark labels, attack-success annotations, and
simulated outcome fields were evaluator-only and were not supplied to the
guardrail.

## What is complete

- Separate Version 3 runner, schema-constrained judge, threat/control split,
  and static-trace outcome monitor.
- Static-input boundary checks and a small live HPG preflight gate.
- Fresh non-final grouped CV: 405/405 records completed, with zero detector
  errors, complete threat-score coverage, and matching judge-attempt/backend
  call telemetry.
- Dataset coverage: FinVault CV is complete. Four-fold CNFinBench V2 and V3
  jobs are running; evaluate their artifacts separately after they finish.
  Every candidate evaluation should cover both datasets and report them
  separately.
- Content-free review packet and reviewed-source-group exclusion. The review
  is exploratory development evidence; it is not independent final evidence.

## Result and decision

The candidate did not meet the predeclared false-positive objective:

| Endpoint | Mean FPR across folds | Decision |
| --- | ---: | --- |
| Legacy intervention | 76.7% | Does not meet the <=30% target |
| Version 3 threat assessment | 67.1% | Does not meet the <=30% target |

Attack-success score coverage was 135/405 pooled (33.3%; 15.7% to 66.7% by
fold), so attack-success F1, AUROC, and AUPRC are unavailable. A later
content-free audit found that all 405 eligible cases had output or tool events;
the 270 missing scores were marked as outcome-judge errors, not absent event
evidence. The artifacts do not retain the specific error causes, so replay
recovery remains unconfirmed. Static traces also do not establish real
authorization, confirmation, or execution.

Therefore:

1. Freeze these artifacts as a **non-qualifying Version 3 diagnostic**.
2. Do not tune thresholds, prompts, or policies against these same CV folds.
3. Do not run the final held-out split for this candidate.

## Required closure and correctness work

These tasks do not change the frozen candidate or its result. A future run
after any behavioral change is a new candidate.

1. **Verified from the supplied HPG audit:** the V1 CV folds use legacy raw
   input and have no reviewed-group checksum, while V3 uses `v3_clean` and
   excludes reviewed groups. Existing V1/V3 comparisons are diagnostic. Since
   V3 fails its gates, a matched V1 replay is not needed for the current report
   unless the team requests a direct efficacy comparison.
2. **Fixed locally after the evaluated run:** V3 record builders now set
   `score_all_outcome_events`, and artifact/checkpoint validation rejects a
   score-mode mismatch. The supplied HPG audit confirmed all 405 final V3
   records have `enforcement_only` while their manifests say
   `score_all_outcome_events`. This affects metadata consistency, not the
   recorded metric calculations.
3. **Fixed locally after the evaluated run:** CV reporting now requires equal
   code commit, reviewed-group checksum, and dataset/metadata checksums across
   folds. The supplied HPG audit confirmed the four final V3 folds match on
   commit `3cfc1c7f2`, reviewed-group checksum, dataset hash, and metadata hash.
4. Restore the agreed judge contract: a policy/category mismatch receives one
   repair attempt and then fails closed. Do not silently normalize a model
   mismatch while claiming semantic validation.
5. Add end-to-end tests showing all known labels and sidecar annotations are
   absent from both threat and outcome prompts. Bound untrusted prior-context
   length for cost, privacy, and prompt-injection resilience.

## Pre-report audit progress

The following documentation and integrity work was completed after the V3
folds. It does not alter or replace the evaluated candidate at commit
`3cfc1c7f2` or its recorded metrics.

| Item | Status | Evidence |
| --- | --- | --- |
| Team-report audit caveats | Added to the V1/V2/V3 comparison reports. | Commit `cd29ec05a`; pre-commit passed. |
| V3 record/manifest outcome-score mode | Fixed in current code; artifact and checkpoint validators reject mismatches. | Commit `ab0694b21`; 19 focused tests and pre-commit passed. |
| CV fold provenance | Reporter now requires matching code, reviewed-group, dataset, and metadata hashes. | Commit `a3bb06821`; 8 focused tests and pre-commit passed. |
| Historical HPG artifact manifests | Audited from the supplied content-free output. | V1/V3 inputs are not matched; final V3 folds share provenance; all 405 final V3 records mismatch their manifest score mode. |
| V3 outcome-score coverage causes | Audited from four final FinVault V3 artifacts. | 135/405 scores present; 270 missing scores flagged as outcome-judge errors; zero cases lacked outcome events; error causes unavailable. |
| Policy/category mismatch behavior | Disclosed as a mismatch with the frozen one-repair-then-fail-closed contract. | Do not claim this behavior is implemented for the evaluated candidate. |
| Human-review blinding | Disclosed as limited by the original packet defect. | The corrected packet cannot undo earlier exposure; review remains exploratory evidence. |

## Best path to the next candidate

1. Produce a content-free false-positive taxonomy from the fresh CV artifacts:
   decision, policy, surface, tool, and legitimate-workflow category.
2. Select one fundamental policy/authorization hypothesis from that evidence.
   Do not use threshold tuning or change the fixed model/routing configuration.
3. Obtain more independent, source-group-disjoint normal/high-impact workflows
   or define a separate instrumented benchmark. Only 36 normal cases remain in
   the current non-final pool, which is insufficient to certify a 30% FPR.
4. If further manual review is needed, use a fresh blinded two-reviewer packet
   and documented adjudication; do not reuse the exploratory review as final
   evidence.
5. Preregister the next candidate (for example, Version 3.1): exact policy
   change, hashes, allowed data, evaluation split, and pass/fail gates.
6. Run local tests, then a small HPG reliability gate, then one grouped-CV
   evaluation. Use the held-out final split only if every preregistered gate
   passes.

## HPG decision

The four-fold CNFinBench V2 and V3 jobs have already been submitted. Do not
submit duplicates. After they finish, validate each artifact's fold membership,
coverage, detector errors, score coverage, and telemetry; keep dataset and
version results separate. Do not run the held-out final split. Any new
candidate must pass a small reliability gate before grouped CV.
