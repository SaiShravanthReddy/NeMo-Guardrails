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

from financial_guardrails.datasets import BenchmarkCase, BenchmarkMessage
from financial_guardrails.splits import assign_nonfinal_cross_validation_folds, assign_splits


def _case(case_id, group):
    return BenchmarkCase(
        dataset_key="cnfinbench-pooled",
        case_id=case_id,
        label=0,
        messages=(BenchmarkMessage(role="user", kind="message", content="ok", original_role="user", turn_index=0),),
        metadata={"sidecar": {"cnfinbench_id": group}},
    )


def test_splits_are_deterministic_and_group_disjoint():
    cases = [_case("a", "shared"), _case("b", "shared"), _case("c", "other")]
    first = assign_splits(cases)
    assert first == assign_splits(reversed(cases))[::-1]
    assert first[0].split == first[1].split


def test_splits_target_the_confirmed_40_20_20_20_allocation():
    cases = [_case(str(index), str(index)) for index in range(10)]

    assignments = assign_splits(cases)

    counts = {
        split: sum(item.split == split for item in assignments)
        for split in ("development", "calibration", "pilot", "final")
    }
    assert counts == {"development": 4, "calibration": 2, "pilot": 2, "final": 2}


def test_cross_validation_preserves_final_holdout_and_source_groups():
    cases = [_case(str(index), str(index // 2)) for index in range(20)]
    split_assignments = assign_splits(cases)
    assignments = assign_nonfinal_cross_validation_folds(cases)

    final_ids = {item.case_id for item in split_assignments if item.split == "final"}
    assert {item.case_id for item in assignments}.isdisjoint(final_ids)
    assert len(assignments) == len(cases) - len(final_ids)
    assert len({item.fold for item in assignments}) == 4
    folds_by_group = {}
    for assignment in assignments:
        folds_by_group.setdefault(assignment.group_id, set()).add(assignment.fold)
    assert all(len(folds) == 1 for folds in folds_by_group.values())
