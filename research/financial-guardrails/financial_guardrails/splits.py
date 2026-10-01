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

"""Deterministic, group-disjoint benchmark splits."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict

from financial_guardrails.datasets import BenchmarkCase

SplitName = Literal["development", "calibration", "pilot", "final"]


class SplitAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    group_id: str
    split: SplitName


def benchmark_group_id(case: BenchmarkCase) -> str:
    sidecar = case.metadata.get("sidecar", {})
    field = "cnfinbench_id" if case.dataset_key == "cnfinbench-pooled" else "scenario_id"
    value = sidecar.get(field)
    if not isinstance(value, (str, int)) or str(value) == "":
        raise ValueError(f"missing grouping field: {field}")
    return f"{case.dataset_key}:{value}"


def assign_splits(cases: Iterable[BenchmarkCase], *, seed: str = "open-lakera-v1") -> tuple[SplitAssignment, ...]:
    """Assign whole source groups to 20/10/10/60 percent partitions."""
    assignments = []
    for case in cases:
        group_id = benchmark_group_id(case)
        bucket = int.from_bytes(hashlib.sha256(f"{seed}\0{group_id}".encode()).digest()[:8], "big") % 100
        split: SplitName
        if bucket < 20:
            split = "development"
        elif bucket < 30:
            split = "calibration"
        elif bucket < 40:
            split = "pilot"
        else:
            split = "final"
        assignments.append(SplitAssignment(case_id=case.case_id, group_id=group_id, split=split))
    if len({item.case_id for item in assignments}) != len(assignments):
        raise ValueError("split input contains duplicate case IDs")
    return tuple(assignments)
