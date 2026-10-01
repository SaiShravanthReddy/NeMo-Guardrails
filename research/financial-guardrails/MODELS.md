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

## Selected local policy judge

`Qwen/Qwen3-8B-AWQ` is the selected general policy judge for the first local
HiPerGator deployment. Its official model card lists Apache-2.0, 8.2 billion
parameters, support for more than 100 languages and dialects, and a native 32,768
token context. The official AWQ repository is about 6.11 GB, leaving substantially
more of the L4's 24 GB memory for KV cache and the longest supplied conversations
than the 19.3 GB BF16 `Qwen/Qwen3.5-9B` repository.

Model card: https://huggingface.co/Qwen/Qwen3-8B-AWQ

The immutable model revision is
`4da05a8edb55c6046cce958586c33b61da07bb79`. The model is large enough to follow
the versioned policy and strict JSON schema,
but small enough for one `hpg-turin` L4. AWQ quantization can reduce quality, so this
is a hypothesis until structured-output, policy-following, benign-counterexample,
latency, and memory tests pass.

`Qwen/Qwen3.5-9B` is not recommended for the first run. Its BF16 repository is close
to the L4 memory limit once runtime state and long-context KV cache are included, and
CNFinBench's supplied labels were already produced using Qwen3.5-9B. Reusing it as
the guardrail judge would increase model-family correlation with that benchmark's
reference labels.

No weights were downloaded and no inference result is claimed in this revision.
Enable a model only after downloading its pinned revision, running the local smoke
fixtures, measuring memory/latency, and calibrating it on a development split.

For the first HiPerGator policy-judge check, follow `JUDGE_RUNBOOK.md` and submit
`slurm/judge-preflight.sbatch`. The existing `slurm/model-smoke.sbatch` checks the
specialized moderation classifier and is a separate experiment.

## Selected NaviGator policy judge

`gpt-oss-120b` is the selected hosted judge. UF lists it as a locally hosted
NaviGator model that permits open, sensitive, and restricted data, exposes an
OpenAI-compatible chat-completions endpoint, supports a 128,000-token context, and
costs $0.06 per million input tokens and $0.15 per million output tokens as checked
on 2026-10-01. Its weights are Apache-2.0. The live team allowlist, successful
structured response, actual token accounting, rate limits, and remaining budget
still require a real preflight before benchmark data is sent.

Model documentation: https://docs.ai.it.ufl.edu/docs/navigator_models/models/oai-gpt-oss-120b/

This model is preferable to `gpt-oss-20b` for the primary hosted condition because
the larger model has more capacity for policy following, long financial dialogues,
and ambiguous authorization decisions. That is a selection rationale, not a result;
fixture and pilot measurements must confirm it. The 20B model remains a contingency
only if the selected model fails availability or budget gates, and changing models
requires a new experiment manifest.

Both selected judges use `financial_guardrails/judge_backends.py` and the declarative
settings in `models/judge_backends.yml`. The shared path prevents backend-specific
policy or parser changes. See `JUDGE_RUNBOOK.md` for the matched experiment matrix
and preflight commands.
