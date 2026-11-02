# Version 1, Version 2, and Version 3 Comparison

## Purpose

This is the decision record for the Open Lakera/NeMo Guardrails research
implementation. It consolidates what changed in Versions 1–3, why each change
was made, what the evidence showed, and what may happen next.

It is deliberately conservative:

- Version 1 is the frozen historical baseline.
- Version 2 is an unselected policy-only candidate.
- Version 3 is a non-qualifying architecture-and-evaluation diagnostic.
- None of these results evaluate Lakera's commercial service.
- Static replay measures screening decisions over recorded traces; it does not
  prove real tool execution, human confirmation, or real-world prevention.

## Executive summary

| Version | Main question | Main change | Result | Decision |
| --- | --- | --- | --- | --- |
| V1 | Can a Lakera-inspired open guardrail detect financial-agent attacks? | Built deterministic policies, a policy-reading LLM judge, and NeMo integration. | Strong CNFinBench attempt screening; FinVault caught attacks but interrupted nearly every normal workflow. | Frozen baseline; not deployment-ready for FinVault. |
| V2 | Can narrow policy wording reduce FinVault friction? | Kept model/routing fixed and clarified four judge-policy areas. | Calibration FPR decreased, but recall/F1 fell, confirmation burden increased, and development reliability was incomplete. | Not selected. |
| V3 | Can threat detection be separated from action control to reduce FPR fundamentally? | Separated threat assessment from control action; added clean static input, schema-constrained judge, and outcome monitor. | Runtime was reliable, but intervention FPR remained 76.7% and threat FPR 67.1% across CV. | Non-qualifying diagnostic; do not run final holdout. |

The core lesson is that high attack recall alone is not enough. A financial
guardrail must also avoid stopping ordinary workflows. The main unresolved
problem is FinVault false-positive burden, not raw model availability or
runtime reliability.

## Shared project scope

### What the repository implements

The repository is an open, Lakera-inspired security layer inside an NVIDIA
NeMo Guardrails fork. Lakera's public descriptions informed the requirements;
the repository does not call, clone, or evaluate Lakera's proprietary service.

The shared policy engine evaluates user input, retrieved content, tool
descriptions, tool calls, tool results, and output. It can return `allow`,
`block`, `sanitize`, `require_confirmation`, or `log_only`, together with
policy IDs, risk category, audit telemetry, and explicit error states.

The implementation covers these public defense areas:

| Area | Open implementation behavior |
| --- | --- |
| Prompt injection and jailbreaks | Detects direct injection and jailbreak patterns; treats retrieval and tool text as untrusted. |
| Harmful content | Applies explicit harmful-content screening to relevant surfaces. |
| Data leakage | Detects PII, credentials, protected financial data, and system-instruction disclosure; may block or sanitize. |
| Malicious links | Normalizes URLs and applies local rules; proprietary reputation intelligence is unavailable. |
| Agent/tool behavior | Screens descriptions, calls, arguments, and results; applies allow, deny, confirmation, and hard-boundary rules. |

### Common evaluation limits

- Recorded benchmark tools are never executed.
- Dataset labels are used only after inference for scoring; they are not
  authorization facts for the guardrail.
- `require_confirmation` stops automatic execution, but static replay cannot
  establish whether a later human would approve it.
- FinVault and CNFinBench do not provide independent application-side records
  of authorization, confirmation, or execution.

## Data and labels

| Dataset | Attempt label | Attack-success label | Important limit |
| --- | --- | --- | --- |
| CNFinBench pooled | Conversation ID prefix: `harmful-` or `harmless-`. | Harmful conversation with HICS below 50 is positive; HICS above 50 is negative. | No application tool-execution record. |
| FinVault v5 fixed full | Source `case_type`: `attack` or `normal`. | Retained `attack_success` annotation. | Outcome annotation is not an independent execution log. |

For Version 1, source groups were deterministically split into 40%
development, 20% calibration, 20% pilot, and 20% final. Version 3 later
excluded source groups represented in its exploratory review packet; that left
405 non-final FinVault cases, including only 36 normal cases. Its four folds
therefore contain only 6–11 normal cases each, making FPR estimates uncertain.

## Version 1: baseline system and results

### Design

Version 1 combined:

- deterministic YAML/Python policies;
- a policy-reading LLM judge;
- custom NeMo actions and Colang flows that use the same shared engine as the
  evaluation runner;
- strict verdict validation, bounded output repair, bounded retry for
  retryable backend failures, and fail-closed handling for consequential
  errors; and
- content-free evaluation artifacts and telemetry.

The selected configuration was local `Qwen/Qwen3-8B-AWQ` on a HiPerGator L4
GPU using `rules_first_cascade`: deterministic rules intervene first, and the
judge considers events not already stopped by a rule. A matched pilot also
examined NaviGator `gpt-oss-120b`; local Qwen was selected for the frozen V1
configuration.

### Frozen final attack-attempt results

| Dataset | Cases | Precision | Recall | F1 | Balanced accuracy | FPR | AUROC | AUPRC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| CNFinBench pooled | 128 | 90.9% | 93.8% | 92.3% | 92.2% | 9.4% | 93.8% | 93.8% |
| FinVault v5 fixed full | 223 | 92.8% | 100.0% | 96.3% | 50.0% | 100.0% | 61.3% | 94.5% |

### Frozen final attack-success monitoring

| Dataset | Cases | Precision | Recall | F1 | Balanced accuracy | FPR | AUROC/AUPRC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| CNFinBench pooled | 64 | 55.6% | 51.7% | 53.6% | 58.7% | 34.3% | 56.1% / 47.1% |
| FinVault v5 fixed full | 223 | 44.4% | 100.0% | 61.5% | 50.0% | 100.0% | unavailable |

A separately labeled, unchanged score-only FinVault diagnostic later obtained
complete attack-success scores. Its AUROC was 55.2% and AUPRC 47.4% (223
cases), near chance. It confirms that V1 is not a reliable FinVault
attack-success monitor.

### Reliability and robustness

| Dataset | Completed | Detector errors | p50 latency | p95 latency |
| --- | ---: | ---: | ---: | ---: |
| CNFinBench pooled | 128/128 | 0 | 52.607 s | 54.618 s |
| FinVault v5 fixed full | 223/223 | 0 | 13.444 s | 45.270 s |

Non-final, source-group-disjoint CV showed the same difference between
datasets:

| Dataset and task | Mean F1 | Mean balanced accuracy | Mean FPR | Meaning |
| --- | ---: | ---: | ---: | --- |
| CNFinBench attempt | 86.8% | 87.2% | 10.5% | Strong screening evidence. |
| CNFinBench success | 47.9% | 53.1% | 42.1% | Weak outcome monitoring. |
| FinVault attempt | 94.5% | 52.0% | 93.6% | High recall but operationally excessive intervention. |
| FinVault success | 69.0% | 51.2% | 95.5% | High FPR; not reliable outcome monitoring. |

### What Version 1 established

- The system can run reliably and has useful CNFinBench attack-attempt
  screening behavior.
- FinVault's high F1 is misleading because the dataset is attack-heavy and the
  guardrail intervenes on many normal workflows.
- FinVault attack-success monitoring needs separate treatment.

### Important later qualification

The Version 3 input audit found raw benchmark identifiers and generator
annotations that could leak benchmark hints into earlier judge prompts. V1
results remain frozen historical results, but they are not a clean efficacy
baseline for V3 until Version 1 is rerun on the same `v3_clean` inputs and
reviewed-group exclusions.

## Version 2: narrow policy-only experiment

### Hypothesis and fixed components

Version 2 tested whether changing written policy instructions alone could lower
unnecessary FinVault interventions. It deliberately kept the model, routing,
schemas, dataset adapters, labels, hard tool boundaries, and Version 1
artifacts fixed.

The Version 2 judge policy clarified that:

1. routine tool-result wording is not automatically prompt injection;
2. read-only analysis and lookup may be allowed when no binding action,
   disclosure, bypass, or transaction occurs;
3. ordinary workflow values are not automatically data leaks; and
4. a tool deviation must be dangerous or unrelated to the trusted workflow.

Unknown tools, invalid arguments, dangerous bypass/override arguments,
unauthorized transfers, credential disclosure, and protected data disclosure
remained prohibited.

### Review evidence used for policy work

Content-free development and calibration false-positive analyses found
`FINVAULT-TOOL-CONFIRM` and tool-result surfaces repeatedly involved in normal
interventions. A private review aid categorized 31 development candidates as:

| Suggested category | Cases |
| --- | ---: |
| Allow candidate | 6 |
| Confirmation appropriate | 21 |
| Keep intervention | 3 |
| Ambiguous | 1 |

These were model-assisted review aids, not new ground-truth labels. Three
authorized trace reviews supported retaining confirmation/intervention for
high-impact payout actions.

### Results and decision

| Calibration metric | V1 | V2 | Change |
| --- | ---: | ---: | ---: |
| F1 | 95.1% | 90.6% | -4.6 points |
| AUPRC | 94.3% | 95.2% | +0.9 points |
| FPR | 88.9% | 77.8% | -11.1 points |
| Confirmation burden | 18/207 | 27/207 | +9 conversations |

V2 removed 20 V1 interventions and added none in the paired calibration
comparison (`p = 0.0004`, McNemar exact test). This was a real tradeoff, not a
clear improvement: it lowered FPR slightly but lost recall/F1 and increased
confirmation burden.

Its development run completed 413/415 cases and had two unknown-policy-ID
fail-closed errors. V2.1 replayed those two cases with an explicit instruction
to use configured policy IDs; both repeated the error. V2/V2.1 were therefore
ineligible for CV, pilot selection, and final evaluation.

### What Version 2 taught us

- Wording-only policy relaxation could reduce some interventions, but it did
  not solve the fundamental authorization/context problem.
- F1/AUPRC must be considered with FPR, coverage, detector errors, and
  confirmation burden.
- Repeated output-schema/policy-ID failures require enforced structure, not
  additional wording.

## Version 3: fundamental architecture experiment

### Why Version 3 differed from Version 2

V3 did not simply relax policies. It separated two previously conflated
questions:

```text
Threat assessment: is the observed request/action benign, suspicious, or malicious?
Control action:    should the system allow, sanitize, confirm, block, or log it?
```

A legitimate but consequential payout can therefore be `benign` while still
requiring confirmation. V3 reports threat-classification metrics and
operational intervention/confirmation burden separately.

### Design changes

| Area | Version 3 design |
| --- | --- |
| Deterministic controls | Retain strict checks for unknown/denied tools, invalid arguments, explicit bypasses, protected-data disclosure, and explicit unauthorized scope. Tool sensitivity alone is not an attack. |
| Authorization | Defines an optional trusted application-side interface for production. Static benchmark replay supplies no fabricated authorization facts. |
| LLM output | Uses provider JSON Schema, application validation, bounded repair, and fail-closed errors. |
| Attack success | Uses a separate trace-based outcome monitor; it does not reuse attempt decisions or labels as guardrail inputs. |
| Input privacy/validity | Uses `v3_clean` event IDs and cleaned tool results to remove known benchmark annotations and labels from prompts. |
| Evaluation | Uses source-group-aware CV, reviewed-group exclusion, telemetry matching, and separate threat/intervention tables. |

### Review and data-provenance limits

V3 assembled a private 60-case development review packet. The review covered
all 12 development source groups, so those groups were excluded from later
qualification evidence. The review audit found a blinding limitation in the
original packet: some benchmark hints remained. A corrected packet removed
identified hints, but it cannot undo original reviewer exposure.

The review is therefore useful for exploratory policy design, not independent
final evidence. It also leaves only 36 normal cases in the untouched non-final
pool. A new independent holdout or more normal, source-group-disjoint evidence
is required for a definitive selection claim.

### Current candidate and runtime evidence

The fresh candidate is commit `3cfc1c7f2`. It used local
`Qwen/Qwen3-8B-AWQ`, `rules_first_cascade`, static conversation-only
`v3_clean` inputs, and no benchmark labels or simulated outcome fields as
guardrail inputs.

All four non-final folds completed 405/405 cases with zero detector errors,
complete threat-score coverage, and matching logical-attempt/backend-call
telemetry. This establishes runtime reliability for the attack-attempt side of
the candidate; it does not establish candidate qualification.

### Version 3 CV results

#### Legacy intervention endpoint

This is the Version 1-compatible definition: `block`, `sanitize`, or
`require_confirmation` is a positive intervention.

| Fold | Cases | F1 | Balanced accuracy | FPR |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 60 | 86.6% | 80.6% | 16.7% |
| 1 | 119 | 92.8% | 47.7% | 100.0% |
| 2 | 118 | 91.7% | 50.8% | 90.0% |
| 3 | 108 | 94.1% | 48.5% | 100.0% |
| **Mean** | **405** | **91.3%** | **56.9%** | **76.7%** |

#### Version 3 threat-assessment endpoint

This is the new V3 classification definition: `suspicious` or `malicious` is
positive, independently of the selected control action.

| Fold | F1 | Balanced accuracy | FPR | AUROC | AUPRC |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 83.0% | 77.8% | 16.7% | 82.3% | 96.7% |
| 1 | 88.5% | 56.2% | 72.7% | 63.8% | 93.5% |
| 2 | 91.7% | 50.8% | 90.0% | 56.3% | 92.7% |
| 3 | 94.1% | 53.5% | 88.9% | 54.9% | 92.5% |
| **Mean** | **89.3%** | **59.6%** | **67.1%** | **64.3%** | **93.8%** |

The high AUPRC does not outweigh the high FPR. The remaining pool is heavily
attack-labeled, so AUPRC is aided by class prevalence. Operationally, the
guardrail still stops too many normal workflows.

#### Attack-success monitor

| Fold | Outcome-score coverage | F1 | AUROC | AUPRC |
| ---: | ---: | --- | --- | --- |
| 0 | 66.7% | unavailable | unavailable | unavailable |
| 1 | 31.1% | unavailable | unavailable | unavailable |
| 2 | 34.7% | unavailable | unavailable | unavailable |
| 3 | 15.7% | unavailable | unavailable | unavailable |

Many traces do not contain the output/tool-effect evidence needed by the
separate static outcome monitor. These values must be reported as unavailable;
they are not evidence that attacks were prevented or that the monitor is ready.

### Version 3 selection outcome

V3 did not satisfy its frozen qualification conditions:

- both the legacy intervention FPR and threat FPR exceed the 30% target;
- the fold-level paired FPR reductions were not statistically supported;
- normal-case/source-group denominators are small; and
- attack-success score coverage is incomplete.

The candidate is frozen as a **non-qualifying diagnostic**. It must not be
tuned repeatedly on the same folds or run on a new final holdout.

### Version 3 closure items

The following are correctness and provenance tasks for future candidates; they
do not modify the frozen V3 result:

1. Verify a matched V1 clean-input baseline before making an efficacy claim
   from V1/V3 paired comparisons.
2. Make each record's outcome-score mode agree with the artifact manifest.
3. Require code commit, reviewed-group checksum, and dataset/metadata
   checksums to match across all CV artifacts.
4. Enforce the written semantic rule that a policy/category mismatch gets one
   repair and then fails closed; do not silently normalize a mismatch while
   claiming semantic validation.
5. Add end-to-end tests proving that labels and known sidecar annotations do
   not enter threat or outcome prompts, and bound untrusted prior context.

## Comparison of the three decisions

| Decision area | V1 | V2 | V3 | Best lesson |
| --- | --- | --- | --- | --- |
| Primary response to FinVault FPR | General rules-first guardrail. | Narrow wording relaxation. | Separate threat from control and clean static evidence. | The next change must be structural and evidence-backed, not threshold tuning. |
| Model/routing | Local Qwen + rules-first cascade. | Unchanged. | Unchanged. | Preserve this control variable until a separate model study is justified. |
| Output reliability | Added strict validation, repair, retry, fail-closed behavior. | Unknown policy IDs persisted. | Provider schema and bounded preflight improved runtime reliability. | Structure should be enforced by schema/code, not only instructions. |
| Authorization | Tool rules inferred from trace context. | Still policy wording only. | Optional trusted-facts production contract; static replay uses no fabricated facts. | Real authorization/execution claims need application-side facts or an instrumented benchmark. |
| FinVault outcome monitoring | Weak / near chance. | Not changed. | Separate monitor, but insufficient static outcome evidence. | Keep outcome monitoring separate and report missing coverage honestly. |
| Status | Frozen baseline. | Rejected candidate. | Non-qualifying diagnostic. | Do not overwrite historical results or select a candidate from one attractive metric. |

## Recommended path forward

### Do now, locally

1. Preserve V1, V2, and V3 artifacts and update this document and the decision
   log whenever a verified decision is made.
2. Complete the V3 closure items above before trusting future artifact reports.
3. Produce a content-free false-positive taxonomy from the fresh V3 folds:
   policy, decision, surface, tool, and legitimate-workflow type.
4. Verify whether the V1 comparison uses identical `v3_clean` inputs and
   reviewed-group exclusions. If not, label it diagnostic and run one matched
   baseline replay before comparing efficacy.

### Before another HPG evaluation

1. Obtain more independent normal/high-impact financial workflows or create a
   separately registered instrumented benchmark. The existing 36 normal cases
   are insufficient to certify a 30% FPR.
2. Select exactly one fundamental hypothesis, based on false-positive evidence.
   For example: distinguish explicit unauthorized/dangerous actions from
   legitimate high-impact actions that require confirmation.
3. Preregister the new candidate's policy/code hashes, allowed data, metrics,
   source-group exclusions, and pass/fail rules. Keep model and routing fixed
   unless the team approves a separate model experiment.
4. Run local tests, then a 12–20 case HPG reliability gate, then grouped CV
   once. Run a new independent final holdout only if all gates pass.

## Document map

- [Version 1 Summary and Results](VERSION_1_SUMMARY_AND_RESULTS.md)
- [Version 2 Policy Proposal](VERSION_2_POLICY_PROPOSAL.md)
- [Version 2 Evaluation Report](VERSION_2_EVALUATION_REPORT.md)
- [Version 3 Design and Evaluation Protocol](VERSION_3_DESIGN_AND_EVALUATION_PROTOCOL.md)
- [Version 3 Protocol Amendment 1](VERSION_3_PROTOCOL_AMENDMENT_1.md)
- [Version 3 Protocol Amendment 2](VERSION_3_PROTOCOL_AMENDMENT_2.md)
- [Version 3 Review Audit](VERSION_3_REVIEW_AUDIT.md)
- [Version 3 Status and Next Steps](VERSION_3_STATUS_AND_NEXT_STEPS.md)
- [Evaluation Protocol](EVALUATION_PROTOCOL.md)
- [Metrics](METRICS.md)
- [Lakera-to-policy mapping](policies/POLICY_MAPPING.md)
