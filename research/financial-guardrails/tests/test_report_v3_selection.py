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

import pytest
from financial_guardrails.datasets import BenchmarkCase
from financial_guardrails.evaluation import EvaluationRecord
from scripts.report_v3_selection import _attach_source_groups, _matched_records, _validate_artifact_dataset


def _case(case_id, scenario_id):
    return BenchmarkCase(
        dataset_key="finvault-v5-fixed-full",
        case_id=case_id,
        label=0,
        messages=(),
        metadata={"sidecar": {"scenario_id": scenario_id}},
    )


def _record(case_id, prediction):
    return EvaluationRecord(
        dataset_key="finvault-v5-fixed-full",
        case_id=case_id,
        label=0,
        prediction=prediction,
        backend="fixture",
        judge_mode="fixture",
    )


def test_selection_report_rebuilds_groups_from_canonical_cases():
    records = (_record("case-a", True),)
    (enriched,) = _attach_source_groups(records, (_case("case-a", "scenario-a"),))

    assert enriched.slices["source_group"] == "finvault-v5-fixed-full:scenario-a"


def test_selection_report_rejects_inconsistent_source_group_or_labels():
    records = (_record("case-a", True).model_copy(update={"slices": {"source_group": "wrong"}}),)
    with pytest.raises(ValueError, match="source group"):
        _attach_source_groups(records, (_case("case-a", "scenario-a"),))

    baseline = (_record("case-a", True),)
    candidate = (_record("case-a", False).model_copy(update={"label": 1}),)
    with pytest.raises(ValueError, match="labels"):
        _matched_records(baseline, candidate)


def test_selection_report_rejects_wrong_canonical_dataset_checksums(tmp_path):
    data = tmp_path / "data.json"
    metadata = tmp_path / "metadata.json"
    data.write_text("[]", encoding="utf-8")
    metadata.write_text("{}", encoding="utf-8")
    adapter = SimpleNamespace(data_path=data, metadata_path=metadata)
    artifact = SimpleNamespace(manifest=SimpleNamespace(dataset_sha256="0" * 64, metadata_sha256="0" * 64))

    with pytest.raises(ValueError, match="data checksum"):
        _validate_artifact_dataset(artifact, adapter)
