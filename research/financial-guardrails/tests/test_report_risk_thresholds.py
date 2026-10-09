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

from financial_guardrails.evaluation import score_binary
from scripts.report_risk_thresholds import ThresholdCandidate, _select_candidate


def _candidate(threshold: float, labels: list[int], predictions: list[bool]) -> ThresholdCandidate:
    return ThresholdCandidate(threshold, score_binary(labels, predictions, positive_label=1))


def test_selects_highest_recall_within_fpr_cap():
    candidates = (
        _candidate(0.9, [1, 1, 0, 0], [True, False, False, False]),
        _candidate(0.8, [1, 1, 0, 0], [True, True, False, False]),
        _candidate(0.7, [1, 1, 0, 0], [True, True, True, False]),
    )

    selected = _select_candidate(candidates, 0.0)

    assert selected is not None
    assert selected.threshold == 0.8


def test_returns_none_when_no_candidate_meets_fpr_cap():
    candidates = (_candidate(0.9, [1, 0], [True, True]),)

    assert _select_candidate(candidates, 0.0) is None
