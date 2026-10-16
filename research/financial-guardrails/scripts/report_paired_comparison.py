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

"""Render a content-free paired comparison between two evaluation artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path

from financial_guardrails.evaluation import PairedComparison, compare_paired
from financial_guardrails.results import EvaluationArtifact, read_evaluation_artifact


def render_comparison(
    baseline: EvaluationArtifact,
    candidate: EvaluationArtifact,
    comparison: PairedComparison,
) -> str:
    if baseline.manifest.dataset_key != candidate.manifest.dataset_key:
        raise ValueError("artifacts must use the same dataset")
    rows = [
        ("Matched completed cases", comparison.matched),
        ("Decision agreement", _percent(comparison.agreement_rate)),
        ("Cohen's kappa", _number(comparison.cohens_kappa)),
        ("Baseline-only interventions", comparison.first_only_detections),
        ("Candidate-only interventions", comparison.second_only_detections),
        ("McNemar exact p-value", _number(comparison.mcnemar_exact_p_value)),
    ]
    deltas = comparison.metric_deltas_second_minus_first
    metric_rows = [
        (name.replace("_", " "), _percent(deltas.get(name)))
        for name in ("precision", "recall", "f1", "balanced_accuracy")
    ]
    return "\n".join(
        (
            "# Paired Version 1 / Version 2 comparison",
            "",
            f"Dataset: `{baseline.manifest.dataset_key}`",
            "",
            "| Field | Value |",
            "| --- | ---: |",
            *(f"| {name} | {value} |" for name, value in rows),
            "",
            "## Candidate minus baseline",
            "",
            "| Metric | Delta |",
            "| --- | ---: |",
            *(f"| {name} | {value} |" for name, value in metric_rows),
            "",
            "The comparison excludes detector-error records and does not replace either standalone report.",
        )
    )


def _percent(value: float | None) -> str:
    return "unavailable" if value is None else f"{value * 100:.1f}%"


def _number(value: float | None) -> str:
    return "unavailable" if value is None else f"{value:.4f}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    baseline = read_evaluation_artifact(args.baseline)
    candidate = read_evaluation_artifact(args.candidate)
    print(render_comparison(baseline, candidate, compare_paired(baseline.records, candidate.records)))


if __name__ == "__main__":
    main()
