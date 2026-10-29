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
from financial_guardrails.benchmark_input import opaque_event_id
from financial_guardrails.datasets import BenchmarkCase, BenchmarkMessage
from financial_guardrails.v3_contexts import load_trusted_facts, validate_trusted_facts_coverage


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


def test_trusted_facts_coverage_requires_every_tool_and_outcome_context(tmp_path):
    case = BenchmarkCase(
        dataset_key="fixture",
        case_id="case-1",
        label=0,
        messages=(
            BenchmarkMessage(
                role="assistant",
                kind="tool_call",
                content="{'tool': 'approve_payout', 'args': {'case_id': 'c-1', 'amount': 1}}",
                original_role="agent",
                turn_index=0,
            ),
        ),
    )
    path = tmp_path / "trusted-facts.json"
    path.write_text(json.dumps(_bundle()), encoding="utf-8")

    with pytest.raises(ValueError, match="incomplete"):
        validate_trusted_facts_coverage((case,), load_trusted_facts(path))

    event_id = opaque_event_id("fixture", "case-1", 0)
    complete = {
        "schema_version": "v3-trusted-facts-1",
        "authorization_facts": [{"event_id": event_id, "authorization": {}, "requirement": {"operation": "approve"}}],
        "outcome_facts": [{"conversation_id": opaque_event_id("fixture", "case-1", -1), "outcome": {}}],
    }
    path.write_text(json.dumps(complete), encoding="utf-8")

    validate_trusted_facts_coverage((case,), load_trusted_facts(path))
