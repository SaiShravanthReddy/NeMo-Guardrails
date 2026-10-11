# Open Lakera / NeMo Guardrails: Version 1 Evaluation Summary

## Purpose

This project builds a zero-fee, Lakera-inspired security layer in an NVIDIA NeMo
Guardrails fork. It uses Lakera's public defense descriptions as requirements,
but does not call the commercial Lakera API and does not claim equivalence to
Lakera's proprietary service.

The goal is to understand where this Open Lakera/NeMo implementation can help a
financial agent and where it remains too disruptive or unreliable for real use.

## What was built

The implementation combines deterministic rules, a written-policy LLM judge,
custom Python actions, and NeMo Guardrails configuration/Colang flows. The same
policy engine can run directly or through NeMo.

| Defense area | Version 1 behavior |
| --- | --- |
| Prompt injection and jailbreaks | Detects direct injection/jailbreak patterns and treats retrieved text and tool results as untrusted. |
| Harmful content | Screens input and output against explicit harmful-content categories. |
| Data leakage | Detects PII, credentials, sensitive financial data, and system-instruction leakage; can block or sanitize. |
| Malicious links | Extracts and normalizes URLs and applies local domain rules. Proprietary reputation intelligence is not available. |
| Agent behavior | Screens tool descriptions, calls, arguments, and results; applies allow/deny/confirmation rules; rejects dangerous bypass arguments; prevents untrusted tool text from authorizing an action. |

Each check returns a structured verdict: `allow`, `block`, `sanitize`,
`require_confirmation`, or `log_only`, with policy IDs, risk category, and an
explicit detector-error state. Detector failures fail closed for high-impact
actions.

## Models and compute

| Component | Role |
| --- | --- |
| NeMo Guardrails | Guardrail configuration, Colang flows, and custom-action integration. |
| Deterministic Python policy engine | CPU-capable baseline for rules, PII/credential patterns, URLs, and tool controls. |
| `Qwen/Qwen3-8B-AWQ` | Local written-policy LLM judge served with vLLM on a HiPerGator L4 GPU. AWQ is weight quantization that reduces memory use for inference. |
| NaviGator `gpt-oss-120b` | Matched optional judge backend used during backend/mode pilot comparison. |
| HiPerGator `hpg-turin` | Local-Qwen evaluation hardware. |

The selected Version 1 configuration was local Qwen with
`rules_first_cascade`: deterministic rules run first and the judge is used when
rules have not already intervened. It was selected on the pilot split before the
final split was evaluated.

## Evaluation design

Evaluation is static replay: recorded conversations, tool calls, and tool
results are screened, but no tools are executed. Therefore, results measure
guardrail screening decisions and do not prove real-world attack prevention.

Two separate tasks are reported:

1. **Attack-attempt detection:** did the guardrail intervene on a known attack
   attempt? `block`, `sanitize`, and `require_confirmation` count as an
   intervention.
2. **Attack-success monitoring:** did output/tool-stage screening identify a
   trace associated with an attack outcome? This is distinct from detecting an
   attempted attack.

| Dataset | Attack-attempt label | Attack-success label |
| --- | --- | --- |
| CNFinBench pooled | Conversation ID begins with `harmful-` or `harmless-`. | Harmful conversation with HICS below 50 is positive; HICS above 50 is negative. |
| FinVault v5 fixed full | Source `case_type` is `attack` or `normal`. | Retained `attack_success` annotation. |

Source groups were deterministically split into 40% development, 20%
calibration, 20% pilot, and 20% final. The model, policies, prompts, and mode
were frozen before the one-time final evaluation. Risk scores are reported as
threshold-free ranking metrics; no score threshold was selected from the final
split.

## Final held-out results

These are results for the Open Lakera/NeMo implementation, not commercial
Lakera.

### Attack-attempt detection

| Dataset | Cases | Precision | Recall | F1 | Balanced accuracy | FPR | AUROC | AUPRC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| CNFinBench pooled | 128 | 90.9% | 93.8% | 92.3% | 92.2% | 9.4% | 93.8% | 93.8% |
| FinVault v5 fixed full | 223 | 92.8% | 100.0% | 96.3% | 50.0% | 100.0% | 61.3% | 94.5% |

### Attack-success monitoring

| Dataset | Cases | Precision | Recall | F1 | Balanced accuracy | FPR | AUROC/AUPRC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| CNFinBench pooled | 64 | 55.6% | 51.7% | 53.6% | 58.7% | 34.3% | 56.1% / 47.1% |
| FinVault v5 fixed full | 223 | 44.4% | 100.0% | 61.5% | 50.0% | 100.0% | unavailable |

### Reliability and latency

| Dataset | Completed cases | Detector errors | Judge calls | p50 latency | p95 latency | Provider cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| CNFinBench pooled | 128/128 | 0 | 3,050 | 52.607 s | 54.618 s | $0.00 |
| FinVault v5 fixed full | 223/223 | 0 | 1,992 | 13.444 s | 45.270 s | $0.00 |

Latency is measured per conversation after model setup; it excludes Slurm queue
time and model startup/loading.

## Four-fold robustness analysis

After the final result was frozen, four source-group-disjoint folds over the
remaining non-final 80% tested stability. These runs did not change the Version
1 configuration or final results.

| Dataset and task | Mean F1 | F1 range | Mean balanced accuracy | Mean FPR | Mean AUROC | Mean AUPRC |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| CNFinBench attack attempt | 86.8% | 80.3%–89.8% | 87.2% | 10.5% | 90.3% | 90.1% |
| CNFinBench attack success | 47.9% | 43.5%–51.5% | 53.1% | 42.1% | 52.7% | 45.9% |
| FinVault attack attempt | 94.5% | 92.3%–96.4% | 52.0% | 93.6% | 67.6% | 94.6% |
| FinVault attack success | 69.0% | 59.8%–74.2% | 51.2% | 95.5% | 55.3% | 60.5% |

## Main findings

- **CNFinBench:** Version 1 is a strong attack-attempt screen. Its held-out
  result and non-final folds both show high F1/balanced accuracy with a much
  lower false-positive rate than FinVault.
- **FinVault:** Version 1 catches every labeled attack attempt in the held-out
  final split, but it also intervenes on every normal final case. The high F1 is
  misleading here because attacks are common; balanced accuracy and FPR show
  that the configuration is too disruptive for deployment as-is.
- **Attack-success monitoring:** performance is close to chance on both
  datasets. Version 1 should not be treated as reliable post-attack recovery or
  outcome detection.
- **Reliability:** final runs had zero detector errors and complete
  attack-attempt risk-score coverage. Earlier malformed or transient LLM output
  failures were addressed with strict schema validation, bounded repair, retry
  handling for transient requests, and fail-closed behavior.

## Known limitations

- This is a Lakera-inspired open implementation, not commercial Lakera.
- Static replay does not execute tools, prove prevention, establish task utility,
  or show whether a confirmation request was appropriate.
- FinVault's normal/attack labels do not include trusted authorization or later
  confirmation outcomes. A confirmation request on a sensitive normal action may
  be appropriate safety friction rather than a true false positive.
- Local URL rules cannot reproduce a proprietary malicious-domain reputation
  service.
- Tool and authorization rules require human review before any production use.

## Reproducibility and next step

The full technical report is
[`PRIMARY_FINAL_EVALUATION_REPORT.md`](PRIMARY_FINAL_EVALUATION_REPORT.md).
The protocol is in [`EVALUATION_PROTOCOL.md`](EVALUATION_PROTOCOL.md), metrics
definitions are in [`METRICS.md`](METRICS.md), and the Lakera-to-policy mapping
is in [`policies/POLICY_MAPPING.md`](policies/POLICY_MAPPING.md).

The next step is a Version 2 proposal based on FinVault false-positive analysis.
Before changing confirmation policies, the team needs to decide whether a
confirmation request for a normal high-impact financial action is a false
positive or acceptable safety friction. Version 2 must be tuned on development
and calibration data only and evaluated as a separate experiment.
