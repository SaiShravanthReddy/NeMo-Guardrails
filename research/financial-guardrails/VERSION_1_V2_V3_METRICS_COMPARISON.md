# Version 1, Version 2, and Version 3 Metrics Comparison

## How to read this document

This document compares the measured outcomes of the three versions of the
Open Lakera/NeMo Guardrails research implementation. It is not a single
leaderboard: the versions used different splits, input views, and endpoints.
Rows are directly comparable only when they have the same dataset, case IDs,
input view, labels, and endpoint.

| Label | Meaning |
| --- | --- |
| **Frozen final** | One-time held-out Version 1 result. Historical baseline; not available for new tuning. |
| **Non-final CV** | Source-group-disjoint cross-validation used for development evidence. |
| **Calibration diagnostic** | Non-final result used to examine a candidate; not eligible for selection when a required gate fails. |
| **Unavailable** | The task lacks complete eligible predictions or required ground truth. It must not be treated as zero. |

## Metric definitions used here

### Attack-attempt endpoints

| Endpoint | Positive prediction | Purpose |
| --- | --- | --- |
| Legacy intervention | `block`, `sanitize`, or `require_confirmation` | Matches Version 1's operational intervention definition. |
| V3 threat assessment | `suspicious` or `malicious` | Separates "is this an attack?" from "should this high-impact action pause?" |

The V3 threat endpoint is not directly comparable with Version 1 F1/FPR because
Version 1 did not produce a separate threat label. V3 therefore reports both
endpoints.

### Primary quantities

| Metric | What it answers | Important caveat |
| --- | --- | --- |
| Precision | Of interventions/predicted threats, how many were attack-labeled? | Can be high while many attacks are missed. |
| Recall | Of attack-labeled cases, how many were caught? | Can be high by stopping nearly everything. |
| F1 | Balance of precision and recall. | Does not fully expose normal-workflow burden in attack-heavy data. |
| Balanced accuracy | Average of sensitivity and specificity. | More informative than raw accuracy under class imbalance. |
| FPR | Fraction of normal-labeled cases stopped/predicted risky. | Main FinVault operational problem. |
| AUROC/AUPRC | Quality of continuous risk-score ranking. | Reported only with complete score coverage; AUPRC is influenced by attack prevalence. |
| Coverage/errors | Whether every intended case finished without unresolved detector error. | Required before a candidate can be selected. |

## Comparability matrix

| Comparison | Directly comparable? | Reason |
| --- | --- | --- |
| V1 CNFinBench final vs V1 FinVault final | No | Different datasets and class distributions. |
| V1 FinVault final vs V2 calibration | No | Final versus calibration split. |
| V1 FinVault CV vs V2 calibration | Partly diagnostic | Same task family, but not necessarily the same cases/input view. |
| V1 historical results vs V3 CV | No efficacy claim yet | V3 uses `v3_clean` inputs and reviewed-group exclusion; earlier V1 artifacts may use raw inputs with benchmark hints. |
| Matched V1/V3 clean-input rerun on identical IDs | Yes | This is the required paired efficacy comparison. |
| V3 legacy intervention vs V3 threat endpoint | No single aggregate | They answer operational stopping and threat classification, respectively. |
| Attack attempt vs attack success | No | They are separate labels and separate questions. |

## Version 1 metrics

### Frozen held-out attack-attempt results

| Dataset | Cases | Precision | Recall | F1 | Balanced accuracy | FPR | AUROC | AUPRC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| CNFinBench pooled | 128 | 90.9% | 93.8% | 92.3% | 92.2% | 9.4% | 93.8% | 93.8% |
| FinVault v5 fixed full | 223 | 92.8% | 100.0% | 96.3% | 50.0% | 100.0% | 61.3% | 94.5% |

Interpretation: CNFinBench shows strong attack-attempt screening. FinVault's
100% recall is not operationally acceptable because every normal-labeled final
case was also stopped, producing a 100% FPR and 50% balanced accuracy.

### Frozen held-out attack-success monitoring

| Dataset | Cases | Precision | Recall | F1 | Balanced accuracy | FPR | AUROC | AUPRC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| CNFinBench pooled | 64 | 55.6% | 51.7% | 53.6% | 58.7% | 34.3% | 56.1% | 47.1% |
| FinVault v5 fixed full | 223 | 44.4% | 100.0% | 61.5% | 50.0% | 100.0% | unavailable | unavailable |

The separate FinVault score-only diagnostic supplied full outcome-score
coverage without changing enforcement: AUROC 55.2% and AUPRC 47.4% across 223
cases. These near-chance ranking results are diagnostic, not a new Version 1
enforcement result.

### Version 1 non-final CV context

| Dataset and task | Mean F1 | F1 range | Mean balanced accuracy | Mean FPR | Mean AUROC | Mean AUPRC |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| CNFinBench attempt | 86.8% | 80.3%–89.8% | 87.2% | 10.5% | 90.3% | 90.1% |
| CNFinBench success | 47.9% | 43.5%–51.5% | 53.1% | 42.1% | 52.7% | 45.9% |
| FinVault attempt | 94.5% | 92.3%–96.4% | 52.0% | 93.6% | 67.6% | 94.6% |
| FinVault success | 69.0% | 59.8%–74.2% | 51.2% | 95.5% | 55.3% | 60.5% |

These are historical context. They must not be used as a clean V3 baseline
until Version 1 is recomputed on the exact V3-clean case IDs and exclusions.

### Version 1 reliability and latency

| Dataset | Completed | Detector errors | Judge calls | p50 latency | p95 latency |
| --- | ---: | ---: | ---: | ---: | ---: |
| CNFinBench pooled | 128/128 | 0 | 3,050 | 52.607 s | 54.618 s |
| FinVault v5 fixed full | 223/223 | 0 | 1,992 | 13.444 s | 45.270 s |

Latency is per conversation after backend configuration; it excludes Slurm
queue time and model startup/loading.

## Version 2 metrics

Version 2 changed only written judge policy instructions. It retained the V1
model, routing, rules, response schema, labels, and hard safety boundaries.

### Calibration comparison

| FinVault legacy intervention metric | V1 calibration | V2 calibration | V2 minus V1 |
| --- | ---: | ---: | ---: |
| Completed cases | 207/207 | 207/207 | 0 |
| F1 | 95.1% | 90.6% | -4.6 points |
| AUPRC | 94.3% | 95.2% | +0.9 points |
| FPR | 88.9% | 77.8% | -11.1 points |
| Confirmation burden | 18/207 (8.7%) | 27/207 (13.0%) | +9 conversations |
| Detector errors | 0 | 0 | 0 |

The paired calibration decision comparison removed 20 V1 interventions and
added none (`p = 0.0004`, McNemar exact test). The candidate still was not
selected: F1/recall fell and confirmation burden rose.

### Reliability failure

| Split/candidate | Completed | Detector errors | Selection status |
| --- | ---: | ---: | --- |
| V2 development | 413/415 | 2 unknown-policy-ID errors | Ineligible |
| V2.1 two-case repair gate | 0/2 successful | 2 repeated unknown-policy-ID errors | Ineligible |

V2 never advanced to fresh CV or a final split. Its calibration metrics are a
tradeoff diagnostic, not evidence of a selected improvement.

## Version 3 metrics

Version 3 uses `v3_clean` conversation-only static inputs and reviewed-group
exclusion. It measures both the legacy intervention endpoint and the new
threat-assessment endpoint.

### Runtime reliability

| CV cases | Completed | Detector errors | Threat-score coverage | Telemetry match |
| ---: | ---: | ---: | ---: | --- |
| 405 | 405/405 | 0 | 100.0% | True |

This establishes a reliable attack-attempt runtime path for this candidate. It
does not make the candidate operationally acceptable.

### Legacy intervention endpoint

| Fold | Cases | F1 | Balanced accuracy | FPR |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 60 | 86.6% | 80.6% | 16.7% |
| 1 | 119 | 92.8% | 47.7% | 100.0% |
| 2 | 118 | 91.7% | 50.8% | 90.0% |
| 3 | 108 | 94.1% | 48.5% | 100.0% |
| **Unweighted mean** | **405 total** | **91.3%** | **56.9%** | **76.7%** |

### Version 3 threat-assessment endpoint

| Fold | F1 | Balanced accuracy | FPR | AUROC | AUPRC |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 83.0% | 77.8% | 16.7% | 82.3% | 96.7% |
| 1 | 88.5% | 56.2% | 72.7% | 63.8% | 93.5% |
| 2 | 91.7% | 50.8% | 90.0% | 56.3% | 92.7% |
| 3 | 94.1% | 53.5% | 88.9% | 54.9% | 92.5% |
| **Unweighted mean** | **89.3%** | **59.6%** | **67.1%** | **64.3%** | **93.8%** |

The threat FPR falls below the legacy intervention FPR because V3 can mark a
high-impact normal action as benign while still requiring confirmation. This is
useful semantic separation, but it is not sufficient operational improvement:
the threat FPR is still high and the legacy intervention FPR remains high.

### Version 3 attack-success monitor

| Fold | Score coverage | F1 | AUROC | AUPRC | Interpretation |
| ---: | ---: | --- | --- | --- | --- |
| 0 | 66.7% | unavailable | unavailable | unavailable | Incomplete trace outcome evidence. |
| 1 | 31.1% | unavailable | unavailable | unavailable | Incomplete trace outcome evidence. |
| 2 | 34.7% | unavailable | unavailable | unavailable | Incomplete trace outcome evidence. |
| 3 | 15.7% | unavailable | unavailable | unavailable | Incomplete trace outcome evidence. |

Because outcome score coverage is incomplete, metrics are correctly withheld.
Static traces cannot establish actual execution or recovery even with complete
coverage.

## Selection-gate scorecard for Version 3

| Requirement | Required value | Current evidence | Status |
| --- | --- | --- | --- |
| Legacy intervention FPR | <=30% | 76.7% mean | Fail |
| Threat FPR | <=30% | 67.1% mean | Fail |
| Paired FPR reduction | >=30 points versus matched clean V1 | Not established; current historical comparison is diagnostic | Not met |
| Paired group-level significance | `p < 0.05` | Fold reports: `p = 1.0` | Fail |
| Legacy intervention recall | >=90%; within 5 points of matched V1 | Not established against matched clean V1 | Not qualified |
| Legacy intervention F1 | No more than 2 points below matched V1 | Not established against matched clean V1 | Not qualified |
| Threat-score coverage | 100% | 100% | Pass |
| Attack-success score coverage | Complete eligible coverage | 15.7%–66.7% by fold | Fail for outcome task |
| Detector errors / telemetry | Zero errors; exact match | 0; exact match | Pass |

Version 3 is therefore a non-qualifying diagnostic. The correct action is not
to lower the gate after observing this result or to tune repeatedly against the
same folds.

## What can and cannot be concluded

| Statement | Supported? | Reason |
| --- | --- | --- |
| V1 is effective for CNFinBench attempt screening. | Yes, with static-replay limits. | Strong frozen final and CV metrics with low FPR. |
| V1 has excessive FinVault normal-workflow friction. | Yes. | Final and CV legacy intervention FPR are near 100%. |
| V2 improved FinVault overall. | No. | It traded lower FPR for lower F1/recall, higher confirmation burden, and failed reliability gates. |
| V3 runtime is more reliable than V2. | Yes for the evaluated attempt path. | 405/405 completed, zero detector errors, matching telemetry. |
| V3 solved FinVault FPR. | No. | Mean legacy FPR is 76.7%; threat FPR is 67.1%. |
| V3 has strong attack-success monitoring. | No. | Outcome-score coverage is incomplete; metrics are unavailable. |
| V3 is ready for a new final holdout. | No. | It fails frozen FPR and outcome-coverage requirements. |
| High V3 AUPRC alone proves operational usefulness. | No. | The pool is attack-heavy and FPR remains high. |

## Required reporting language

Use language such as:

> Version 3 improved the architecture and achieved reliable conversation-only
> attack-attempt inference, but did not meet its predeclared FinVault
> false-positive criteria. It remains non-final development evidence and does
> not support a deployment or final-holdout claim.

Avoid language such as:

> Version 3 is better than Version 1.

That statement requires a verified, matched V1 clean-input baseline and every
predeclared selection gate to pass.

## Next metric work

1. Verify or obtain a matched V1 rerun on identical `v3_clean` inputs and
   reviewed-group exclusions before making a paired efficacy claim.
2. Fix V3 artifact and report provenance invariants before producing future
   selection reports.
3. Expand independent normal/high-impact evidence; the current 36 normal cases
   cannot estimate or certify a low FPR precisely.
4. Keep attack-success separate. Mark it unavailable when static outcome
   evidence is absent; do not fabricate scores or infer execution.
5. For the next preregistered candidate, preserve the two FPR endpoints,
   coverage/error gates, and matched group-level comparison.

## Related documents

- [Version 1, Version 2, and Version 3 Comparison](VERSION_1_V2_V3_COMPARISON.md)
- [Version 1 Summary and Results](VERSION_1_SUMMARY_AND_RESULTS.md)
- [Version 2 Evaluation Report](VERSION_2_EVALUATION_REPORT.md)
- [Version 3 Design and Evaluation Protocol](VERSION_3_DESIGN_AND_EVALUATION_PROTOCOL.md)
- [Version 3 Status and Next Steps](VERSION_3_STATUS_AND_NEXT_STEPS.md)
- [Metrics](METRICS.md)
