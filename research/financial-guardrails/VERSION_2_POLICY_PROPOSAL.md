# Version 2 Policy Proposal

## Status and scope

This is a proposal and analysis plan. It does not modify Version 1 policies,
the selected model, the judge prompt, routing, or generation settings.

Team guidance received on 2026-10-14:

- Keep local `Qwen/Qwen3-8B-AWQ` and `rules_first_cascade` routing unchanged.
- Modify policies only.
- Count `require_confirmation` as an intervention that stops automatic execution
  pending human review.
- Prioritize attack-attempt F1 and AUPRC, while continuing to report false-
  positive rate and confirmation burden.

Version 1 remains frozen. Version 2 will be a separate experiment.

## Why Version 2 is needed

The Version 1 final result is strong on CNFinBench attack-attempt detection, but
FinVault is too conservative under its static normal/attack labels:

| FinVault attack-attempt result | Version 1 final |
| --- | ---: |
| Recall | 100.0% |
| F1 | 96.3% |
| Balanced accuracy | 50.0% |
| False-positive rate | 100.0% |

All normal-labeled final FinVault cases received an intervention. Four-fold
non-final cross-validation found the same pattern: attack-attempt FPR ranged
from 84.2% to 100.0%.

F1 alone is insufficient for this dataset because attack attempts are common.
Version 2 therefore treats F1 and AUPRC as primary selection metrics while
retaining FPR and confirmation burden as required operational safeguards.

## Evidence from non-final false-positive analysis

The development and calibration artifacts use older matched-policy telemetry,
so policy IDs can co-occur and cannot establish a unique causal rule. They are
useful for prioritization, not for blindly changing a rule.

| Split | False positives | Deterministic-rule interventions | Judge-only interventions | Most common matched policy | Most common first surface |
| --- | ---: | ---: | ---: | --- | --- |
| Development | 31 | 20 | 11 | `FINVAULT-TOOL-CONFIRM` (19) | Tool result (21) |
| Calibration | 16 | 11 | 5 | `FINVAULT-TOOL-CONFIRM` (9) | Tool result (9) |

The repeated tool-confirmation and tool-result patterns are the first review
targets. They do not prove that confirmation is incorrect: FinVault does not
provide trusted authorization or a later human-confirmation outcome for each
normal-labeled case.

Export the exact normal-labeled intervention candidates without benchmark
content before an authorized trace review:

```bash
uv run --locked python -m scripts.export_false_positive_review \
  outputs/<development-or-calibration-artifact>.json \
  --output outputs/<private-review-candidates>.json
```

The JSON contains only case IDs, decision-policy attribution, first detection
surface/turn, and whether the rule or judge intervened. It must remain outside
Git. Review the corresponding raw traces only in an authorized environment.

## Proposed policy work

### 1. Review confirmation candidates before relaxing them

Review a small authorized sample of normal-labeled false positives associated
with `FINVAULT-TOOL-CONFIRM`. For each case, determine whether the recorded
action is:

- clearly read-only or reversible and eligible for `allow`;
- a legitimate high-impact action where `require_confirmation` is appropriate;
- a dangerous action that should remain blocked or require confirmation; or
- ambiguous because the trace lacks trusted authorization context.

Only the first category is a candidate for policy relaxation. Ambiguous cases
must not be converted to `allow` merely to improve a benchmark score.

### 2. Review tool-result rules separately

Most observed first detections occur on tool results. Review the relevant
normal-labeled traces to distinguish genuine leakage/injection indicators from
benign financial data, routine system-like text, or URLs that trigger broad
patterns. Any adjustment must preserve:

- credential and payment-card protection;
- system-instruction protection;
- untrusted tool-result injection resistance; and
- local URL-policy enforcement.

### 3. Preserve hard safety boundaries

Version 2 will retain blocks for unknown tools, out-of-schema arguments,
explicitly denied tools, and activated dangerous bypass/override arguments
unless a case review identifies a concrete policy error. These protections are
not candidates for blanket relaxation.

### 4. Improve attribution before policy decisions

Run the existing content-free false-positive report on development and
calibration artifacts, then use current primary-policy telemetry for every
future Version 2 run. This separates the decision-producing policy from other
matched policies and prevents changes based on co-occurrence alone.

## What Version 2 will not change

- The local Qwen judge model.
- The LLM judge prompt or response schema.
- The `rules_first_cascade` routing mode.
- The dataset adapters, labels, source-group split assignment, or final Version
  1 artifacts.
- Hard blocks for explicit bypass/override arguments without documented review.

Outcome-stage score-only judging is not included in Version 2. The team requested
it as a separately labeled diagnostic for complete FinVault attack-success
AUROC/AUPRC; it retains Version 1 enforcement decisions and does not alter a
policy, model, prompt, routing mode, or Version 2 selection.

## Validation and decision gates

1. Document each proposed rule change, affected policy ID/tool, rationale, and
   expected security tradeoff.
2. Obtain team approval before editing a policy.
3. Add regression tests for every approved benign and malicious case pattern.
4. Evaluate only development and calibration splits while revising policies.
5. Select a Version 2 policy with pilot results using F1/AUPRC as primary
   metrics and FPR/confirmation burden as operational safeguards.
6. Freeze the approved Version 2 policy and run its final split once.
7. Compare Version 1 and Version 2 as separate experiments; do not overwrite
   Version 1 results.

## Decision needed before implementation

Approve the exact policy changes after the authorized case review. In
particular, a normal-labeled high-impact financial action should remain a
confirmation candidate unless the review establishes that it is safely
allowable without trusted confirmation.
