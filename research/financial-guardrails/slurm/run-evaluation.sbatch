#!/bin/bash
#SBATCH --job-name=open-lakera-eval
#SBATCH --account=iruchkin
#SBATCH --qos=iruchkin
#SBATCH --partition=hpg-turin
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=24:00:00
#SBATCH --output=logs/evaluation-%j.out
#SBATCH --error=logs/evaluation-%j.err

set -euo pipefail

: "${DATASET:?Set DATASET to cnfinbench-pooled or finvault-v5-fixed-full}"
: "${JUDGE_MODE:?Set JUDGE_MODE to all_events or rules_first_cascade}"
SPLIT="${SPLIT:-pilot}"
MAX_CASES="${MAX_CASES:-}"
CASE_ID_FILE="${CASE_ID_FILE:-}"
CV_FOLD="${CV_FOLD:-}"
RESUME_CHECKPOINT="${RESUME_CHECKPOINT:-}"
PROJECT_ROOT="${SLURM_SUBMIT_DIR}"
VLLM_BIN="${PROJECT_ROOT}/.venv-vllm/bin/vllm"
NINJA_BIN="${PROJECT_ROOT}/.venv-vllm/bin/ninja"
PROJECT_PYTHON="${PROJECT_ROOT}/.venv/bin/python"
MODEL_ID="Qwen/Qwen3-8B-AWQ"
MODEL_REVISION="4da05a8edb55c6046cce958586c33b61da07bb79"
SERVER_LOG="${PROJECT_ROOT}/logs/vllm-${SLURM_JOB_ID}.log"

test -x "${VLLM_BIN}"
test -x "${NINJA_BIN}"
test -x "${PROJECT_PYTHON}"
cd "${PROJECT_ROOT}"
export PATH="${PROJECT_ROOT}/.venv-vllm/bin:${PATH}"
test "$(command -v ninja)" = "${NINJA_BIN}"
ninja --version
mkdir -p logs outputs

export HF_HOME="${HF_HOME:-/blue/iruchkin/sa.madem/huggingface}"
mkdir -p "${HF_HOME}"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader

"${VLLM_BIN}" serve "${MODEL_ID}" \
  --revision "${MODEL_REVISION}" \
  --host 127.0.0.1 \
  --port 8000 \
  --quantization awq \
  --max-model-len 32768 \
  --gpu-memory-utilization 0.85 \
  --no-enable-log-requests \
  --disable-uvicorn-access-log \
  >"${SERVER_LOG}" 2>&1 &
SERVER_PID=$!
trap 'kill "${SERVER_PID}" 2>/dev/null || true' EXIT

for _attempt in $(seq 1 120); do
  if curl --fail --silent http://127.0.0.1:8000/health >/dev/null; then
    break
  fi
  if ! kill -0 "${SERVER_PID}" 2>/dev/null; then
    echo "vLLM exited before its health check passed" >&2
    exit 1
  fi
  sleep 5
done
curl --fail --silent http://127.0.0.1:8000/health >/dev/null

evaluation_args=(
  "${DATASET}"
  --split "${SPLIT}"
  --judge-mode "${JUDGE_MODE}"
  --backend hipergator
)
if [[ -n "${MAX_CASES}" ]]; then
  [[ "${MAX_CASES}" =~ ^[1-9][0-9]*$ ]] || { echo "MAX_CASES must be a positive integer" >&2; exit 2; }
  evaluation_args+=(--max-cases "${MAX_CASES}")
fi
if [[ -n "${CASE_ID_FILE}" ]]; then
  [[ -z "${MAX_CASES}" ]] || { echo "Set only one of MAX_CASES or CASE_ID_FILE" >&2; exit 2; }
  [[ -z "${CV_FOLD}" ]] || { echo "CV_FOLD cannot be combined with CASE_ID_FILE" >&2; exit 2; }
  test -r "${CASE_ID_FILE}"
  evaluation_args+=(--case-id-file "${CASE_ID_FILE}")
fi
if [[ -n "${CV_FOLD}" ]]; then
  [[ -z "${MAX_CASES}" ]] || { echo "CV_FOLD cannot be combined with MAX_CASES" >&2; exit 2; }
  [[ "${CV_FOLD}" =~ ^[0-3]$ ]] || { echo "CV_FOLD must be 0, 1, 2, or 3" >&2; exit 2; }
  evaluation_args+=(--cv-fold "${CV_FOLD}")
fi
if [[ -n "${RESUME_CHECKPOINT}" ]]; then
  test -r "${RESUME_CHECKPOINT}"
  evaluation_args+=(--resume-checkpoint "${RESUME_CHECKPOINT}")
fi

"${PROJECT_PYTHON}" -m scripts.run_static_evaluation "${evaluation_args[@]}"
