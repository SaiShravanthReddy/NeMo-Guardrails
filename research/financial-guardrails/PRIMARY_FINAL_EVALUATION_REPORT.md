# Primary final evaluation report

## Scope

This report is the one-time final-split evaluation of the selected Open Lakera
configuration: local `Qwen/Qwen3-8B-AWQ` on HiPerGator with
`rules_first_cascade`. It evaluates the Open Lakera/NeMo implementation, not
commercial Lakera. Recorded conversations and tool traces were statically
screened; no tool was executed.

The configuration was selected from the frozen 20% pilot split. Policies,
prompts, model, and mode were then held fixed for the final 20% source-group-
disjoint split. Primary predictions are the guardrail's policy decisions:
`block`, `sanitize`, and `require_confirmation` count as interventions. Risk
scores are reported only as threshold-free ranking metrics.

## Validated artifacts

The final artifacts are stored outside Git on HiPerGator:

- `outputs/finvault-v5-fixed-full-final-hipergator-rules_first_cascade-b9896cd5bb58.json`
- `outputs/cnfinbench-pooled-final-hipergator-rules_first_cascade-bdbf909d6a7b.json`

Both completed every assigned case, had zero detector errors, retained complete
attack-attempt risk-score coverage, and had exact logical-judge-attempt/backend-
call telemetry matches.

## Attack-attempt detection

| Dataset | Cases | Precision | Recall | F1 | Balanced accuracy | FPR | AUROC | AUPRC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| CNFinBench pooled | 128 | 90.9% | 93.8% | 92.3% | 92.2% | 9.4% | 93.8% | 93.8% |
| FinVault v5 fixed full | 223 | 92.8% | 100.0% | 96.3% | 50.0% | 100.0% | 61.3% | 94.5% |

The CNFinBench result has bootstrap 95% confidence intervals of 86.9–96.8%
for F1 and 86.9–96.8% for balanced accuracy. The FinVault result has a 94.3–
97.9% F1 interval, but its balanced-accuracy interval is exactly 50.0% because
the configuration intervened on every final FinVault case. F1 alone would be
misleading for FinVault because attack attempts are prevalent in that split.

## Attack-success monitoring

| Dataset | Cases | Precision | Recall | F1 | Balanced accuracy | FPR | AUROC/AUPRC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| CNFinBench pooled | 64 | 55.6% | 51.7% | 53.6% | 58.7% | 34.3% | 56.1% / 47.1% |
| FinVault v5 fixed full | 223 | 44.4% | 100.0% | 61.5% | 50.0% | 100.0% | unavailable |

For FinVault attempted attacks only, attack-success F1 is 64.7%, with a 100%
FPR. Its ranking metrics are unavailable because outcome-stage score coverage
is not complete; they are intentionally not estimated from a smaller subset.

## Operational results

| Dataset | Detector errors | Judge calls | Repairs | p50 latency | p95 latency | Estimated provider cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| CNFinBench pooled | 0 | 3,050 | 3 | 52.607 s | 54.618 s | $0.00 |
| FinVault v5 fixed full | 0 | 1,992 | 0 | 13.444 s | 45.270 s | $0.00 |

The local Qwen model ran on HiPerGator L4 GPUs. Latency is per conversation and
excludes scheduler queueing and model startup.

## Interpretation

The selected guardrail is effective on CNFinBench attack attempts: it has high
recall with a comparatively low false-positive rate. Its attack-success
monitoring is substantially weaker, so a detected input attack should not be
treated as proof that a harmful outcome was detected or recovered.

On FinVault, the configuration is highly conservative. It catches every labeled
attack attempt but intervenes on every labeled normal case. This is a material
deployment shortcoming for a financial workflow: the guardrail may be safe but
too disruptive to normal operations. The final action mix was 96.4% automatic
blocks and 3.6% confirmation requests, with no allows. The supplied static
labels do not establish whether each sensitive financial action was authorized,
so they cannot determine whether a confirmation request would have been
appropriate in production.

## Limits and next work

- Static replay measures screening decisions, not real tool execution or actual
  attack prevention.
- The project does not claim equivalence to Lakera or evaluation of Lakera's
  commercial service.
- CNFinBench and FinVault use different task constructions; results must remain
  separate rather than averaged into one score.
- The planned four-fold cross-validation over the non-final 80% is a robustness
  analysis only. It cannot alter this frozen final result.
