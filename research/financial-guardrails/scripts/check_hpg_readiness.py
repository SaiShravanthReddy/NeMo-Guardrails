# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Check files and environment required before submitting HiPerGator jobs."""

from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path

from financial_guardrails.datasets import cnfinbench_adapter, finvault_adapter
from financial_guardrails.judge_backends import load_judge_backend_registry
from financial_guardrails.replay import parse_finvault_tool_call

EXPECTED = {
    "cnfinbench-pooled.json": "9762ddbb3b4504cc523688956e3ecfdfa25bf5eb355949c5c5762aff5dead908",
    "finvault-v5-fixed-full.json": "743ff07b0604fb55094046a68b5c3afa327f2b3c31c3c80fab3737b7f033cbe6",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--require-hpg-tools", action="store_true")
    args = parser.parse_args()
    for filename, expected in EXPECTED.items():
        path = args.data_dir / filename
        if not path.is_file() or _sha256(path) != expected:
            raise SystemExit(f"FAIL: missing or checksum mismatch: {filename}")
        metadata = path.with_suffix(".json.meta.json")
        if not metadata.is_file():
            raise SystemExit(f"FAIL: missing metadata: {metadata.name}")
    cnfinbench = tuple(cnfinbench_adapter(args.data_dir).cases())
    finvault = tuple(finvault_adapter(args.data_dir).cases())
    tool_calls = 0
    for case in finvault:
        for message in case.messages:
            if message.kind == "tool_call":
                parse_finvault_tool_call(message.content)
                tool_calls += 1
    spec = load_judge_backend_registry().backends["hipergator"]
    if spec.model != "Qwen/Qwen3-8B-AWQ" or not spec.revision:
        raise SystemExit("FAIL: HiPerGator model or immutable revision is not pinned")
    for path in (Path("slurm/judge-preflight.sbatch"), Path("slurm/run-evaluation.sbatch")):
        if not path.is_file():
            raise SystemExit(f"FAIL: missing job script: {path}")
    if args.require_hpg_tools:
        for executable in ("sbatch", "nvidia-smi"):
            if shutil.which(executable) is None:
                raise SystemExit(f"FAIL: required HiPerGator command is unavailable: {executable}")
        if not Path(".venv-vllm/bin/vllm").is_file():
            raise SystemExit("FAIL: .venv-vllm/bin/vllm is unavailable")
    print(
        f"READY: {len(cnfinbench)} CNFinBench cases, {len(finvault)} FinVault cases, "
        f"{tool_calls} safe-parsed tool calls, pinned model {spec.model}@{spec.revision}"
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    main()
