# Version 3 outcome-score replay gate

This gate checks whether the 270 missing FinVault outcome scores can be recovered
reliably. It replays 12 cases, three from each non-final CV fold. It is a small
diagnostic sample, not a new performance estimate or a substitute for complete
score coverage.

## Local preparation

- [x] Record only a bounded, content-free outcome failure code in evaluation
  records. Never persist exception text or prompts.
- [x] Add a preparer that checks dataset and reviewed-group provenance, selects
  three eligible missing-score cases per fold, and writes private checkpoints
  retaining all other records.
- [x] Verify tests and code checks before using it on HPG.
- [x] Commit and push the validated research changes (`d1dbf86f9`).

## HPG preparation and run

Run these steps from
`/path/to/your/dir/NeMo-Guardrails/research/financial-guardrails`.

1. Wait until the currently submitted jobs have finished. Confirm the worktree
   is clean, then fast-forward the research branch to receive the gate tool.
2. Prepare four private checkpoints from the latest complete FinVault V3 fold
   artifacts:

   ```bash
   uv run --locked python -m scripts.prepare_v3_outcome_gate \
     outputs/finvault-v5-fixed-full-cv0-hipergator-v3-1867ebc4d905.json \
     outputs/finvault-v5-fixed-full-cv1-hipergator-v3-5e5457207d99.json \
     outputs/finvault-v5-fixed-full-cv2-hipergator-v3-2b33e73b0cf2.json \
     outputs/finvault-v5-fixed-full-cv3-hipergator-v3-00f4601bbacb.json \
     --reviewed-groups-file outputs/finvault-v3-private-review/coordinator/reviewed-source-groups-v3.json \
     --output-dir outputs/finvault-v3-outcome-gate
   ```

   It should report three replay cases and a retained checkpoint for each fold,
   for 12 replay cases total. It refuses mismatched provenance, incomplete
   folds, insufficient eligible candidates, or non-empty output directories.
   **Each checkpoint is mutable resume state:** the evaluation runner appends
   replayed records to it. Do not reuse a checkpoint after a job has consumed
   it; prepare a fresh gate directory from the original CV artifacts for every
   diagnostic rerun.
3. Submit one `slurm/run-v3-evaluation.sbatch` job per fold with:
   `DATASET=finvault-v5-fixed-full`, `SPLIT=all`, the matching `CV_FOLD`, the
   reviewed-groups file above, that fold's `.checkpoint.jsonl` as `CHECKPOINT`,
   and `OUTPUT_DIR=outputs/finvault-v3-outcome-gate`.
4. Verify all four jobs exit successfully and each resulting fold artifact has
   the expected case count, complete attack-success score coverage for the 12
   replayed cases, zero outcome-score detector errors for those cases, and
   matching judge attempt/backend-call telemetry. Check attempt-detector
   errors separately; they are not the outcome-score gate. Inspect only
   aggregate outcome failure-code counts.
5. If the gate passes, prepare a full repair from the latest four gate-result
   artifacts using `--all-missing` and a fresh output directory. This selects
   every labeled case with a missing score and usable outcome events, including
   cases whose separate attack-attempt prediction failed. If it fails, use the
   error-code counts to diagnose first; do not launch the full replay until the
   cause is understood.

## Interpretation

- A clean 12-case gate shows that the new diagnostic path works on this sample.
- It does not establish that all 270 cases will succeed or that outcome
  AUROC/AUPRC are complete.
- Full coverage requires rerunning all eligible missing-score cases, then
  validating fold membership, score coverage, detector errors, and telemetry
  before reporting outcome ranking metrics.
- Keep Version 1 and Version 2 artifacts unchanged. Keep case-ID files,
  checkpoints, traces, and generated evaluation artifacts private on HPG.

## Content-free result template

| Fold | Replayed | Completed | Outcome scores | Outcome errors by code | Backend calls match attempts |
| ---: | ---: | ---: | ---: | --- | --- |
| 0 |  |  |  |  |  |
| 1 |  |  |  |  |  |
| 2 |  |  |  |  |  |
| 3 |  |  |  |  |  |
| Total | 12 |  |  |  |  |

Do not put case IDs, prompts, traces, or raw provider responses in this summary.
