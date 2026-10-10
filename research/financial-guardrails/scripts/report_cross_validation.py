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

"""Validate and summarize four non-final cross-validation result artifacts."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
from statistics import fmean

from financial_guardrails.evaluation import EvaluationTaskMetrics
from financial_guardrails.results import EvaluationArtifact, read_evaluation_artifact

_METRICS = ("f1", "balanced_accuracy", "false_positive_rate", "auroc", "auprc")


def _configuration_identity(artifact: EvaluationArtifact) -> tuple[object, ...]:
    manifest = artifact.manifest
    return (
        manifest.dataset_key,
        manifest.backend,
        manifest.model_id,
        manifest.model_revision,
        manifest.judge_mode,
        manifest.policy_sha256,
        manifest.judge_policy_sha256,
        manifest.benchmark_policy_sha256,
        manifest.decision_threshold,
    )


def _validate_artifacts(artifacts: Sequence[EvaluationArtifact]) -> None:
    """Ensure artifacts are four disjoint folds of one frozen configuration."""
    if len(artifacts) != 4:
        raise ValueError("cross-validation reporting requires exactly four artifacts")
    if len({_configuration_identity(artifact) for artifact in artifacts}) != 1:
        raise ValueError("cross-validation artifacts use different configurations")
    folds = {artifact.manifest.cross_validation_fold for artifact in artifacts}
    if folds != {0, 1, 2, 3}:
        raise ValueError("cross-validation artifacts must contain folds 0, 1, 2, and 3 exactly once")
    case_ids = [record.case_id for artifact in artifacts for record in artifact.records]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("cross-validation artifacts contain duplicate case IDs")
    if any(record.slices.get("split") == "final" for artifact in artifacts for record in artifact.records):
        raise ValueError("cross-validation artifacts must exclude final-split records")


def _format_percent(value: float | None) -> str:
    return "unavailable" if value is None else f"{value * 100:.1f}%"


def _task_table(title: str, artifacts: Sequence[EvaluationArtifact], task_name: str) -> str:
    lines = [
        f"## {title}",
        "",
        "| Fold | Cases | Coverage | F1 | Balanced accuracy | FPR | AUROC | AUPRC |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    values: dict[str, list[float]] = {metric: [] for metric in _METRICS}
    for artifact in sorted(artifacts, key=lambda item: item.manifest.cross_validation_fold or 0):
        task: EvaluationTaskMetrics = getattr(artifact.metrics, task_name)
        fold = artifact.manifest.cross_validation_fold
        if not task.available or task.binary is None or task.ranking is None:
            lines.append(
                f"| {fold} | {task.eligible_records} | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable |"
            )
            continue
        binary = task.binary
        ranking = task.ranking
        row = {
            "f1": binary.f1,
            "balanced_accuracy": binary.balanced_accuracy,
            "false_positive_rate": binary.false_positive_rate,
            "auroc": ranking.auroc,
            "auprc": ranking.auprc,
        }
        for metric, value in row.items():
            if value is not None:
                values[metric].append(value)
        lines.append(
            "| "
            + " | ".join(
                (
                    str(fold),
                    str(task.eligible_records),
                    _format_percent(binary.coverage),
                    _format_percent(row["f1"]),
                    _format_percent(row["balanced_accuracy"]),
                    _format_percent(row["false_positive_rate"]),
                    _format_percent(row["auroc"]),
                    _format_percent(row["auprc"]),
                )
            )
            + " |"
        )
    lines.extend(("", "Unweighted fold summary:", "", "| Metric | Mean | Range |", "| --- | ---: | ---: |"))
    for metric in _METRICS:
        metric_values = values[metric]
        if not metric_values:
            lines.append(f"| {metric} | unavailable | unavailable |")
            continue
        lines.append(
            f"| {metric} | {_format_percent(fmean(metric_values))} | "
            f"{_format_percent(min(metric_values))}–{_format_percent(max(metric_values))} |"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", nargs=4, type=Path)
    args = parser.parse_args()
    artifacts = [read_evaluation_artifact(path) for path in args.artifacts]
    _validate_artifacts(artifacts)
    manifest = artifacts[0].manifest
    print("# Non-final four-fold cross-validation")
    print()
    print(
        f"Configuration: `{manifest.dataset_key}` / `{manifest.backend}` / `{manifest.judge_mode}`. "
        "This is a robustness analysis and does not alter the frozen final result."
    )
    print()
    print(_task_table("Attack-attempt detection", artifacts, "attack_attempt"))
    print()
    print(_task_table("Attack-success detection", artifacts, "attack_success"))


if __name__ == "__main__":
    main()
