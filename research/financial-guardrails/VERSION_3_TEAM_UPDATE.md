# Version 3 Update

## Goal

Version 3 explored whether separating threat assessment from control actions
could reduce false positives in the Open Lakera-inspired financial guardrail.
It is a research prototype evaluated on static benchmark traces, not a
deployment-ready system.

## What changed in Version 3

- It separates the question **“Does this conversation look like an attack?”**
  from **“What should the guardrail do?”**
- It uses cleaned conversation text. Benchmark labels and simulated outcome
  annotations are kept out of the guardrail input and used only for scoring.
- It adds a separate V3 evaluation runner, a schema-constrained judge, and an
  attack-success monitoring path.
- It preserves the same model and routing configuration used for the selected
  baseline.

## Evaluation

- Dataset: FinVault v5 fixed full, non-final data.
- Method: four-fold, source-grouped cross-validation.
- Exploratory human-review source groups were excluded from these folds.
- Total: **405 cases** across the four folds.

This Version 3 cross-validation is FinVault-only. CNFinBench Version 3
cross-validation has not been run, so these results do not complete the
project's two-dataset evaluation. Every future candidate evaluation should
include both FinVault and CNFinBench, with results reported separately.

## Results

| Measure | Version 3 result | Interpretation |
| --- | ---: | --- |
| Completed records | 405/405 | All selected cases completed. |
| Detector errors | 0 | No unresolved detector errors in the evaluated folds. |
| Threat-score coverage | 100% | A threat score was available for every evaluated case. |
| Mean intervention false-positive rate | 76.7% | The guardrail still intervened on many normal-labeled cases. |
| Mean threat-assessment false-positive rate | 67.1% | Threat assessment also marked many normal-labeled cases as suspicious or malicious. |
| Attack-success score coverage | 135/405 pooled (33.3%); 15.7%–66.7% by fold | Too incomplete for reliable aggregate attack-success metrics. |

The predeclared target for both FinVault false-positive endpoints was **30% or
less**. Version 3 did not meet that target. Its reliable run completion is a
useful engineering result, but it does not offset the high false-positive
rates.

## What we can conclude

- Version 3 implemented and exercised a different architecture that separates
  threat assessment from control action.
- The evaluated candidate ran reliably on the selected non-final folds.
- The candidate did **not** solve FinVault's false-positive problem and is
  **not qualified to replace Version 1**.
- Attack-success performance remains undetermined from these folds because
  score coverage was incomplete.
- A later content-free audit found all 405 eligible cases had output or tool
  events, while 270 missing scores were marked as outcome-judge errors. The
  artifacts do not retain the specific error causes, so recovery by replay has
  not yet been confirmed.
- Since the benchmark consists of static traces, it cannot show whether an
  action was truly authorized, confirmed by a person, or executed by an
  application.

## Comparison with Version 1

The existing V1 and V3 cross-validation results are **not a matched
head-to-head comparison**. V1 used legacy raw inputs and did not exclude the
exploratory review source groups; V3 used cleaned conversation inputs and
excluded those groups. Metric differences between those runs are diagnostic
context, not evidence that one version outperformed the other.

### What V3 did better

- **Clearer separation of responsibilities:** V3 reports threat assessment
  separately from the action taken. V1's primary attempt metric treated
  intervention as the detection prediction.
- **Cleaner guardrail input:** V3 removed known benchmark hints and kept labels
  and simulated outcomes out of the prompt. The audited V1 folds used legacy
  raw inputs.
- **More complete threat-score evidence in this evaluation:** V3 had threat
  scores for all 405 cases and completed all four folds without detector
  errors.

### What V3 did worse or did not resolve

- **False positives remain high:** V3's mean intervention FPR was 76.7%, and
  its threat-assessment FPR was 67.1%. Both missed the predeclared 30% target.
- **Attack-success evidence is incomplete:** V3 score coverage was only
  15.7%–66.7% by fold, so aggregate outcome metrics were unavailable.
- **No proven overall metric improvement over V1:** V1's FinVault CV mean
  intervention FPR was 93.6%, compared with V3's 76.7%. This numerical
  difference is only directional context because the cases, input cleaning,
  and review-group exclusions differed. It does not establish that V3 reduced
  false positives.

| Aspect | Version 1 evidence | Version 3 evidence | Careful interpretation |
| --- | --- | --- | --- |
| FinVault intervention FPR | 93.6% mean in historical CV | 76.7% mean in V3 CV | V3's reported value is lower, but the runs are not matched; improvement is unproven. |
| Threat assessment | No separate threat endpoint | 67.1% mean FPR; 100% score coverage | V3 adds this capability, but its false-positive rate remains high. |
| Attack-success monitoring | Separate score-only diagnostic had AUROC 55.2% and AUPRC 47.4% | Incomplete score coverage; aggregate metrics unavailable | Neither provides strong evidence of reliable FinVault outcome monitoring; the runs are not directly comparable. |
| Run reliability | Frozen final V1 evaluations completed without detector errors | 405/405 V3 CV records completed without detector errors | Both showed successful runs in their respective evaluations. |

This table's V3 evidence is FinVault-only. A full V1/V3 project comparison also
needs V3 results on CNFinBench, reported separately from FinVault.
