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

from datetime import UTC, datetime, timedelta

import pytest
from financial_guardrails.evaluation import EvaluationRecord, bootstrap_confidence_intervals, summarize_records
from financial_guardrails.results import (
    EvaluationArtifact,
    ExperimentManifest,
    read_evaluation_artifact,
    write_evaluation_artifact,
)
from financial_guardrails.schema import Decision
from pydantic import ValidationError


def records():
    return (
        EvaluationRecord(
            dataset_key="fixture",
            case_id="unsafe",
            label=1,
            prediction=True,
            decision=Decision.BLOCK,
            risk_score=0.9,
            backend="fixture",
            judge_mode="all_events",
        ),
        EvaluationRecord(
            dataset_key="fixture",
            case_id="safe",
            label=0,
            prediction=False,
            decision=Decision.ALLOW,
            risk_score=0.1,
            backend="fixture",
            judge_mode="all_events",
        ),
    )


def manifest():
    started = datetime(2026, 10, 1, tzinfo=UTC)
    return ExperimentManifest(
        run_id="fixture-run",
        started_at=started,
        completed_at=started + timedelta(seconds=1),
        code_commit="abcdef1",
        dataset_key="fixture",
        dataset_sha256="a" * 64,
        metadata_sha256="b" * 64,
        expected_records=2,
        policy_id="open-lakera",
        policy_version="1.0.0",
        policy_sha256="c" * 64,
        judge_policy_sha256="d" * 64,
        backend="fixture",
        model_id="fixture-model",
        judge_mode="all_events",
        positive_label=1,
        decision_threshold=0.5,
        bootstrap_iterations=100,
    )


def test_artifact_round_trip_is_atomic_and_content_free(tmp_path):
    case_records = records()
    artifact = EvaluationArtifact(
        manifest=manifest(),
        records=case_records,
        metrics=summarize_records(case_records, run_elapsed_seconds=1),
        confidence_intervals=bootstrap_confidence_intervals(case_records, iterations=100),
    )
    destination = tmp_path / "result.json"

    write_evaluation_artifact(destination, artifact)

    assert read_evaluation_artifact(destination) == artifact
    assert not list(tmp_path.glob(".result.json.*.tmp"))
    assert "content" not in destination.read_text()


def test_artifact_rejects_incomplete_record_sets():
    case_records = records()
    with pytest.raises(ValidationError, match="record count"):
        EvaluationArtifact(
            manifest=manifest(),
            records=case_records[:1],
            metrics=summarize_records(case_records[:1]),
            confidence_intervals={},
        )


def test_manifest_requires_timezone_aware_timestamps():
    values = manifest().model_dump()
    values["started_at"] = datetime(2026, 10, 1)

    with pytest.raises(ValidationError, match="timezone"):
        ExperimentManifest.model_validate(values)
