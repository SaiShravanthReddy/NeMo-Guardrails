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

import json

import pytest
from financial_guardrails.datasets import AgentAuditorDatasetAdapter, inspect_json_dataset


def test_jsonl_manifest_contains_no_record_values(tmp_path):
    path = tmp_path / "cases.jsonl"
    secret = "private-example-value"
    path.write_text(json.dumps({"id": "1", "prompt": secret}) + "\n", encoding="utf-8")

    manifest = inspect_json_dataset(path)

    assert manifest.record_count == 1
    assert manifest.top_level_keys == ("id", "prompt")
    assert secret not in manifest.model_dump_json()


def test_invalid_jsonl_reports_line_without_content(tmp_path):
    path = tmp_path / "cases.jsonl"
    path.write_text('{"valid": true}\nnot-json\n', encoding="utf-8")

    with pytest.raises(ValueError, match="line 2"):
        inspect_json_dataset(path)


def write_export(tmp_path, name, records, metadata):
    data_path = tmp_path / f"{name}.json"
    metadata_path = tmp_path / f"{name}.json.meta.json"
    data_path.write_text(json.dumps(records), encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    return AgentAuditorDatasetAdapter(name, data_path, metadata_path)


def base_record(case_id, label, contents):
    return {
        "id": case_id,
        "label": label,
        "contents": [contents],
        "ambiguous": 0,
        "behavior_mode": "test",
        "goal": "test goal",
        "profile": "test profile",
        "risk_type": "test risk",
        "scenario": "test scenario",
    }


def test_cnfinbench_adapter_preserves_messages_labels_and_metadata(tmp_path):
    record = base_record(
        "cn-1",
        1,
        [{"role": "user", "content": "question"}, {"role": "agent", "content": "answer"}],
    )
    adapter = write_export(tmp_path, "cnfinbench-pooled", [record], {"cn-1": {"label": 1, "threshold": 70}})

    case = tuple(adapter.cases())[0]

    assert case.case_id == "cn-1"
    assert case.label == 1
    assert [message.role for message in case.messages] == ["user", "assistant"]
    assert [message.kind for message in case.messages] == ["message", "message"]
    assert case.metadata["sidecar"]["threshold"] == 70


def test_finvault_adapter_preserves_tool_calls_and_results(tmp_path):
    record = base_record(
        "fin-1",
        0,
        [
            {"role": "user", "content": "request"},
            {"role": "agent", "action": "lookup(account_id='a-1')"},
            {"role": "environment", "content": "result"},
        ],
    )
    adapter = write_export(tmp_path, "finvault-v5-fixed-full", [record], {"fin-1": {"label": 0}})

    case = tuple(adapter.cases())[0]

    assert [message.role for message in case.messages] == ["user", "assistant", "tool"]
    assert [message.kind for message in case.messages] == ["message", "tool_call", "tool_result"]
    assert case.messages[1].content == "lookup(account_id='a-1')"


@pytest.mark.parametrize(
    ("records", "metadata", "error"),
    [
        ([base_record("same", 0, [{"role": "user", "content": "one"}])] * 2, {"same": {"label": 0}}, "duplicate"),
        ([base_record("one", 0, [{"role": "user", "content": "one"}])], {"other": {"label": 0}}, "IDs do not match"),
        ([base_record("one", 0, [{"role": "user", "content": "one"}])], {"one": {"label": 1}}, "labels do not match"),
    ],
)
def test_adapter_rejects_identity_and_label_corruption(tmp_path, records, metadata, error):
    adapter = write_export(tmp_path, "cnfinbench-pooled", records, metadata)

    with pytest.raises(ValueError, match=error):
        tuple(adapter.cases())
