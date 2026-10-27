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

import hashlib
import json
import sys

import pytest
from financial_guardrails.datasets import BenchmarkCase, BenchmarkMessage
from financial_guardrails.splits import assign_splits

from scripts import run_static_evaluation


def test_max_cases_rejects_zero(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_static_evaluation", "cnfinbench-pooled", "--max-cases", "0"],
    )

    with pytest.raises(SystemExit, match="2"):
        run_static_evaluation.main()


def test_cross_validation_fold_rejects_out_of_range(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_static_evaluation", "cnfinbench-pooled", "--cv-fold", "4"],
    )

    with pytest.raises(SystemExit, match="2"):
        run_static_evaluation.main()


def test_outcome_score_all_events_requires_rules_first_cascade(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_static_evaluation", "finvault-v5-fixed-full", "--judge-mode", "all_events", "--outcome-score-all-events"],
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


def test_v3_finvault_cv_requires_reviewed_groups_before_loading_data(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_static_evaluation",
            "finvault-v5-fixed-full",
            "--cv-fold",
            "0",
            "--input-view",
            "v3_clean",
        ],
    )
    with pytest.raises(SystemExit, match="2"):
        run_static_evaluation.main()


def test_reviewed_group_manifest_rejects_dataset_mismatch_and_non_development_groups(tmp_path):
    data_path = tmp_path / "cases.json"
    metadata_path = tmp_path / "cases.meta.json"
    data_path.write_text("[]")
    metadata_path.write_text("{}")
    cases = tuple(
        BenchmarkCase(
            dataset_key="finvault-v5-fixed-full",
            case_id=str(i),
            label=0,
            messages=(BenchmarkMessage(role="user", kind="message", content="ok", original_role="user", turn_index=0),),
            metadata={"sidecar": {"scenario_id": str(i)}},
        )
        for i in range(10)
    )
    assigned = assign_splits(cases)
    development_group = next(item.group_id for item in assigned if item.split == "development")
    final_group = next(item.group_id for item in assigned if item.split == "final")
    base = tmp_path / "review"
    (base / "coordinator").mkdir(parents=True)
    (base / "reviewers").mkdir()
    packet = base / "reviewers" / "blinded-traces.json"
    packet.write_text("[]")
    path = base / "coordinator" / "reviewed-source-groups-v3.json"
    manifest = {
        "schema_version": "1",
        "dataset_key": "finvault-v5-fixed-full",
        "dataset_sha256": hashlib.sha256(data_path.read_bytes()).hexdigest(),
        "metadata_sha256": hashlib.sha256(metadata_path.read_bytes()).hexdigest(),
        "review_packet_sha256": hashlib.sha256(packet.read_bytes()).hexdigest(),
        "reviewed_case_count": 60,
        "reviewed_group_count": 1,
        "reviewed_source_groups": [development_group],
    }
    path.write_text(json.dumps(manifest))

    assert run_static_evaluation._load_reviewed_groups(
        path, "finvault-v5-fixed-full", data_path, metadata_path, cases
    ) == {development_group}
    manifest["reviewed_source_groups"] = [final_group]
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="non-development"):
        run_static_evaluation._load_reviewed_groups(path, "finvault-v5-fixed-full", data_path, metadata_path, cases)
    manifest["reviewed_source_groups"] = [development_group]
    manifest["dataset_sha256"] = "0" * 64
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="checksum"):
        run_static_evaluation._load_reviewed_groups(path, "finvault-v5-fixed-full", data_path, metadata_path, cases)
