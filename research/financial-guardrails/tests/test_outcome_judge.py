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
from financial_guardrails.judge import JudgeOutputError
from financial_guardrails.outcome_judge import (
    TrustedOutcomeContext,
    V3OutcomeJudge,
    build_outcome_prompt,
    load_outcome_policy,
)
from financial_guardrails.schema import SecurityEvent, SourceRole, Surface, TrustLevel


class StructuredBackend:
    name = "outcome-structured"

    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def complete_with_schema(self, prompt, *, schema_name, schema):
        self.calls.append((prompt, schema_name, schema))
        return next(self.responses)


def _event(surface=Surface.TOOL_RESULT, content='{"status":"executed"}'):
    role = SourceRole.TOOL if surface is Surface.TOOL_RESULT else SourceRole.ASSISTANT
    trust = TrustLevel.UNTRUSTED if surface is Surface.TOOL_RESULT else TrustLevel.TRUSTED
    return SecurityEvent(event_id="opaque:1", surface=surface, source_role=role, trust=trust, content=content)


def _response(succeeded=False, **updates):
    value = {
        "attack_succeeded": succeeded,
        "outcome_score": 0.9 if succeeded else 0.1,
        "policy_ids": ["OUTCOME-ACTION"] if succeeded else [],
        "evidence_summary": "observed effect" if succeeded else "",
        "explanation": "The action executed." if succeeded else "No harmful effect was observed.",
    }
    value.update(updates)
    return json.dumps(value)


def test_outcome_prompt_rejects_input_events_and_excludes_attempt_decisions():
    input_event = SecurityEvent(
        event_id="opaque:0",
        surface=Surface.INPUT,
        source_role=SourceRole.USER,
        trust=TrustLevel.USER_INTENT,
        content="attack attempt",
    )

    with pytest.raises(ValueError, match="only ordered output"):
        build_outcome_prompt((input_event,), load_outcome_policy(), TrustedOutcomeContext())
    prompt = build_outcome_prompt((_event(),), load_outcome_policy(), TrustedOutcomeContext())
    assert "benchmark IDs, labels" in prompt
    assert "intervention" in prompt
    assert "TRUSTED_EXECUTION_CONTEXT_JSON" in prompt


def test_outcome_judge_returns_independent_success_score():
    backend = StructuredBackend([_response(True)])

    response = V3OutcomeJudge(backend).assess((_event(),), TrustedOutcomeContext())

    assert response.attack_succeeded
    assert response.outcome_score == 0.9
    assert backend.calls[0][1] == "open_lakera_v3_outcome_response"
    assert backend.calls[0][2]["additionalProperties"] is False
    assert backend.calls[0][2]["properties"]["policy_ids"]["items"]["enum"] == [
        "OUTCOME-ACTION",
        "OUTCOME-DISCLOSURE",
        "OUTCOME-HARMFUL-OUTPUT",
    ]
    assert {"policy_ids", "evidence_summary", "explanation"} <= set(backend.calls[0][2]["required"])


def test_outcome_judge_allows_one_repair_then_fails_closed():
    invalid = _response(True, policy_ids=["UNKNOWN"])
    repaired = V3OutcomeJudge(StructuredBackend([invalid, _response(False)]))

    assert not repaired.assess((_event(),), TrustedOutcomeContext()).attack_succeeded
    assert repaired.completion_attempts == 2
    assert repaired.repair_attempts == 1

    failing = V3OutcomeJudge(StructuredBackend([invalid, invalid]))
    with pytest.raises(JudgeOutputError, match="unknown_policy_id"):
        failing.assess((_event(),), TrustedOutcomeContext())
    assert failing.completion_attempts == 2
    assert failing.repair_attempts == 1


def test_unsuccessful_outcome_cannot_carry_success_policy():
    backend = StructuredBackend([_response(False, policy_ids=["OUTCOME-ACTION"])] * 2)

    with pytest.raises(JudgeOutputError, match="schema_invalid"):
        V3OutcomeJudge(backend).assess((_event(),), TrustedOutcomeContext())
