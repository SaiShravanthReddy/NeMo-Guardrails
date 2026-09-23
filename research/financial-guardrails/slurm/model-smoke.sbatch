#!/bin/bash
#SBATCH --job-name=open-lakera-smoke
#SBATCH --account=iruchkin
#SBATCH --qos=iruchkin
#SBATCH --partition=hpg-turin
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=00:15:00
#SBATCH --output=logs/model-smoke-%j.out
#SBATCH --error=logs/model-smoke-%j.err

set -euo pipefail

nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
uv run --locked --extra local-models python scripts/model_smoke.py --model content_safety --device auto
