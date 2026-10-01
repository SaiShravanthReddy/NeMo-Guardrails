# Benchmark dataset intake

Do not place raw CNFinBench or FinVault data in Git. After receiving a dataset,
record its source, license, version, archive checksum, extraction procedure, split
definitions, and official scorer revision. Generate a content-free first manifest:

```bash
uv run --locked python scripts/inspect_dataset.py /path/to/data.jsonl
```

The generic intake utility validates JSON/JSONL syntax and reports only filename,
SHA-256, byte size, record count, and observed top-level keys. Dataset-specific
adapters must preserve the official conversation, tool, sandbox, and scoring
protocol. They cannot be completed until the exact supplied exports are inspected.

## Supplied export semantics

The converter source in the adjacent AgentAuditor-ASSEBench workspace establishes
the following meanings for the supplied files:

- `cnfinbench-pooled`: label `0` is safe and label `1` is unsafe. The converter uses
  HICS with `high_safe` polarity and a threshold of 70: scores at or above 70 become
  safe. The export contains completed 24-turn conversations.
- `finvault-v5-fixed-full`: label `1` means `outcome == attack_success`; label `0`
  includes both benign cases and defended attacks. Agent actions are tool calls and
  environment messages are the preceding tool results. The final tool consequence
  is not present in the converted conversation.

These labels answer completed-interaction safety questions. They are not identical
to a runtime guardrail's question of whether an attack attempt or dangerous request
should be intercepted. In particular, naively treating every guardrail detection in
a defended FinVault attack as a false positive would be invalid. Before the final
evaluation, choose and record one or both of these tasks:

1. Outcome safety: use `finvault-v5-fixed-full` and judge whether the completed agent
   behavior resulted in an unsafe outcome.
2. Runtime attack interception: derive the documented benign-versus-malicious view,
   where benign is label `0` and both defended and successful attacks are label `1`.

Never silently relabel the full export. A derived view needs its own manifest and
must preserve the source case ID and original outcome.
