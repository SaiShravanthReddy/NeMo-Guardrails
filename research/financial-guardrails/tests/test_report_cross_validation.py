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

from __future__ import annotations

from types import SimpleNamespace

import pytest
from scripts.report_cross_validation import _validate_artifacts


def _artifact(fold: int, case_id: str):
    manifest = SimpleNamespace(
        dataset_key="fixture",
        backend="fixture",
        model_id="fixture-model",
        model_revision="revision",
        judge_mode="rules_first_cascade",
        policy_sha256="a" * 64,
        judge_policy_sha256="b" * 64,
        benchmark_policy_sha256=None,
        decision_threshold=None,
        cross_validation_fold=fold,
    )
    return SimpleNamespace(
        manifest=manifest, records=(SimpleNamespace(case_id=case_id, slices={"split": "development"}),)
    )


def test_accepts_four_disjoint_nonfinal_folds():
    _validate_artifacts(tuple(_artifact(fold, f"case-{fold}") for fold in range(4)))


def test_rejects_duplicate_case_ids():
    artifacts = tuple(_artifact(fold, "duplicate") for fold in range(4))

    with pytest.raises(ValueError, match="duplicate case IDs"):
        _validate_artifacts(artifacts)
