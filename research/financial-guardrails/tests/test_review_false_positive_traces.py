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

import pytest
from scripts.manage_false_positive_review import ReviewWorksheetRow
from scripts.review_false_positive_traces import classify


def _row():
    return ReviewWorksheetRow(
        case_id="case-1",
        decision="block",
        decision_policy_ids=("FINVAULT-TOOL-CONFIRM",),
        policy_attribution="primary",
        first_detection_surface="tool_call",
        first_detection_turn=1,
        intervention_source="deterministic_rule",
    )


@pytest.mark.parametrize(
    ("choice", "outcome", "basis"),
    (
        ("a", "allow_candidate", "read_only_or_reversible"),
        ("c", "confirmation_appropriate", "trusted_authorization_missing"),
        ("k", "keep_intervention", "real_security_concern"),
        ("m", "ambiguous", "insufficient_context"),
    ),
)
def test_classify_uses_only_fixed_content_free_values(choice, outcome, basis):
    classified = classify(_row(), choice)

    assert classified.review_outcome == outcome
    assert classified.review_basis == basis


def test_classify_rejects_unknown_choice():
    with pytest.raises(ValueError, match="a, c, k, or m"):
        classify(_row(), "x")
