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
from scripts.manage_false_positive_review import ReviewWorksheetRow, prepare, validate


def _candidate(case_id="case-1"):
    return {
        "case_id": case_id,
        "decision": "block",
        "decision_policy_ids": ["FINVAULT-TOOL-CONFIRM"],
        "policy_attribution": "primary",
        "first_detection_surface": "tool_call",
        "first_detection_turn": 1,
        "intervention_source": "deterministic_rule",
    }


def test_prepare_creates_blank_content_free_rows():
    row = prepare([_candidate()])[0]

    assert row.review_outcome is None
    assert row.review_basis is None
    assert not hasattr(row, "notes")


def test_validate_requires_all_rows_to_be_classified():
    row = prepare([_candidate()])[0]

    with pytest.raises(ValueError, match="incomplete"):
        validate([row])


def test_allow_candidate_requires_read_only_or_reversible_basis():
    with pytest.raises(ValueError, match="read_only_or_reversible"):
        ReviewWorksheetRow.model_validate(
            {
                **_candidate(),
                "review_outcome": "allow_candidate",
                "review_basis": "trusted_authorization_missing",
            }
        )


def test_validate_counts_completed_classifications():
    rows = [
        ReviewWorksheetRow.model_validate(
            {**_candidate("allow"), "review_outcome": "allow_candidate", "review_basis": "read_only_or_reversible"}
        ),
        ReviewWorksheetRow.model_validate(
            {
                **_candidate("confirm"),
                "review_outcome": "confirmation_appropriate",
                "review_basis": "trusted_authorization_missing",
            }
        ),
    ]

    assert validate(rows) == {"allow_candidate": 1, "confirmation_appropriate": 1}
