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

from financial_guardrails.evaluation import EvaluationRecord, compare_paired
from financial_guardrails.schema import Decision
from scripts.report_paired_comparison import render_comparison


def _artifact(dataset_key: str = "fixture"):
    manifest = SimpleNamespace(dataset_key=dataset_key)
    records = (
        EvaluationRecord(
            dataset_key=dataset_key,
            case_id="unsafe",
            label=1,
            prediction=True,
            decision=Decision.BLOCK,
            backend="fixture",
            judge_mode="rules_first_cascade",
        ),
        EvaluationRecord(
            dataset_key=dataset_key,
            case_id="safe",
            label=0,
            prediction=False,
            decision=Decision.ALLOW,
            backend="fixture",
            judge_mode="rules_first_cascade",
        ),
    )
    return SimpleNamespace(manifest=manifest, records=records)


def test_paired_comparison_report_includes_matched_cases_and_metric_deltas():
    baseline = _artifact()
    candidate = _artifact()

    report = render_comparison(baseline, candidate, compare_paired(baseline.records, candidate.records))

    assert "# Paired Version 1 / Version 2 comparison" in report
    assert "| Matched completed cases | 2 |" in report
    assert "| f1 | 0.0% |" in report


def test_paired_comparison_rejects_different_datasets():
    baseline = _artifact()
    candidate = _artifact("other")

    try:
        render_comparison(baseline, candidate, compare_paired(baseline.records, candidate.records))
    except ValueError as error:
        assert str(error) == "artifacts must use the same dataset"
    else:
        raise AssertionError("different datasets should fail")
