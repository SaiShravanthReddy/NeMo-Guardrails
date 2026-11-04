# CNFinBench Version 3 outcome-score replay gate

The completed CNFinBench V3 folds have attack-success scores for only 35 of
253 eligible cases (13.8%). A 12-case gate can diagnose whether missing scores
are recoverable. It is not a performance estimate.

## HPG preparation

Run after the completed V3 artifacts are available and the latest research
branch is pulled. Work from
`/path/to/your/dir/NeMo-Guardrails/research/financial-guardrails`.

1. Confirm the four existing CNFinBench V3 fold artifacts are the only `.json`
   artifacts in `outputs/cnfinbench-v3-cv/`.
2. Prepare three private replay cases per fold:

   ```bash
   ~/.local/bin/uv run --locked python -m scripts.prepare_v3_outcome_gate \
     outputs/cnfinbench-v3-cv/*.json \
     --dataset cnfinbench-pooled \
     --output-dir outputs/cnfinbench-v3-outcome-gate
   ```

   Expect four fold checkpoints and four case-ID files, with 12 replay cases
   total. The preparer verifies fold membership, data and metadata checksums,
   model/policy/code consistency, labeled missing-score eligibility, and usable
   outcome events. It writes private files and refuses non-empty output dirs.
3. Submit one `slurm/run-v3-evaluation.sbatch` job per fold with
   `DATASET=cnfinbench-pooled`, `SPLIT=all`, the matching `CV_FOLD`, that fold's
   `.checkpoint.jsonl` as `CHECKPOINT`, and
   `OUTPUT_DIR=outputs/cnfinbench-v3-outcome-gate`.
4. Verify all 12 selected cases complete with outcome scores, zero
   outcome-score errors, and matching logical judge-attempt/backend-call
   telemetry. Inspect aggregate outcome failure-code counts only. Report
   attempt-detector errors separately.
5. If the gate passes, prepare a targeted full repair of the remaining
   eligible missing-score cases. If it fails, diagnose the recorded failure
   categories before any broader replay.

## Interpretation

- The gate tests whether this small sample can be rescored; it cannot establish
  full score coverage.
- Complete CNFinBench attack-success AUROC/AUPRC requires scores for all 253
  eligible cases. Keep any remaining detector errors visible in coverage and
  reliability results.
- Keep the original CV artifacts unchanged. Preserve checkpoints and case-ID
  files privately on HPG.
