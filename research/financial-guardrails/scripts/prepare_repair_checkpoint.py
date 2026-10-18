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

"""Create a content-free checkpoint that replays only detector-error cases."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from financial_guardrails.evaluation import EvaluationRecord
from financial_guardrails.results import read_evaluation_artifact


def completed_records(records: Sequence[EvaluationRecord]) -> tuple[EvaluationRecord, ...]:
    """Keep only records that are safe to resume without replaying."""
    retained = tuple(record for record in records if not record.detector_error)
    if not retained:
        raise ValueError("artifact contains no completed records to retain")
    return retained


def write_checkpoint(path: Path, records: Sequence[EvaluationRecord]) -> None:
    if path.exists():
        raise FileExistsError("repair checkpoint already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        for record in records:
            stream.write(record.model_dump_json())
            stream.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    artifact = read_evaluation_artifact(args.artifact)
    retained = completed_records(artifact.records)
    write_checkpoint(args.output, retained)
    print(
        {
            "expected_records": artifact.manifest.expected_records,
            "retained_records": len(retained),
            "replay_cases": artifact.manifest.expected_records - len(retained),
            "output": str(args.output),
        }
    )


if __name__ == "__main__":
    main()
