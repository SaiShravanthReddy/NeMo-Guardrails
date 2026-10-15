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

from scripts.export_false_positive_review import review_candidates


def _record(*, case_id: str, label: int, prediction: bool | None, primary_policy_ids=(), policy_ids=(), rule=True):
    return SimpleNamespace(
        case_id=case_id,
        label=label,
        prediction=prediction,
        decision=SimpleNamespace(value="block"),
        primary_policy_ids=primary_policy_ids,
        policy_ids=policy_ids,
        surface=SimpleNamespace(value="tool_result"),
        first_detection_turn=3,
        rules_intervened=rule,
    )


def test_exports_only_completed_normal_interventions_in_deterministic_order():
    records = (
        _record(case_id="z-case", label=0, prediction=True, primary_policy_ids=("TOOL-CONFIRM",)),
        _record(case_id="attack", label=1, prediction=True),
        _record(case_id="allow", label=0, prediction=False),
        _record(case_id="a-case", label=0, prediction=True, policy_ids=("INJ-01",), rule=False),
    )

    assert review_candidates(records) == [
        {
            "case_id": "a-case",
            "decision": "block",
            "decision_policy_ids": ["INJ-01"],
            "policy_attribution": "matched_fallback",
            "first_detection_surface": "tool_result",
            "first_detection_turn": 3,
            "intervention_source": "judge_only",
        },
        {
            "case_id": "z-case",
            "decision": "block",
            "decision_policy_ids": ["TOOL-CONFIRM"],
            "policy_attribution": "primary",
            "first_detection_surface": "tool_result",
            "first_detection_turn": 3,
            "intervention_source": "deterministic_rule",
        },
    ]
