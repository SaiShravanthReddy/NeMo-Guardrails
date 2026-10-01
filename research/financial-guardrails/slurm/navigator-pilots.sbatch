#!/bin/bash
#SBATCH --job-name=open-lakera-navigator-pilots
#SBATCH --account=iruchkin
#SBATCH --qos=iruchkin
#SBATCH --partition=hpg-default
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=04:00:00
#SBATCH --output=logs/navigator-pilots-%j.out
#SBATCH --error=logs/navigator-pilots-%j.err
#SBATCH --mail-type=BEGIN,END,FAIL

set -euo pipefail

PROJECT_ROOT="${SLURM_SUBMIT_DIR}"
DATASET="${DATASET:-cnfinbench-pooled}"
case "${DATASET}" in
  cnfinbench-pooled|finvault-v5-fixed-full) ;;
  *) echo "Unsupported DATASET: ${DATASET}" >&2; exit 2 ;;
esac
cd "${PROJECT_ROOT}"
mkdir -p logs outputs

test -r .env.local
set -a
source .env.local
set +a
test -n "${NAVIGATOR_TOOLKIT_API_KEY:-}"

echo "MILESTONE 1/5: validating NaviGator before ${DATASET} cascade pilot"
.venv/bin/python -m scripts.judge_preflight --backend navigator

echo "MILESTONE 2/5: running ${DATASET} rules-first cascade pilot"
.venv/bin/python -m scripts.run_static_evaluation "${DATASET}" \
  --split pilot \
  --judge-mode rules_first_cascade \
  --backend navigator

echo "MILESTONE 3/5: revalidating NaviGator before ${DATASET} all-events pilot"
.venv/bin/python -m scripts.judge_preflight --backend navigator

echo "MILESTONE 4/5: running ${DATASET} all-events pilot"
.venv/bin/python -m scripts.run_static_evaluation "${DATASET}" \
  --split pilot \
  --judge-mode all_events \
  --backend navigator

echo "MILESTONE 5/5: both ${DATASET} NaviGator pilots completed"
