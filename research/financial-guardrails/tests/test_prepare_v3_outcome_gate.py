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

# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES.
# SPDX-License-Identifier: Apache-2.0

import pytest
from financial_guardrails.datasets import BenchmarkCase, BenchmarkMessage
from financial_guardrails.evaluation import EvaluationRecord
from financial_guardrails.schema import Decision
from scripts.prepare_v3_outcome_gate import retained_checkpoint_records, select_replay_ids, write_private_text


def _case(
    case_id: str,
    *,
    attack_success: bool = True,
    dataset_key: str = "finvault-v5-fixed-full",
) -> BenchmarkCase:
    return BenchmarkCase(
        dataset_key=dataset_key,
        case_id=case_id,
        label=1,
        messages=(
            BenchmarkMessage(
                role="assistant",
                kind="message",
                content="Response retained only in the fixture.",
                original_role="agent",
                turn_index=0,
            ),
        ),
        metadata={"evaluation": {"attack_success": attack_success}},
    )


def _record(
    case_id: str,
    *,
    score: float | None,
    outcome_error: bool,
    prediction: bool | None = False,
    dataset_key: str = "finvault-v5-fixed-full",
) -> EvaluationRecord:
    return EvaluationRecord(
        dataset_key=dataset_key,
        case_id=case_id,
        label=1,
        prediction=prediction,
        decision=Decision.ALLOW if prediction is not None else None,
        detector_error=prediction is None,
        failure_code="v3_detector_error" if prediction is None else None,
        attack_success_risk_score=score,
        outcome_score_detector_error=outcome_error,
        attack_success_detector_error=outcome_error,
        backend="hipergator",
        judge_mode="v3_rules_first_cascade",
        outcome_score_mode="enforcement_only",
        input_view="v3_clean",
    )


def test_select_replay_ids_only_uses_missing_scores_with_labeled_outcome_events():
    cases = {
        case.case_id: case
        for case in (_case("candidate-a"), _case("candidate-b"), _case("unlabeled", attack_success=False))
    }
    records = (
        _record("candidate-a", score=None, outcome_error=True),
        _record("candidate-b", score=None, outcome_error=True),
        _record("unlabeled", score=None, outcome_error=True),
        _record("attempt-failed", score=None, outcome_error=True, prediction=None),
        _record("already-scored", score=0.7, outcome_error=True),
    )

    selected = select_replay_ids(records, cases, per_fold=2)

    assert set(selected) == {"candidate-a", "candidate-b"}


def test_select_replay_ids_supports_cnfinbench_outcome_labels():
    case = _case("cnf-candidate", dataset_key="cnfinbench-pooled")
    record = _record(
        case.case_id,
        score=None,
        outcome_error=True,
        dataset_key="cnfinbench-pooled",
    )

    assert select_replay_ids((record,), {case.case_id: case}, per_fold=1) == (case.case_id,)


def test_retained_checkpoint_excludes_only_selected_and_normalizes_legacy_mode():
    records = (_record("replay", score=None, outcome_error=True), _record("retain", score=0.7, outcome_error=False))

    retained = retained_checkpoint_records(records, {"replay"})

    assert [record.case_id for record in retained] == ["retain"]
    assert retained[0].outcome_score_mode == "score_all_outcome_events"


def test_private_text_writer_creates_private_file_and_refuses_overwrite(tmp_path):
    path = tmp_path / "private" / "ids.txt"

    write_private_text(path, "opaque-case\n")

    assert path.read_text(encoding="utf-8") == "opaque-case\n"
    assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        write_private_text(path, "replacement\n")
