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

from types import SimpleNamespace

from financial_guardrails.datasets import BenchmarkCase
from scripts.run_v3_static_evaluation import _select_cases


def _case(case_id, scenario_id):
    return BenchmarkCase(
        dataset_key="finvault-v5-fixed-full",
        case_id=case_id,
        label=1,
        messages=(),
        metadata={"sidecar": {"scenario_id": scenario_id}},
    )


def test_v3_selection_uses_group_disjoint_cv_assignment_without_review_manifest():
    cases = tuple(_case(f"case-{index}", f"scenario-{index}") for index in range(8))
    args = SimpleNamespace(cv_fold=0, split="development", reviewed_groups_file=None)
    adapter = SimpleNamespace()

    selected, name, reviewed_sha = _select_cases(args, cases, adapter)

    assert name == "cv0"
    assert selected
    assert reviewed_sha is None
