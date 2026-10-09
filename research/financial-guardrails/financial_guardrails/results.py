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

"""Atomic, content-free result artifacts for reproducible evaluations."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from financial_guardrails.evaluation import (
    ConfidenceInterval,
    EvaluationRecord,
    MetricBundle,
    score_slices,
    summarize_records,
)

Scalar = str | int | float | bool | None


class ExperimentManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    run_id: str = Field(min_length=1)
    started_at: datetime
    completed_at: datetime
    code_commit: str = Field(min_length=7)
    dataset_key: str = Field(min_length=1)
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    metadata_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_records: int = Field(ge=1)
    case_limit: int | None = Field(default=None, ge=1)
    case_selection_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    cross_validation_fold: int | None = Field(default=None, ge=0)
    policy_id: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    policy_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    judge_policy_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    benchmark_policy_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    backend: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    model_revision: str | None = None
    judge_mode: Literal["rules_only", "all_events", "rules_first_cascade"]
    positive_label: Literal[0, 1]
    decision_threshold: float | None = Field(default=None, ge=0, le=1)
    generation_settings: dict[str, JsonValue] = Field(default_factory=dict)
    software_versions: dict[str, str] = Field(default_factory=dict)
    hardware: dict[str, Scalar] = Field(default_factory=dict)
    pricing_usd_per_million_tokens: dict[str, float] = Field(default_factory=dict)
    bootstrap_iterations: int = Field(default=1000, ge=100)
    bootstrap_confidence_level: float = Field(default=0.95, gt=0, lt=1)
    bootstrap_seed: int = 0
    bootstrap_group_slice_key: str | None = None
    inference_elapsed_seconds: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_times(self):
        if self.started_at.tzinfo is None or self.completed_at.tzinfo is None:
            raise ValueError("manifest timestamps must include a timezone")
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at")
        return self


class EvaluationArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest: ExperimentManifest
    records: tuple[EvaluationRecord, ...]
    metrics: MetricBundle
    confidence_intervals: dict[str, ConfidenceInterval]
    slice_metrics: dict[str, dict[str, MetricBundle]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_records(self):
        if len(self.records) != self.manifest.expected_records:
            raise ValueError("artifact record count does not match the manifest")
        if any(record.dataset_key != self.manifest.dataset_key for record in self.records):
            raise ValueError("artifact contains a record from another dataset")
        if any(record.positive_label != self.manifest.positive_label for record in self.records):
            raise ValueError("artifact positive labels do not match the manifest")
        elapsed = self.manifest.inference_elapsed_seconds
        if elapsed is None:
            elapsed = (self.manifest.completed_at - self.manifest.started_at).total_seconds()
        if self.metrics != summarize_records(self.records, run_elapsed_seconds=elapsed):
            raise ValueError("artifact metrics do not match its records")
        for slice_key, metrics_by_value in self.slice_metrics.items():
            if metrics_by_value != score_slices(self.records, slice_key):
                raise ValueError("artifact slice metrics do not match its records")
        points = {
            "accuracy": self.metrics.binary.accuracy,
            "precision": self.metrics.binary.precision,
            "recall": self.metrics.binary.recall,
            "specificity": self.metrics.binary.specificity,
            "f1": self.metrics.binary.f1,
            "balanced_accuracy": self.metrics.binary.balanced_accuracy,
            "matthews_correlation": self.metrics.binary.matthews_correlation,
            "auroc": self.metrics.ranking.auroc,
            "auprc": self.metrics.ranking.auprc,
        }
        if any(
            name not in points or interval.point != points[name] for name, interval in self.confidence_intervals.items()
        ):
            raise ValueError("artifact confidence intervals do not match its metrics")
        return self


def write_evaluation_artifact(path: str | Path, artifact: EvaluationArtifact) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(artifact.model_dump_json(indent=2))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def read_evaluation_artifact(path: str | Path) -> EvaluationArtifact:
    return EvaluationArtifact.model_validate_json(Path(path).read_text(encoding="utf-8"))
