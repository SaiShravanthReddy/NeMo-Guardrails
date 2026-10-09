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

"""Regression checks for static-evaluation command-line safeguards."""

from __future__ import annotations

import sys

import pytest

from scripts import run_static_evaluation


def test_max_cases_rejects_zero(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_static_evaluation", "cnfinbench-pooled", "--max-cases", "0"],
    )

    with pytest.raises(SystemExit, match="2"):
        run_static_evaluation.main()


def test_case_id_file_rejects_duplicates(tmp_path):
    path = tmp_path / "cases.txt"
    path.write_text("one\none\n", encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate"):
        run_static_evaluation._load_case_ids(path)


def test_case_id_file_preserves_explicit_order(tmp_path):
    path = tmp_path / "cases.txt"
    path.write_text("two\n\none\n", encoding="utf-8")

    assert run_static_evaluation._load_case_ids(path) == ("two", "one")
