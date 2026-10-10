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

"""Report development-only risk-score threshold candidates from result artifacts."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from financial_guardrails.evaluation import BinaryMetrics, EvaluationRecord, score_binary
from financial_guardrails.results import read_evaluation_artifact


@dataclass(frozen=True)
class ThresholdCandidate:
    """One operating point derived from retained attack-attempt risk scores."""

    threshold: float
    metrics: BinaryMetrics


def _candidates(records: Sequence[EvaluationRecord]) -> tuple[ThresholdCandidate, ...]:
    """Return score-derived attack-attempt operating points without changing artifacts."""
    if not records:
        raise ValueError("artifact has no records")
    if any(record.prediction is None or record.risk_score is None for record in records):
        raise ValueError("threshold analysis requires completed records with risk scores")
    positive_labels = {record.positive_label for record in records}
    if len(positive_labels) != 1:
        raise ValueError("records must have one positive label")
    positive_label = positive_labels.pop()
    labels = [record.label for record in records]
    scores = [record.risk_score for record in records]
    return tuple(
        ThresholdCandidate(
            threshold=threshold,
            metrics=score_binary(
                labels,
                [score >= threshold for score in scores],
                positive_label=positive_label,
            ),
        )
        for threshold in sorted(set(scores), reverse=True)
    )


def _select_candidate(candidates: Sequence[ThresholdCandidate], maximum_fpr: float) -> ThresholdCandidate | None:
    """Select the highest-recall operating point within a false-positive-rate cap."""
    eligible = [
        candidate
        for candidate in candidates
        if candidate.metrics.false_positive_rate is not None and candidate.metrics.false_positive_rate <= maximum_fpr
    ]
    if not eligible:
        return None
    return max(
        eligible,
        key=lambda candidate: (
            candidate.metrics.recall if candidate.metrics.recall is not None else -1.0,
            -(candidate.metrics.false_positive_rate or 0.0),
            candidate.metrics.precision if candidate.metrics.precision is not None else -1.0,
            candidate.threshold,
        ),
    )


def _format(value: float | None) -> str:
    return "unavailable" if value is None else f"{value:.1%}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument(
        "--fpr-cap",
        action="append",
        type=float,
        default=None,
        help="Maximum false-positive rate; repeatable. Defaults to 0.01, 0.05, and 0.10.",
    )
    args = parser.parse_args()
    caps = args.fpr_cap or [0.01, 0.05, 0.10]
    if any(not 0 <= cap <= 1 for cap in caps):
        raise ValueError("--fpr-cap must be between 0 and 1")

    artifact = read_evaluation_artifact(args.artifact)
    candidates = _candidates(artifact.records)
    run = f"{artifact.manifest.dataset_key} / {artifact.manifest.backend} / {artifact.manifest.judge_mode}"
    print("# Risk-score threshold candidates")
    print()
    print("These are retrospective candidates from retained attack-attempt scores. They do not change verdicts.")
    print()
    print("| Run | FPR cap | Threshold | Recall | Precision | Observed FPR |")
    print("| --- | ---: | ---: | ---: | ---: | ---: |")
    for cap in caps:
        candidate = _select_candidate(candidates, cap)
        if candidate is None:
            print(f"| {run} | {_format(cap)} | unavailable | unavailable | unavailable | unavailable |")
            continue
        metrics = candidate.metrics
        print(
            f"| {run} | {_format(cap)} | {candidate.threshold:.3f} | {_format(metrics.recall)} | "
            f"{_format(metrics.precision)} | {_format(metrics.false_positive_rate)} |"
        )


if __name__ == "__main__":
    main()
