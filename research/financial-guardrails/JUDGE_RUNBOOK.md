# Judge deployment and preflight runbook

This project uses the same policy prompt, response parser, and aggregation path for
two judge backends:

| Backend | Model | Execution location |
| --- | --- | --- |
| `navigator` | `gpt-oss-120b` | UF NaviGator AI Toolkit |
| `hipergator` | `Qwen/Qwen3-8B-AWQ` at revision `4da05a8edb55c6046cce958586c33b61da07bb79` | One `hpg-turin` L4 |

The local model is served through vLLM's loopback-only OpenAI-compatible endpoint.
The application therefore uses one client implementation for both backends. Never
place the NaviGator key in Git, a SLURM script, shell history, or job output.

## Experiment matrix

For each inference condition, freeze the policy, dataset checksum, code commit, and
generation settings. Run these matched conditions:

1. NaviGator judge on every applicable event.
2. NaviGator judge only when deterministic rules do not already intervene.
3. HiPerGator judge on every applicable event.
4. HiPerGator judge only when deterministic rules do not already intervene.

Run each condition on CNFinBench and FinVault. One FinVault inference pass can be
scored twice, because the completed-outcome and runtime-interception reports use the
same cases with different documented labels. This yields eight LLM inference runs
and twelve metric rows, rather than repeating identical FinVault inference. Run the
rules-only baseline once per dataset and score FinVault both ways as well.

This is a comparison of two deployable configurations, not a controlled test of
hosted versus local infrastructure: `gpt-oss-120b` and Qwen3-8B-AWQ differ in model
family, size, quantization, and serving stack.

## 1. Offline check on the Mac

From the repository root:

```bash
cd research/financial-guardrails
UV_CACHE_DIR=/tmp/open-lakera-uv-cache uv sync --locked
UV_CACHE_DIR=/tmp/open-lakera-uv-cache uv run --locked pytest -q
```

This must pass without a network call or API key.

## 2. NaviGator preflight

Read the key without echoing it, export it only in the current shell, and make two
content-free test calls:

```bash
cd research/financial-guardrails
read -rs "NAVIGATOR_TOOLKIT_API_KEY?NaviGator API key: "
echo
export NAVIGATOR_TOOLKIT_API_KEY
uv run --locked python -m scripts.judge_preflight --backend navigator
unset NAVIGATOR_TOOLKIT_API_KEY
```

Success means the command prints one JSON object containing only the backend name,
two fixture decisions, policy IDs, and latencies. It must show `allow` for `safe`
and a non-allow decision for `attack`. Stop if authentication fails, the model is
unavailable, JSON is malformed, either fixture is misclassified, or the team budget
cannot be verified. A `/models` response alone is not enough.

As checked on 2026-10-01, UF lists `gpt-oss-120b` with a 128,000-token context at
$0.06 per million input tokens and $0.15 per million output tokens. Recheck the live
price and remaining account budget before every full run.

## 3. One-time HiPerGator setup

Use a dedicated clone at the following path, or replace `OPEN_LAKERA_REPO` with the
actual clone location. These commands do not modify the AgentAuditor repository.

```bash
export OPEN_LAKERA_REPO=/blue/iruchkin/sa.madem/NeMo-Guardrails
cd /blue/iruchkin/sa.madem
git clone https://github.com/SaiShravanthReddy/NeMo-Guardrails.git NeMo-Guardrails
cd "$OPEN_LAKERA_REPO"
git switch research/financial-guardrails-plan
git pull --ff-only origin research/financial-guardrails-plan
```

If the clone already exists, skip `git clone` and run only the final three commands.
Check space before installing or downloading approximately 6.1 GB of weights:

```bash
blue_quota -g iruchkin
df -h /blue/iruchkin
```

Create two separate environments. The project environment remains locked; vLLM is
isolated because its GPU dependency stack is large and platform-specific:

```bash
cd "$OPEN_LAKERA_REPO/research/financial-guardrails"
uv sync --locked
uv venv --python 3.11 .venv-vllm
uv pip install --python .venv-vllm/bin/python 'vllm==0.30.0'
.venv-vllm/bin/vllm --version
```

The recorded version must be `0.30.0`. If installation fails because of the
compute node's CUDA driver or Python compatibility, stop and retain the full error;
do not replace the pinned package during the experiment.

### Unattended NaviGator pilots

`slurm/navigator-pilots.sbatch` runs a live two-fixture preflight before each pilot,
then runs the cascade and all-events CNFinBench pilot conditions. It stops on the
first failure, checkpoints after every completed case, prints progress every 10%,
and requests SLURM mail for job start, completion, or failure. Supply the email
address at submission time; do not commit it or the API key.

## 4. First HiPerGator GPU preflight

Create the log directory before submitting because SLURM opens log files before the
job begins:

```bash
cd "$OPEN_LAKERA_REPO/research/financial-guardrails"
mkdir -p logs
sbatch slurm/judge-preflight.sbatch
squeue -u sa.madem
```

After the job finishes, replace `<job-id>` and inspect its outcome:

```bash
sacct -j <job-id> --format=JobID,State,ExitCode,Elapsed,MaxRSS,AllocTRES
cat "logs/judge-preflight-<job-id>.out"
cat "logs/judge-preflight-<job-id>.err"
```

Proceed to a stratified pilot only when the job state is `COMPLETED`, its exit code
is `0:0`, the L4 is detected, the vLLM health check passes, and both reviewed
fixtures pass. This preflight does not establish benchmark accuracy.

## 5. Gates before full evaluation

Before either backend receives a full dataset, verify all of the following:

- Dataset checksums match the recorded CNFinBench and FinVault manifests.
- Leakage-safe development and final splits are frozen.
- Both judge modes pass the same stratified pilot.
- Result manifests, restart checkpoints, latency, token counts, and resource use are recorded.
- Raw benchmark prompts, model responses, credentials, and detected secrets are absent from logs.
- The NaviGator cost estimate fits the available account balance.
- HiPerGator peak GPU memory and maximum input length pass on the selected L4 settings.

## 6. Evaluation jobs

The runner replays recorded conversations without executing their tool calls. Its
JSONL checkpoint is flushed after every case, and rerunning the same command resumes
completed cases. Run the readiness check before submission:

```bash
cd "$OPEN_LAKERA_REPO/research/financial-guardrails"
uv run --locked python -m scripts.check_hpg_readiness --require-hpg-tools
mkdir -p logs outputs
```

Submit the pilot conditions one at a time so each result can be reviewed before a
larger run:

```bash
DATASET=cnfinbench-pooled SPLIT=pilot JUDGE_MODE=rules_first_cascade \
  sbatch --export=ALL,DATASET,SPLIT,JUDGE_MODE slurm/run-evaluation.sbatch

DATASET=finvault-v5-fixed-full SPLIT=pilot JUDGE_MODE=rules_first_cascade \
  sbatch --export=ALL,DATASET,SPLIT,JUDGE_MODE slurm/run-evaluation.sbatch
```

Repeat with `JUDGE_MODE=all_events` only after both cascade pilots pass. Replace
`SPLIT=pilot` with `SPLIT=final` only after Professor Ivan confirms static replay
as the evaluation protocol and the FinVault tool policy is reviewed. The job writes
only content-free checkpoints and artifacts under `outputs/`; vLLM request logging
is disabled.
