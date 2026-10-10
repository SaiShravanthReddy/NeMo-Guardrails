# Open Lakera / NeMo Guardrails: Team Update

## Goal

Build a zero-fee, Lakera-inspired guardrail layer in the NeMo Guardrails fork.
The implementation is based on Lakera's public defense descriptions; it does
not use the commercial Lakera API. This is an approximation, not a claim of
commercial Lakera equivalence.

## What is implemented

- A shared Python policy engine used directly and through NeMo Guardrails.
- NeMo configuration and Colang flows in [`config/`](config/).
- Role-aware events that separate trusted system/user instructions from
  untrusted retrieved text and tool results.
- Structured verdicts: `allow`, `block`, `sanitize`,
  `require_confirmation`, and `log_only`.
- Deterministic policies for prompt injection and jailbreaks, harmful content,
  PII/credentials/financial-data leakage, local URL rules, and risky tool use.
- A frozen FinVault tool policy that classifies recorded tool calls without
  executing them.
- Detect and enforce modes, audit metadata without raw secrets, deterministic
  decision precedence, and fail-closed detector errors.
- Static replay evaluation for CNFinBench and FinVault. Recorded tool calls are
  parsed and screened but never executed.

The written policy mappings are in
[`policies/POLICY_MAPPING.md`](policies/POLICY_MAPPING.md). The rules are in
[`policies/open_lakera_v1.yml`](policies/open_lakera_v1.yml), the LLM-judge
policy is in [`policies/llm_judge_v1.yml`](policies/llm_judge_v1.yml), and the
FinVault policy is in [`policies/finvault_tools_v1.yml`](policies/finvault_tools_v1.yml).

## Models, tools, and resources

| Component | Use |
| --- | --- |
| NeMo Guardrails | Configuration, Colang flows, and custom Python action integration. |
| Deterministic Python rules | Default CPU-capable guardrails; no model or API call is required. |
| NaviGator `gpt-oss-120b` | Optional policy-reading LLM judge, using the available weekly NaviGator credit. |
| `Qwen/Qwen3-8B-AWQ` | Optional local policy-reading LLM judge served with vLLM on HiPerGator. |
| HiPerGator `hpg-turin` L4 GPU | Local Qwen inference. CPU nodes run rules-only evaluation and NaviGator requests. |
| CNFinBench and FinVault v5 fixed | Static replay evaluation datasets. |

Both LLM backends receive the same written judge policy and return the same
structured verdict schema. The default profile remains rules-only.

## Verified deterministic baseline results

These are complete static-replay results for the Open Lakera/NeMo
implementation. They are not commercial Lakera results.

| Dataset | Cases | Detector errors | Accuracy | Precision | Recall | F1 | Specificity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| CNFinBench pooled | 642 | 0 | 66.4% | 45.4% | 21.3% | 28.9% | 87.8% |
| FinVault v5 fixed full | 1,043 | 0 | 67.9% | 63.8% | 85.7% | 73.2% | 49.2% |

The deterministic baseline is intentionally conservative on known rule
patterns. It has low CNFinBench recall and a high FinVault false-positive rate,
which motivates testing the LLM judge rather than tuning against the full sets.

## LLM-judge status

- Both backends pass safe/attack two-case preflights.
- Initial pilot runs exposed malformed structured judge responses. The judge
  now validates policy IDs and categories, uses bounded JSON repair, retries
  transient backend failures, and fails closed when a response remains invalid.
- The eight repaired 20% pilot artifacts (two datasets, two backends, and two
  judge modes) passed schema and metric-integrity validation. They are used for
  backend/mode selection only; they are not final held-out results.
- The confirmed protocol reports attack attempts and attack success separately.
  CNFinBench attempts use the harmful/harmless ID prefix and success uses
  harmful conversations with HICS below 50. FinVault uses its supplied attempt
  and `attack_success` annotations.
- Development uses 40% of source groups, with 20% each for calibration, pilot,
  and a one-time final split. Current development reliability work is resolving
  the remaining local-Qwen unknown-policy-ID cases before any final evaluation.

## Next steps

The primary final evaluation is complete. Its findings are in
[`PRIMARY_FINAL_EVALUATION_REPORT.md`](PRIMARY_FINAL_EVALUATION_REPORT.md): the
selected local-Qwen cascade configuration is strong on CNFinBench attack
attempts but intervenes on every FinVault final case, including every normal
case. This is reported as a real operational limitation, not hidden by F1.

The remaining planned analysis is source-group-disjoint four-fold cross-
validation on the non-final 80%. It is a robustness analysis only and cannot
change the frozen final result.
