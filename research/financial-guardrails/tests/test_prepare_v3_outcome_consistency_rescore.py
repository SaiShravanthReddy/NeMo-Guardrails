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

import pytest
from financial_guardrails.datasets import BenchmarkCase, BenchmarkMessage
from financial_guardrails.evaluation import EvaluationRecord
from financial_guardrails.schema import Decision
from scripts.prepare_v3_outcome_consistency_rescore import (
    checkpoint_records,
    prior_scored_ids,
    record_configuration_is_valid,
    sample_rescore_ids,
)


def _case(case_id: str, *, attack_success: bool | None = True) -> BenchmarkCase:
    return BenchmarkCase(
        dataset_key="cnfinbench-pooled",
        case_id=case_id,
        label=1,
        messages=(
            BenchmarkMessage(
                role="assistant",
                kind="message",
                content="An observed response.",
                original_role="agent",
                turn_index=0,
            ),
        ),
        metadata={"evaluation": {"attack_success": attack_success}},
    )


def _record(case_id: str, score: float | None) -> EvaluationRecord:
    return EvaluationRecord(
        dataset_key="cnfinbench-pooled",
        case_id=case_id,
        label=1,
        prediction=True,
        decision=Decision.BLOCK,
        detector_error=False,
        backend="hipergator",
        judge_mode="v3_rules_first_cascade",
        outcome_score_mode="score_all_outcome_events",
        input_view="v3_clean",
        attack_success_risk_score=score,
    )


def test_prior_scored_ids_selects_only_labeled_scores_to_rescore():
    cases = {
        case.case_id: case
        for case in (
            _case("prior-score"),
            _case("missing-score"),
            _case("unlabeled", attack_success=None),
        )
    }
    original = (_record("prior-score", 0.8), _record("missing-score", None), _record("unlabeled", 0.3))
    repaired = (_record("prior-score", 0.8), _record("missing-score", 0.7), _record("unlabeled", 0.3))

    assert prior_scored_ids(original, repaired, cases) == ("prior-score",)


def test_prior_scored_ids_rejects_unmatched_artifact_records():
    with pytest.raises(ValueError, match="case IDs must match"):
        prior_scored_ids((_record("original", 0.8),), (_record("different", 0.8),), {})


def test_prior_scored_ids_rejects_repaired_case_without_score():
    case = _case("prior-score")
    with pytest.raises(ValueError, match="no outcome score"):
        prior_scored_ids((_record("prior-score", 0.8),), (_record("prior-score", None),), {case.case_id: case})


def test_checkpoint_records_retain_every_nonselected_repaired_case():
    records = (_record("replay", 0.8), _record("retain-a", 0.2), _record("retain-b", 0.7))

    assert [record.case_id for record in checkpoint_records(records, {"replay"})] == ["retain-a", "retain-b"]


def test_checkpoint_records_rejects_ids_not_in_repaired_artifact():
    with pytest.raises(ValueError, match="does not match"):
        checkpoint_records((_record("present", 0.8),), {"absent"})


def test_legacy_score_mode_is_accepted_only_for_original_records():
    record = _record("historical", 0.8).model_copy(update={"outcome_score_mode": "enforcement_only"})

    assert record_configuration_is_valid(
        record, dataset="cnfinbench-pooled", backend="hipergator", original_artifact=True
    )
    assert not record_configuration_is_valid(
        record, dataset="cnfinbench-pooled", backend="hipergator", original_artifact=False
    )


def test_rescore_sample_is_deterministic_and_respects_requested_size():
    case_ids = ("case-a", "case-b", "case-c", "case-d")

    assert sample_rescore_ids(case_ids, 2) == sample_rescore_ids(case_ids, 2)
    assert len(sample_rescore_ids(case_ids, 2)) == 2
    assert sample_rescore_ids(case_ids, None) == case_ids
    with pytest.raises(ValueError, match="fewer than the requested"):
        sample_rescore_ids(case_ids, 5)
