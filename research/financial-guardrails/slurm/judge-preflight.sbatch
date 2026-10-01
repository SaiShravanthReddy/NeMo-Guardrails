#!/bin/bash
#SBATCH --job-name=open-lakera-judge-preflight
#SBATCH --account=iruchkin
#SBATCH --qos=iruchkin
#SBATCH --partition=hpg-turin
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --output=logs/judge-preflight-%j.out
#SBATCH --error=logs/judge-preflight-%j.err

set -euo pipefail

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

export HF_HOME="${HF_HOME:-/blue/iruchkin/sa.madem/huggingface}"
mkdir -p "${HF_HOME}"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
"${VLLM_BIN}" --version

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
"${PROJECT_PYTHON}" -m scripts.judge_preflight --backend hipergator --timeout 120
