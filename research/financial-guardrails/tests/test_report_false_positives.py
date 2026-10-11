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

from __future__ import annotations

from types import SimpleNamespace

from scripts.report_false_positives import false_positives, render


def _record(*, label: int, prediction: bool | None, rule: bool, policy: tuple[str, ...] = ()):
    return SimpleNamespace(
        label=label,
        prediction=prediction,
        rules_intervened=rule,
        decision="block",
        primary_policy_ids=policy,
        surface="tool_call",
    )


def test_selects_only_completed_normal_interventions():
    records = (
        _record(label=0, prediction=True, rule=True),
        _record(label=0, prediction=False, rule=True),
        _record(label=1, prediction=True, rule=False),
        _record(label=0, prediction=None, rule=False),
    )

    assert false_positives(records) == (records[0],)


def test_render_groups_by_primary_policy_and_source():
    report = render(
        (
            _record(label=0, prediction=True, rule=True, policy=("TOOL-CONFIRM",)),
            _record(label=0, prediction=True, rule=False, policy=("INJ-01",)),
        )
    )

    assert "| TOOL-CONFIRM | 1 |" in report
    assert "| INJ-01 | 1 |" in report
    assert "| deterministic_rule | 1 |" in report
    assert "| judge_only | 1 |" in report
