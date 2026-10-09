#!/bin/bash
#SBATCH --job-name=open-lakera-navigator-eval
#SBATCH --account=iruchkin
#SBATCH --qos=iruchkin
#SBATCH --partition=hpg-default
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=12:00:00
#SBATCH --output=logs/navigator-evaluation-%j.out
#SBATCH --error=logs/navigator-evaluation-%j.err

set -euo pipefail

: "${DATASET:?Set DATASET to cnfinbench-pooled or finvault-v5-fixed-full}"
: "${JUDGE_MODE:?Set JUDGE_MODE to all_events or rules_first_cascade}"
SPLIT="${SPLIT:-pilot}"
MAX_CASES="${MAX_CASES:-}"
CASE_ID_FILE="${CASE_ID_FILE:-}"
PROJECT_ROOT="${SLURM_SUBMIT_DIR}"
PROJECT_PYTHON="${PROJECT_ROOT}/.venv/bin/python"
ENV_FILE="${PROJECT_ROOT}/.env.local"

case "${DATASET}" in
  cnfinbench-pooled|finvault-v5-fixed-full) ;;
  *) echo "Unsupported DATASET: ${DATASET}" >&2; exit 2 ;;
esac
case "${JUDGE_MODE}" in
  all_events|rules_first_cascade) ;;
  *) echo "Unsupported JUDGE_MODE: ${JUDGE_MODE}" >&2; exit 2 ;;
esac

test -x "${PROJECT_PYTHON}"
test -r "${ENV_FILE}"
cd "${PROJECT_ROOT}"
mkdir -p logs outputs
set -a
source "${ENV_FILE}"
set +a
test -n "${NAVIGATOR_TOOLKIT_API_KEY:-}"

echo "MILESTONE 1/3: validating NaviGator before ${DATASET} evaluation"
"${PROJECT_PYTHON}" -m scripts.judge_preflight --backend navigator

evaluation_args=(
  "${DATASET}"
  --split "${SPLIT}"
  --judge-mode "${JUDGE_MODE}"
  --backend navigator
)
if [[ -n "${MAX_CASES}" ]]; then
  [[ "${MAX_CASES}" =~ ^[1-9][0-9]*$ ]] || { echo "MAX_CASES must be a positive integer" >&2; exit 2; }
  evaluation_args+=(--max-cases "${MAX_CASES}")
fi
if [[ -n "${CASE_ID_FILE}" ]]; then
  [[ -z "${MAX_CASES}" ]] || { echo "Set only one of MAX_CASES or CASE_ID_FILE" >&2; exit 2; }
  test -r "${CASE_ID_FILE}"
  evaluation_args+=(--case-id-file "${CASE_ID_FILE}")
fi

echo "MILESTONE 2/3: running ${DATASET} ${JUDGE_MODE} evaluation"
"${PROJECT_PYTHON}" -m scripts.run_static_evaluation "${evaluation_args[@]}"
echo "MILESTONE 3/3: ${DATASET} evaluation completed"
