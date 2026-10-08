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

"""Print protocol-defined Markdown tables from content-free result artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path

from financial_guardrails.reporting import render_evaluation_report
from financial_guardrails.results import read_evaluation_artifact


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", nargs="+", type=Path)
    args = parser.parse_args()
    artifacts = [read_evaluation_artifact(path) for path in args.artifacts]
    runs = [
        (
            f"{artifact.manifest.dataset_key} / {artifact.manifest.backend} / {artifact.manifest.judge_mode}",
            artifact.metrics,
        )
        for artifact in artifacts
    ]
    print(render_evaluation_report(runs))


if __name__ == "__main__":
    main()
