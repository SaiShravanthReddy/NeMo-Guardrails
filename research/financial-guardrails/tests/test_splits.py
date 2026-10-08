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
from financial_guardrails.splits import assign_splits


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
