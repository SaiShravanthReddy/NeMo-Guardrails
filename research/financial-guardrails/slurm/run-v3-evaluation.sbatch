#!/bin/bash
#SBATCH --job-name=open-lakera-v3-eval
#SBATCH --account=iruchkin
#SBATCH --qos=iruchkin
#SBATCH --partition=hpg-turin
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=24:00:00
#SBATCH --output=logs/v3-evaluation-%j.out
#SBATCH --error=logs/v3-evaluation-%j.err

set -euo pipefail

: "${DATASET:?Set DATASET to cnfinbench-pooled or finvault-v5-fixed-full}"
: "${TRUSTED_FACTS:?Set TRUSTED_FACTS to the private trusted-facts JSON file}"
SPLIT="${SPLIT:-pilot}"
CV_FOLD="${CV_FOLD:-}"
REVIEWED_GROUPS_FILE="${REVIEWED_GROUPS_FILE:-}"
MAX_CASES="${MAX_CASES:-}"
CHECKPOINT="${CHECKPOINT:-}"
OUTPUT_DIR="${OUTPUT_DIR:-outputs}"
JUDGE_POLICY_PATH="${JUDGE_POLICY_PATH:-}"
PROJECT_ROOT="${SLURM_SUBMIT_DIR}"
VLLM_BIN="${PROJECT_ROOT}/.venv-vllm/bin/vllm"
NINJA_BIN="${PROJECT_ROOT}/.venv-vllm/bin/ninja"
PROJECT_PYTHON="${PROJECT_ROOT}/.venv/bin/python"
MODEL_ID="Qwen/Qwen3-8B-AWQ"
MODEL_REVISION="4da05a8edb55c6046cce958586c33b61da07bb79"
SERVER_LOG="${PROJECT_ROOT}/logs/vllm-${SLURM_JOB_ID}.log"

[[ "${DATASET}" == "cnfinbench-pooled" || "${DATASET}" == "finvault-v5-fixed-full" ]] || {
  echo "DATASET is invalid" >&2
  exit 2
}
test -r "${TRUSTED_FACTS}"
if [[ "${DATASET}" == "finvault-v5-fixed-full" ]]; then
  [[ -n "${REVIEWED_GROUPS_FILE}" ]] || { echo "FinVault V3 requires REVIEWED_GROUPS_FILE" >&2; exit 2; }
  test -r "${REVIEWED_GROUPS_FILE}"
fi
if [[ -n "${CV_FOLD}" ]]; then
  [[ "${CV_FOLD}" =~ ^[0-3]$ ]] || { echo "CV_FOLD must be 0, 1, 2, or 3" >&2; exit 2; }
fi
if [[ -n "${MAX_CASES}" ]]; then
  [[ "${MAX_CASES}" =~ ^[1-9][0-9]*$ ]] || { echo "MAX_CASES must be a positive integer" >&2; exit 2; }
fi

test -x "${VLLM_BIN}"
test -x "${NINJA_BIN}"
test -x "${PROJECT_PYTHON}"
cd "${PROJECT_ROOT}"
export PATH="${PROJECT_ROOT}/.venv-vllm/bin:${PATH}"
test "$(command -v ninja)" = "${NINJA_BIN}"
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
  --trusted-facts "${TRUSTED_FACTS}"
  --backend hipergator
  --split "${SPLIT}"
  --output-dir "${OUTPUT_DIR}"
)
if [[ -n "${REVIEWED_GROUPS_FILE}" ]]; then
  evaluation_args+=(--reviewed-groups-file "${REVIEWED_GROUPS_FILE}")
fi
if [[ -n "${CV_FOLD}" ]]; then
  evaluation_args+=(--cv-fold "${CV_FOLD}")
fi
if [[ -n "${MAX_CASES}" ]]; then
  evaluation_args+=(--max-cases "${MAX_CASES}")
fi
if [[ -n "${CHECKPOINT}" ]]; then
  test -r "${CHECKPOINT}"
  evaluation_args+=(--checkpoint "${CHECKPOINT}")
fi
if [[ -n "${JUDGE_POLICY_PATH}" ]]; then
  test -r "${JUDGE_POLICY_PATH}"
  evaluation_args+=(--judge-policy-path "${JUDGE_POLICY_PATH}")
fi

"${PROJECT_PYTHON}" -m scripts.run_v3_static_evaluation "${evaluation_args[@]}"
