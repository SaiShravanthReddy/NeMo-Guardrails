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
from collections import defaultdict
from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict

from financial_guardrails.datasets import BenchmarkCase

SplitName = Literal["development", "calibration", "pilot", "final"]
_SPLIT_TARGETS: tuple[tuple[SplitName, float], ...] = (
    ("development", 0.4),
    ("calibration", 0.2),
    ("pilot", 0.2),
    ("final", 0.2),
)


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
    """Assign whole source groups to 40/20/20/20 percent partitions."""
    selected_cases = tuple(cases)
    if len({case.case_id for case in selected_cases}) != len(selected_cases):
        raise ValueError("split input contains duplicate case IDs")
    groups: dict[str, list[BenchmarkCase]] = defaultdict(list)
    for case in selected_cases:
        groups[benchmark_group_id(case)].append(case)
    targets = _target_counts(len(selected_cases))
    assigned_counts = {split: 0 for split, _fraction in _SPLIT_TARGETS}
    group_splits: dict[str, SplitName] = {}
    for group_id, group_cases in sorted(groups.items(), key=lambda item: _group_sort_key(seed, item[0])):
        split = max(
            assigned_counts,
            key=lambda candidate: (targets[candidate] - assigned_counts[candidate], -_split_order(candidate)),
        )
        group_splits[group_id] = split
        assigned_counts[split] += len(group_cases)
    return tuple(
        SplitAssignment(case_id=case.case_id, group_id=group_id, split=group_splits[group_id])
        for case in selected_cases
        for group_id in (benchmark_group_id(case),)
    )


def _target_counts(total: int) -> dict[SplitName, int]:
    targets = {split: int(total * fraction) for split, fraction in _SPLIT_TARGETS}
    targets["final"] += total - sum(targets.values())
    return targets


def _group_sort_key(seed: str, group_id: str) -> tuple[bytes, str]:
    return hashlib.sha256(f"{seed}\0{group_id}".encode()).digest(), group_id


def _split_order(split: SplitName) -> int:
    return next(index for index, (name, _fraction) in enumerate(_SPLIT_TARGETS) if name == split)
