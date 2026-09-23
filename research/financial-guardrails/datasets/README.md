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
