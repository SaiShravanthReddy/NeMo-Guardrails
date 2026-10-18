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
from financial_guardrails.evaluation import EvaluationRecord
from financial_guardrails.schema import Decision
from scripts.prepare_repair_checkpoint import completed_records, write_checkpoint


def _record(case_id: str, *, detector_error: bool) -> EvaluationRecord:
    return EvaluationRecord(
        dataset_key="fixture",
        case_id=case_id,
        label=1,
        prediction=None if detector_error else True,
        decision=Decision.REQUIRE_CONFIRMATION if detector_error else Decision.BLOCK,
        detector_error=detector_error,
        failure_code="detector_timeout" if detector_error else None,
        backend="fixture",
        judge_mode="rules_first_cascade",
    )


def test_completed_records_removes_detector_errors():
    records = completed_records((_record("complete", detector_error=False), _record("failed", detector_error=True)))

    assert [record.case_id for record in records] == ["complete"]


def test_completed_records_rejects_an_artifact_with_only_failures():
    with pytest.raises(ValueError, match="no completed records"):
        completed_records((_record("failed", detector_error=True),))


def test_write_checkpoint_refuses_to_overwrite(tmp_path):
    path = tmp_path / "repair.jsonl"
    write_checkpoint(path, (_record("complete", detector_error=False),))

    assert len(path.read_text(encoding="utf-8").splitlines()) == 1
    with pytest.raises(FileExistsError, match="already exists"):
        write_checkpoint(path, (_record("complete", detector_error=False),))
