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

import json

import pytest
from financial_guardrails.v3_contexts import load_trusted_facts


def _bundle(*, duplicate=False):
    event_id = "v3:" + "a" * 64 + ":0"
    return {
        "schema_version": "v3-trusted-facts-1",
        "authorization_facts": [
            {
                "event_id": event_id,
                "authorization": {},
                "requirement": {"operation": "message"},
            },
            *(
                [
                    {
                        "event_id": event_id,
                        "authorization": {},
                        "requirement": {"operation": "message"},
                    }
                ]
                if duplicate
                else []
            ),
        ],
        "outcome_facts": [
            {
                "conversation_id": "v3:" + "a" * 64 + ":-1",
                "outcome": {"executed_action_event_ids": [event_id]},
            }
        ],
    }


def test_trusted_facts_are_resolved_only_by_opaque_identifiers(tmp_path):
    path = tmp_path / "trusted-facts.json"
    path.write_text(json.dumps(_bundle()), encoding="utf-8")

    bundle = load_trusted_facts(path)

    authorization, requirement = bundle.authorization_for("v3:" + "a" * 64 + ":0")
    assert authorization.allowed_tools == frozenset()
    assert requirement.operation == "message"
    assert bundle.outcome_for("v3:" + "a" * 64 + ":-1").executed_action_event_ids
    with pytest.raises(ValueError, match="unavailable"):
        bundle.authorization_for("v3:" + "b" * 64 + ":0")


def test_trusted_facts_reject_duplicate_identifiers(tmp_path):
    path = tmp_path / "trusted-facts.json"
    path.write_text(json.dumps(_bundle(duplicate=True)), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate"):
        load_trusted_facts(path)
