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

Qwen3Guard remains a specialized moderation detector because it has a constrained
safety output. The parser rejects missing or unknown labels. It does not replace the
separate policy-reading judge required for contextual Open Lakera decisions. No
model may decide user identity, permission, or transaction authorization.

## Recommended policy judge, pending approval

`Qwen/Qwen3-8B-AWQ` is the recommended general policy judge for the first local
HiPerGator deployment. Its official model card lists Apache-2.0, 8.2 billion
parameters, support for more than 100 languages and dialects, and a native 32,768
token context. The official AWQ repository is about 6.11 GB, leaving substantially
more of the L4's 24 GB memory for KV cache and the longest supplied conversations
than the 19.3 GB BF16 `Qwen/Qwen3.5-9B` repository.

Model card: https://huggingface.co/Qwen/Qwen3-8B-AWQ

The model is large enough to follow the versioned policy and strict JSON schema,
but small enough for one `hpg-turin` L4. AWQ quantization can reduce quality, so this
is a hypothesis until structured-output, policy-following, benign-counterexample,
latency, and memory tests pass. The revision must be pinned after approval and before
download.

`Qwen/Qwen3.5-9B` is not recommended for the first run. Its BF16 repository is close
to the L4 memory limit once runtime state and long-context KV cache are included, and
CNFinBench's supplied labels were already produced using Qwen3.5-9B. Reusing it as
the guardrail judge would increase model-family correlation with that benchmark's
reference labels.

No weights were downloaded and no inference result is claimed in this revision.
Enable a model only after downloading its pinned revision, running the local smoke
fixtures, measuring memory/latency, and calibrating it on a development split.

For the first HiPerGator check, pre-stage the locked environment and pinned weights,
create `logs/`, then submit `slurm/model-smoke.sbatch` from this directory. The job
requests one `hpg-turin` L4 for 15 minutes. Inspect the model labels, exit status,
actual GPU model/memory, and maximum resident memory before increasing resources.
