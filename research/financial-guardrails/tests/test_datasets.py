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
from financial_guardrails.datasets import inspect_json_dataset


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
