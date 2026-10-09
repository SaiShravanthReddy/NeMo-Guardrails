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

"""Print retained attack-attempt bootstrap confidence intervals from result artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path

from financial_guardrails.results import read_evaluation_artifact

_METRICS = ("precision", "recall", "f1", "balanced_accuracy", "auroc", "auprc")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", nargs="+", type=Path)
    args = parser.parse_args()
    print("# Attack-attempt bootstrap confidence intervals")
    print()
    print("| Run | Metric | Point | 95% CI | Valid resamples |")
    print("| --- | --- | ---: | ---: | ---: |")
    for path in args.artifacts:
        artifact = read_evaluation_artifact(path)
        run = f"{artifact.manifest.dataset_key} / {artifact.manifest.backend} / {artifact.manifest.judge_mode}"
        for metric in _METRICS:
            interval = artifact.confidence_intervals[metric]
            point = _format(interval.point)
            bounds = (
                "unavailable"
                if interval.lower is None or interval.upper is None
                else f"[{interval.lower:.3f}, {interval.upper:.3f}]"
            )
            print(f"| {run} | {metric} | {point} | {bounds} | {interval.valid_resamples} |")


def _format(value: float | None) -> str:
    return "unavailable" if value is None else f"{value:.3f}"


if __name__ == "__main__":
    main()
