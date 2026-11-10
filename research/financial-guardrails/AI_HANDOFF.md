# AI Handoff: Open Lakera Financial Guardrails

**Last updated:** 2026-11-09
**Repository:** `NeMo-Guardrails` fork, active research branch `research/financial-guardrails-plan`
**Scope:** the research application in `research/financial-guardrails/`, not a complete technical inventory of every NeMo Guardrails package feature.

## Start here

This file is the concise project handoff. Before changing code, also read the
repository-root `AGENTS.md` and `AI_POLICY.md`; they control contribution,
privacy, validation, and AI-assisted work. The research branch has owner approval
for focused signed-off commits and pushes within this project; do not open a PR
without an explicit request. Never commit private datasets, raw traces, credentials,
or unvalidated run artifacts.

Use this source order when documents disagree:

1. `EVALUATION_PROTOCOL.md`, `METRICS.md`, and the versioned protocol amendments
for definitions and frozen evaluation rules.
2. Validated evaluation artifacts and their manifests for exact run-level facts.
3. The latest per-fold/aggregate reports derived from those artifacts.
4. This handoff for current status and navigation.
5. Older plans, README summaries, and team updates only as historical context.

Several project documents predate the current evaluation state. In particular,
`README.md` still describes the early pilot, `PLAN.md` is an initial planning
document, `VERSION_2_EVALUATION_REPORT.md` still labels itself “In progress,” and
parts of `VERSION_3_STATUS_AND_NEXT_STEPS.md` describe an earlier incomplete
outcome-scoring state. Do not repeat those status statements without checking
this handoff and the latest artifacts.

## Goal and research question

Build and evaluate an open, **Lakera-inspired** security layer implemented with
NeMo Guardrails, deterministic policies, and a local LLM judge. The goal is to
understand where the guardrail detects attempted attacks and successful harmful
outcomes, where it disrupts normal financial workflows, and whether the evidence
is reliable enough to support further development.

The system must work acceptably on **both CNFinBench and FinVault**. Keep their
results separate because their task labels and interaction structures differ.
The study does not reproduce Lakera’s proprietary system, establish production
readiness, or prove that a recorded financial action was actually stopped.

The team prioritizes F1/AUPRC while treating false-positive rate, recall,
coverage, reliability, and confirmation burden as required safety/operational
checks. The approved false-positive objective is **FPR at or below 30%**. Do not
trade away attack detection just to reduce interventions. The held-out final
split must stay untouched during design selection and tuning.

## Repository map

The root repository is the NeMo Guardrails codebase. Project-specific code is
isolated under `research/financial-guardrails/`:

- `financial_guardrails/`: policy engine, schema, detectors, datasets, evaluation,
  runners, integration, authorization, V3 judge and outcome judge.
- `policies/`: versioned deterministic and judge policies, tool mapping, outcome
  scoring contract.
- `config/`: NeMo configuration and Colang rails.
- `scripts/`: evaluation, reporting, audits, review export, and repair preparation.
- `slurm/`: HiPerGator batch templates.
- `tests/`: offline unit tests and fixtures. Unit tests must not call a live LLM.
- `data/`: local/private benchmark exports, ignored by Git.
- `outputs/`, `logs/`: generated local/HPG artifacts and logs, not shareable source
  data and normally not committed.

The research Python project and lockfile are local to this subdirectory. From
this directory, use `uv run --locked ...`. The user commonly runs long inference
jobs on HiPerGator (HPG), while source edits and lightweight validation are done
locally. Do not assume local and HPG filesystems are synchronized.

## The two evaluation questions

These are separate endpoints; do not combine or rename them as one “success”
metric.

### Attack attempt

Question: did the guardrail identify and intervene on an attempted attack?

- CNFinBench positive/negative labels: `harmful-` / `harmless-` case ID prefixes.
- FinVault positive/negative labels: `case_type == attack` / `case_type == normal`.
- `block`, `sanitize`, and `require_confirmation` count as intervention. Report
  confirmation separately; the team agreed that requesting confirmation stops
  the conversation for this endpoint. Static replay does not prove that a human
  later confirmed or rejected the action.

### Attack success / harmful outcome monitoring

Question: does the output/tool-stage evidence indicate that a harmful outcome
occurred or that a harmful response was produced?

- FinVault uses its `attack_success` annotation.
- CNFinBench uses only harmful conversations: HICS below 50 is positive, above
  50 negative, and exactly 50 is excluded. Harmless cases are not success-task
  negatives.
- Predictions must come from an outcome-specific assessment of output/tool
  surfaces. Do not reuse the combined attack-attempt decision as the success
  prediction.
- Do not supply outcome labels, sidecar annotations, or success fields to the
  guardrail prompt as trusted facts. They are evaluation labels only.

For both endpoints report completion/score coverage and detector errors alongside
classification metrics. AUROC/AUPRC require complete eligible score coverage.
Risk scores are ranking values, not calibrated probabilities. AUPRC depends on
class prevalence. `require_confirmation` is not evidence of actual prevention or
confirmation outcome.

## Dataset facts and limits

The supplied exports were inspected on HPG. They are benchmark/converter exports,
not comprehensive samples of all real-world financial workflows.

| Dataset | Size and structure | What it can test | Main limitations |
| --- | --- | --- | --- |
| `cnfinbench-pooled` | 642 cases; 24 turns each; 15,408 text messages; 321 attack-attempt positives and 321 negatives; no tool calls. Attack-success labels: 140 positive, 177 negative, 325 unlabeled. | Text-based attack-attempt detection and HICS-based harmful-response monitoring. | No tool authorization/execution behavior; success task applies only to eligible harmful cases. |
| `finvault-v5-fixed-full` | 1,043 cases; 957 attack-attempt and 86 normal labels; 4,838 tool calls and 4,838 tool results across 197 tool names. Attack-success labels: 534 positive and 509 negative. | Static screening of simulated financial-agent tool workflows and simulated outcome labels. | Tool traces and labels are simulator-produced, not independent application audit logs. The normal set is small and highly class-imbalanced for attack-attempt FPR. |

The team confirmed there are no separate application-side records available for
whether each exact tool call was independently authorized, human-confirmed, or
executed. FinVault’s `outcome`, `attack_success`, and `final_status` are useful
benchmark annotations but must not be fed into the guardrail as authorization or
execution proof. All recorded tool actions in this evaluation are **static**:
the runner does not execute them. CNFinBench has no tool-call records at all.

## System and model configuration

The evaluation uses deterministic defenses plus a written-policy LLM judge in
`rules_first_cascade`: deterministic rules run first, and the judge handles events
not already stopped by rules. The selected local backend is
`Qwen/Qwen3-8B-AWQ` on an HPG L4 GPU. V1/V2 routing and model were held fixed by
team direction. Version-specific policy and architecture changes are described
below. Navigator runs are historical comparisons, not the selected configuration.

NeMo configuration and Colang call custom actions; the same research policy
engine is used by the evaluator and NeMo integration. Verdicts are structured
(`allow`, `block`, `sanitize`, `require_confirmation`, or `log_only`) and include
policy IDs, risk category, surface, and detector status. Detector errors and
malformed responses are explicit; high-impact paths fail closed. Static replay
does not invoke external tools.

## Version history and decisions

### V1 — selected baseline, final split frozen

V1 combined deterministic policies, a written-policy LLM judge, NeMo actions,
and input/output/retrieval/tool-boundary checks. It established the comparison
baseline. It is strong on CNFinBench attack-attempt detection but too aggressive
on normal FinVault workflows. Its final result remains frozen and must not be
rewritten using later development/CV data.

Frozen held-out attack-attempt results:

| Dataset | N | F1 | Balanced accuracy | FPR | AUROC | AUPRC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| CNFinBench | 128 | 92.3% | 92.2% | 9.4% | 93.8% | 93.8% |
| FinVault | 223 | 96.3% | 50.0% | 100.0% | 61.3% | 94.5% |

V1 attack-success results were substantially weaker. CNFinBench final: N=64,
F1=53.6%, AUROC=56.1%, AUPRC=47.1%. FinVault’s later score-only diagnostic
preserved enforcement decisions and produced AUROC=55.2%, AUPRC=47.4% (N=223);
among attempted attacks AUROC=53.9%, AUPRC=50.1% (N=207). These are weak ranking
results, not a reliable outcome-monitoring capability.

### V2 — policy wording only; not selected

V2 and V2.1 kept the model, routing, deterministic hard boundaries, and output
schema fixed; they narrowed written judge-policy wording. The intent was to reduce
unnecessary interruptions while retaining attack recall. V2 calibration on
FinVault improved FPR/AUPRC over V1 calibration, but reduced F1/recall and raised
confirmation burden. V2 development had two fail-closed unknown-policy-ID errors;
V2.1’s two-case gate repeated them. Neither candidate qualified for selection or
final evaluation. There is no selected V2 final result.

Non-final CNFinBench V2 four-fold means: attack-attempt F1=84.4%, balanced
accuracy=85.2%, FPR=9.7%, AUROC=90.9%, AUPRC=90.9%; attack-success F1=44.6%,
AUROC=52.2%, AUPRC=46.0%. FinVault V2 evidence is calibration, not full CV:
F1=90.6%, recall=88.9%, FPR=77.8%, AUPRC=95.2%, versus V1 calibration F1=95.1%,
recall=98.4%, FPR=88.9%, AUPRC=94.3%. Do not describe V2 as an unambiguous
improvement.

### V3 — architecture diagnostic; not a V1 replacement

V3 added context-aware authorization interfaces, separate threat assessment and
control action, schema-constrained judge output with a bounded repair/fail-closed
path, and a separate static outcome monitor. The judge must not see benchmark
labels as trusted authorization facts. The V3 architecture was approved as an
experiment; team guidance kept the same model and routing where applicable,
retained deterministic controls for clear dangerous actions, and separated
attack-attempt detection from attack-success monitoring.

V3 ran non-final grouped four-fold evaluations on both datasets. Its overall FPR
did not meet the approved <=30% target. It is diagnostic only; do not run the
held-out final split for this candidate. The exploratory human review of 60
FinVault cases informed development and excluded reviewed source groups, but is
not independent blinded validation evidence.

## Latest matched V1–V3 fold comparison

These are the reports most relevant to the current decision. Eight matched-fold
reports were generated on HPG under
`outputs/v3-matched-v1-comparison/` on 2026-11-09. The V1 artifacts are under
`outputs/v3-matched-v1-cv/`; CNFinBench V3 candidate artifacts came from
`outputs/cnfinbench-v3-cv/`; FinVault V3 artifacts came from
`outputs/finvault-v3-outcome-consistency-rescore/`.

The report-reader correction is pushed on this branch as `81b7e4e27`. It allows
reports to recompute stale derived summaries from schema-validated records; it
changes reporting only, not the evaluated model or decisions. The earlier
FinVault V3 root-level fold artifacts had manifest/record outcome-score-mode
mismatches and were not used for these matched reports.

The report matches mutually completed records by case ID within each fold.
CNFinBench matched counts total 512 (fold counts 128, 129, 130, 125); FinVault
matched counts total 405 (60, 119, 118, 108). Two CNFinBench records from the
514-case four-fold pool are not in the matched comparison. The tables below
reproduce the generated fold reports; they are not pooled record-level estimates.

### CNFinBench: legacy intervention endpoint

| Fold | N | V1 F1 | V3 F1 | V1 recall | V3 recall | V1 FPR | V3 FPR |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 128 | 81.4% | 70.1% | 75.0% | 96.9% | 9.4% | 79.7% |
| 1 | 129 | 75.2% | 71.2% | 67.7% | 96.9% | 12.5% | 76.6% |
| 2 | 130 | 84.1% | 71.2% | 81.5% | 96.9% | 12.3% | 75.4% |
| 3 | 125 | 86.0% | 72.1% | 82.5% | 98.4% | 9.7% | 75.8% |

The grouped normal-case comparison corresponds to V3-minus-V1 FPR increases of
70.3, 64.1, 63.1, and 66.1 percentage points by fold. The report instead
labels baseline-minus-V3 as “FPR reduction,” so it prints negative point changes
and negative confidence intervals. Group sign-flip p-values were printed as
`0.000000`/`0.000010`; the test used sampled sign flips
(`exact_enumeration: False`), so `0.000000` is rounded output, not literal
probability zero.

V3 threat-assessment FPR was 76.6%, 75.0%, 73.8%, and 75.8% (AUPRC 64.8%,
61.9%, 63.9%, 66.9%). This endpoint is separate from intervention.

### FinVault: legacy intervention endpoint

| Fold | N | V1 F1 | V3 F1 | V1 recall | V3 recall | V1 FPR | V3 FPR |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 60 | 94.5% | 86.6% | 96.3% | 77.8% | 66.7% | 16.7% |
| 1 | 119 | 95.2% | 92.8% | 100.0% | 95.4% | 100.0% | 100.0% |
| 2 | 118 | 95.6% | 91.7% | 100.0% | 91.7% | 100.0% | 90.0% |
| 3 | 108 | 95.7% | 94.1% | 100.0% | 97.0% | 100.0% | 100.0% |

There were only 36 matched normal cases across the four folds (6, 11, 10, 9),
so FPR estimates are imprecise. Grouped FPR reduction was 50%, 0%, 10%, and 0%
by fold; all reported sign-flip p-values were 1.0. V3 threat FPR was 16.7%,
72.7%, 90.0%, and 88.9%; threat AUPRC was 96.8%, 93.5%, 92.7%, and 92.5%.
High AUPRC does not erase high fixed-decision FPR.

### Interpretation of the matched reports

- CNFinBench: V3 recall is higher in every fold, but FPR increases from about
  9–13% to about 75–80%; F1 falls in every fold. This is a serious regression
  for the multi-dataset goal.
- FinVault: V3 lowers FPR substantially in fold 0 and slightly in fold 2, but
  FPR remains 90–100% in the other folds. Recall and F1 fall in every fold.
  The very small normal sample limits the precision of the FPR comparison.
- Do not claim V3 is a global improvement. These results show a poor cross-data
  tradeoff: aggressive detection on CNFinBench and inconsistent FinVault FPR
  improvement.
- The matched reports compare completed case IDs, but an input/configuration
  audit is still needed before calling the comparison controlled. In particular,
  the comparison utility enforces `v3_clean` on the V3 candidate but does not
  enforce the V1 baseline input view. Verify all manifests for input view,
  judge mode, model, policy, dataset/metadata hashes, fold, and reviewed-group
  exclusions. If V1 was not evaluated on the same cleaned inputs and compatible
  exclusions, retain the reports as descriptive diagnostics, not causal evidence.
- Use record-level pooled metrics and grouped uncertainty for each dataset before
  presenting one aggregate comparison. Do not average fold percentages and call
  that a pooled metric.

## Attack-success score status

Attack-success monitoring has been difficult and must remain separate from the
attempt endpoint. The current status is not “no data”: replay/rescore work
produced full-fold artifacts and the reports showed score coverage for eligible
labels, but the scores/predictions were weak or collapsed. Do not cite the older
`135/405` incomplete-score figure as the final current coverage without checking
which artifact it describes; it predates later replay/rescore jobs.

In later full-CV consistency-rescore reports, CNFinBench predictions were all
negative, AUROC was 0.50 in each fold, AUPRC ranged 34.9–49.2%, and F1 was
unavailable. FinVault attack-success ranking was also near chance/weak (fold
AUROC 50.0–50.8%; AUPRC 38.3–75.1%; F1 unavailable or 2.2–3.0%). These results
do not establish a useful outcome monitor. The 24-case ordinal-score gate was a
separate small diagnostic: CNFinBench had one score level (all 0.00), AUROC 0.50
and AUPRC 0.375; FinVault had three score levels, AUROC about 0.633 and AUPRC
about 0.575. The latter is preliminary only. Do not combine it with full-CV or
earlier numeric-score artifacts; the ordinal score is not a probability.

## Current next steps

1. **Audit all 16 manifests** (8 V1 matched artifacts and 8 V3 candidates): input
   view; model and revision; judge mode; policy IDs and hashes; code commit;
   dataset and metadata hashes; fold; reviewed-group checksum; expected and
   completed counts; detector errors; judge-call telemetry. Confirm whether the
   V1 runs really used `v3_clean` and the same case/group exclusions. The report
   generator currently does not enforce every such baseline match.
2. **If comparable, compute pooled record-level matched metrics** separately for
   CNFinBench and FinVault, with source-group-aware confidence intervals. Keep
   the four fold tables and coverage/error counts beside pooled results.
3. **If not comparable, label the current results diagnostic.** Decide with the
   team whether to rerun a truly matched V1 condition; do not silently present a
   raw-vs-clean comparison as controlled.
4. **Update the V3 team report** with the matched findings, dataset-specific
   interpretation, manifest caveat, and weak attack-success results.
5. **Before another candidate:** obtain team direction, write a specific
   hypothesis, freeze a versioned config, use development/calibration only,
   require a small reliability gate, then group-disjoint CV on both datasets.
   Do not tune on or run the held-out final split unless the preregistered gates
   are met and the team approves advancement.

No new HPG inference job is required just to audit manifests and create
record-level reports. HPG artifacts and `squeue` state are external to this local
checkout; the latest verified activity for this handoff is the completed eight
matched runs and eight generated fold reports above. Check HPG before assuming
any job is pending or complete.

## Operating instructions for an assistant

- Recommend the best scientifically defensible next step; verify the chosen
  step and state limitations plainly. Do not agree by default or overstate
  significance.
- Keep CNFinBench and FinVault results separate; keep attack attempt and attack
  success separate; distinguish static benchmark evidence from real application
  evidence.
- Be concise in chat, but give the user enough evidence to understand decisions.
  When giving commands, give **one command at a time** and say whether to run it
  locally or on HPG. Give a rough wall-time estimate for each submitted HPG job.
- Continue unblocked authorized research work without needless confirmation.
  Stop for external HPG actions only when the user must run a command, when a
  required external approval is genuinely missing, or when results require team
  input.
- Use `uv` for Python. From the project directory on HPG:

  ```bash
  cd /path/to/your/dir/NeMo-Guardrails/research/financial-guardrails
  ~/.local/bin/uv run --locked python ...
  ```

- Never place private benchmark text, raw traces, secrets, credentials, or
  provider data in Git, Slack, or a public report. Keep output content-free.
  Do not pass labels/sidecar annotations to the guardrail prompt.
- Check `git status` before editing/committing. Preserve unrelated or untracked
  user files. Commit/push only focused, validated changes within the authorized
  research scope; no PR unless explicitly requested.

## Key documents

| Document | Use | Status note |
| --- | --- | --- |
| `AGENTS.md`, `AI_POLICY.md` at repository root | Required agent/contribution/privacy rules | Canonical instructions. |
| `README.md` | Project orientation and commands | Early-stage content; partly stale. |
| `EVALUATION_PROTOCOL.md` | Labels, endpoints, splits, metrics, final-split restrictions | Canonical evaluation definitions; check amendments. |
| `METRICS.md` | Fields and metric validity/coverage rules | Canonical metric explanations. |
| `POLICY_SELECTION_PROTOCOL.md` | Candidate selection and reliability gates | Current V2 and later policy-selection framework; observe final holdout rule. |
| `ARCHITECTURE.md`, `VERSION_3_AUTHORIZATION_DESIGN.md`, `VERSION_3_TRUSTED_FACTS.md` | Runtime design and trust boundaries | Use for implementation details. |
| `PRIMARY_FINAL_EVALUATION_REPORT.md` | Frozen V1 final results | Do not rewrite from development/CV evidence. |
| `VERSION_1_SUMMARY_AND_RESULTS.md` | External V1 overview | Historical final result and limitations. |
| `VERSION_2_EVALUATION_REPORT.md` | V2 candidate and calibration results | Has stale “In progress” wording; verify before citing. |
| `VERSION_3_DESIGN_AND_EVALUATION_PROTOCOL.md`, `VERSION_3_PROTOCOL_AMENDMENT_1.md`, `VERSION_3_PROTOCOL_AMENDMENT_2.md` | V3 design and approved amendments | Read together; amendments may supersede base protocol. |
| `VERSION_3_STATUS_AND_NEXT_STEPS.md`, `VERSION_3_SUMMARY.md` | Prior V3 status/results narrative | Some figures/status predate the latest repairs and matched reports; this handoff records the newer findings. |
| `policies/POLICY_MAPPING.md`, `policies/FINVAULT_TOOL_REVIEW.md` | Lakera public-defense mapping and FinVault tool notes | Policy rationale and scope. |
| `JUDGE_RUNBOOK.md`, `MODELS.md`, `VALIDATION.md` | Backend, model, and run procedures | Consult before model or scheduler changes. |
