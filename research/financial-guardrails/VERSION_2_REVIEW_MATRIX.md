# Version 2 false-positive review matrix

## Purpose

This matrix converts the completed Version 1 development/calibration
false-positive analysis into a controlled review plan. It does not change a
policy. A matched policy ID can co-occur with another detector's decision, so
the counts below identify review priorities rather than causal attribution.

Review only the private, authorized FinVault traces corresponding to the
content-free candidate lists. Do not add raw prompts, tool results, customer
data, or secrets to this repository.

| Review target | Development candidates | Calibration candidates | Evidence | Permitted next step |
| --- | ---: | ---: | --- | --- |
| `FINVAULT-TOOL-CONFIRM` | 19 | 9 | Repeated matched policy in both splits | Classify each action as read-only/reversible, high-impact confirmation, unsafe, or ambiguous. Relax only verified read-only/reversible actions. |
| Tool-result first detections | 21 | 9 | Most common detection surface in both splits | Determine whether text represents real leakage/injection or benign financial/system-like content before changing DLP or injection rules. |
| `DLP-FINANCIAL` and `DLP-SYSTEM` | 9 / 9 | 6 / 5 | Repeated co-occurrence on normal-labeled cases | Preserve credential/payment-card/system protection; consider a narrowly scoped exception only when the exact benign context is verified. |
| `TOOL-DEVIATION` / `TOOL-PERMISSION` | 12 / 6 | 4 / 3 | Repeated co-occurrence on tool-related cases | Verify that the FinVault tool schema and expected sequence were represented correctly. Do not allow unknown tools or out-of-schema arguments. |
| Judge-only interventions | 11 | 5 | Intervention source without deterministic rule | Record the policy/evidence category during trace review. The judge prompt, model, and routing remain frozen. |

## Required classification for each reviewed case

Use one of these outcomes for every candidate:

1. **Allow candidate:** clearly read-only or reversible and no protected-data,
   injection, authorization, or transfer concern is present.
2. **Confirmation appropriate:** a legitimate high-impact action where automatic
   execution would be unsafe without trusted confirmation.
3. **Keep intervention:** the trace contains a real policy concern.
4. **Ambiguous:** the static trace lacks enough authorization or execution
   context to make a safe policy change.

Only outcome 1 can justify a Version 2 relaxation. Outcomes 2–4 remain an
intervention for evaluation and must not be converted to `allow` to improve a
benchmark score.

## Content-free worksheet workflow

Prepare a private worksheet from either candidate list:

```bash
uv run --locked python -m scripts.manage_false_positive_review prepare \
  outputs/<private-review-candidates>.json \
  --output outputs/<private-review-worksheet>.json
```

An authorized reviewer classifies each row using only the four outcomes above
and one fixed basis code. The worksheet deliberately has no free-text field, so
raw FinVault content cannot be entered accidentally. Validate the completed
worksheet before drafting a change list:

```bash
uv run --locked python -m scripts.manage_false_positive_review validate \
  outputs/<private-review-worksheet>.json
```

## Decision gate

Before editing a Version 2 policy, record the exact policy/tool/argument,
candidate case IDs, review classifications, expected change, security tradeoff,
and regression tests. Team approval is required for that change list. Version 1
artifacts, the selected Qwen model, the judge policy, and `rules_first_cascade`
routing remain frozen.
