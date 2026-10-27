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
from financial_guardrails.datasets import BenchmarkCase, BenchmarkMessage
from financial_guardrails.judge import build_judge_prompt, load_judge_policy
from financial_guardrails.replay import event_from_message, parse_finvault_tool_call


def test_parses_reviewed_finvault_literal_format():
    parsed = parse_finvault_tool_call("{'tool': 'lookup', 'args': {'active': true, 'count': -2}}")
    assert parsed.name == "lookup"
    assert parsed.arguments == {"active": True, "count": -2}


@pytest.mark.parametrize(
    "value",
    [
        "run_tool()",
        "{'tool': 'x', 'args': __import__('os').environ}",
        "{'tool': 'x', 'args': {}, 'unexpected': 'field'}",
        "{'tool': '', 'args': {}}",
    ],
)
def test_rejects_executable_or_unsupported_forms(value):
    with pytest.raises(ValueError):
        parse_finvault_tool_call(value)


def _case(dataset_key, case_id, message):
    return BenchmarkCase(dataset_key=dataset_key, case_id=case_id, label=1, messages=(message,))


def test_v3_view_hides_label_bearing_case_id_from_judge_prompt():
    message = BenchmarkMessage(
        role="user", kind="message", content="Explain this policy", original_role="user", turn_index=0
    )
    case = _case("cnfinbench-pooled", "harmful-example", message)

    legacy = event_from_message(case, message)
    clean = event_from_message(case, message, input_view="v3_clean")
    prompt = build_judge_prompt(clean, load_judge_policy())

    assert legacy.event_id == "harmful-example:0"
    assert "harmful-example" not in clean.event_id
    assert "harmful-example" not in prompt
    assert clean.event_id == event_from_message(case, message, input_view="v3_clean").event_id
    assert clean.content == legacy.content


@pytest.mark.parametrize("flag", [False, True])
def test_v3_view_removes_finvault_annotations_and_preserves_business_evidence(flag):
    message = BenchmarkMessage(
        role="tool",
        kind="tool_result",
        original_role="environment",
        turn_index=2,
        content=json.dumps(
            {
                "result": {"status": "error", "authorization_valid": False, "attack_intent_detected": flag},
                "state": {"risk_flags": {"bypass": flag}, "calls_made_count": 1},
                "security_alerts": [{"vuln_id": "V1"}],
            }
        ),
    )
    case = _case("finvault-v5-fixed-full", "finvault-case", message)
    legacy = event_from_message(case, message)
    clean = event_from_message(case, message, input_view="v3_clean")

    assert legacy.content == message.content
    assert json.loads(clean.content) == {
        "result": {"status": "error", "authorization_valid": False},
        "state": {"calls_made_count": 1},
    }
    assert "finvault-case" not in clean.event_id


def test_v3_view_strips_scenario_description_but_keeps_limits_and_tool_call():
    description = BenchmarkMessage(
        role="tool",
        kind="tool_result",
        original_role="environment",
        turn_index=1,
        content="Description: Normal case\nRisk limit: 10\n",
    )
    call = BenchmarkMessage(
        role="assistant",
        kind="tool_call",
        original_role="agent",
        turn_index=2,
        content='{"tool": "deploy", "args": {"override": true}}',
    )
    case = BenchmarkCase(
        dataset_key="finvault-v5-fixed-full", case_id="finvault-case", label=1, messages=(description, call)
    )

    assert event_from_message(case, description, input_view="v3_clean").content == "Risk limit: 10\n"
    assert event_from_message(case, call, input_view="v3_clean").content == call.content


def test_v3_view_redacts_benchmark_ids_inside_messages_and_tool_arguments():
    user = BenchmarkMessage(
        role="user",
        kind="message",
        original_role="user",
        turn_index=0,
        content="[Case ID: harmful-example] Check this request.",
    )
    call = BenchmarkMessage(
        role="assistant",
        kind="tool_call",
        original_role="agent",
        turn_index=1,
        content='{"tool": "lookup", "args": {"note": "[Case ID: harmful-example]"}}',
    )
    case = BenchmarkCase(
        dataset_key="finvault-v5-fixed-full", case_id="harmful-example", label=1, messages=(user, call)
    )

    assert event_from_message(case, user, input_view="v3_clean").content == "[Case ID: REDACTED] Check this request."
    tool_event = event_from_message(case, call, input_view="v3_clean")
    assert tool_event.arguments == {"note": "[Case ID: REDACTED]"}
    assert "harmful-example" not in tool_event.content
