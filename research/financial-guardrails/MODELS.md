# Local model decision

The default profile uses deterministic rules and runs on CPU without model weights.
Two optional models are pinned in `models/local_models.yml` after reviewing their
public model cards on 2026-09-23.

## Prompt injection

`protectai/deberta-v3-base-prompt-injection-v2` is selected because it is a focused
binary injection classifier, uses the Apache-2.0 license, has about 0.2 billion
parameters, and provides a 738 MB safetensors file. It is English-focused. It can
run on CPU for small tests or on one L4 for throughput. Review the licenses of its
training datasets before redistribution or commercial use.

Model card: https://huggingface.co/protectai/deberta-v3-base-prompt-injection-v2

## Content safety

`Qwen/Qwen3Guard-Gen-0.6B` is selected for optional semantic moderation because its
model card lists Apache-2.0, 119-language support, input/output moderation, and
explicit safety categories including jailbreak, PII, violence, illegal acts, and
self-harm. The card currently reports 0.8 billion BF16 parameters. One 24 GB L4 is
ample for the raw weights and normal inference overhead; actual peak memory and
throughput must be measured on `hpg-turin` before a benchmark run.

Model card: https://huggingface.co/Qwen/Qwen3Guard-Gen-0.6B

The generative safety model is preferred over a general assistant acting as a judge
because it has a constrained moderation output. The parser still rejects missing or
unknown labels. Neither model is allowed to decide user identity, permission, or
transaction authorization.

No weights were downloaded and no inference result is claimed in this revision.
Enable a model only after downloading its pinned revision, running the local smoke
fixtures, measuring memory/latency, and calibrating it on a development split.

For the first HiPerGator check, pre-stage the locked environment and pinned weights,
create `logs/`, then submit `slurm/model-smoke.sbatch` from this directory. The job
requests one `hpg-turin` L4 for 15 minutes. Inspect the model labels, exit status,
actual GPU model/memory, and maximum resident memory before increasing resources.
