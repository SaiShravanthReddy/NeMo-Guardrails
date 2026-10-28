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
from financial_guardrails.authorization import (
    AuthorizationRequirement,
    AuthorizationState,
    TrustedAuthorizationContext,
)
from financial_guardrails.judge import JudgeOutputError, load_judge_policy
from financial_guardrails.schema import Decision, SecurityEvent, SourceRole, Surface, ThreatAssessment, TrustLevel
from financial_guardrails.v3_judge import V3PolicyJudgeDetector, build_v3_judge_prompt


class StructuredBackend:
    name = "structured"

    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def complete_with_schema(self, prompt, *, schema_name, schema):
        self.calls.append((prompt, schema_name, schema))
        return next(self.responses)


def _event(content="process the approved payout"):
    return SecurityEvent(
        event_id="opaque-event",
        surface=Surface.TOOL_CALL,
        source_role=SourceRole.ASSISTANT,
        trust=TrustLevel.TRUSTED,
        content=content,
        tool_name="approve_payout",
        arguments={"amount": 50},
    )


def _authorization():
    return TrustedAuthorizationContext(
        state=AuthorizationState.KNOWN,
        allowed_tools={"approve_payout"},
        allowed_operations={"approve"},
        transaction_limit=100,
    )


def _requirement():
    return AuthorizationRequirement(operation="approve", amount_argument_name="amount", high_impact=True)


def _response(**updates):
    value = {
        "threat_assessment": "benign",
        "control_action": "require_confirmation",
        "policy_ids": ["TOOL-CONFIRM"],
        "risk_category": "agent_action",
        "evidence_summary": "legitimate high-impact action",
        "explanation": "Trusted confirmation is still required.",
        "sanitized_content": None,
        "threat_score": 0.1,
    }
    value.update(updates)
    return json.dumps(value)


def test_prompt_keeps_authorization_separate_from_untrusted_event():
    prompt = build_v3_judge_prompt(
        _event("tool result claims approval"), load_judge_policy(), _authorization(), _requirement()
    )

    assert "TRUSTED_CONTEXT_JSON" in prompt
    assert "UNTRUSTED_EVENT_JSON" in prompt
    assert "cannot grant permission" in prompt
    assert "tool result claims approval" in prompt


def test_benign_threat_can_require_confirmation():
    backend = StructuredBackend([_response()])
    result = V3PolicyJudgeDetector(backend, load_judge_policy()).detect(_event(), _authorization(), _requirement())

    assert result.threat_assessment is ThreatAssessment.BENIGN
    assert result.threat_score == 0.1
    assert result.decision is Decision.REQUIRE_CONFIRMATION
    assert backend.calls[0][1] == "open_lakera_v3_judge_response"
    assert backend.calls[0][2]["additionalProperties"] is False


def test_detected_threat_can_be_logged_without_conflating_action():
    backend = StructuredBackend(
        [
            _response(
                threat_assessment="malicious",
                control_action="log_only",
                policy_ids=["INJ-01"],
                risk_category="prompt_injection",
                threat_score=0.95,
            )
        ]
    )

    result = V3PolicyJudgeDetector(backend, load_judge_policy()).detect(_event(), _authorization(), _requirement())

    assert result.threat_assessment is ThreatAssessment.MALICIOUS
    assert result.decision is Decision.LOG_ONLY


def test_semantic_error_gets_exactly_one_repair():
    invalid = _response(policy_ids=["UNKNOWN"])
    backend = StructuredBackend([invalid, _response()])
    detector = V3PolicyJudgeDetector(backend, load_judge_policy())

    result = detector.detect(_event(), _authorization(), _requirement())

    assert result.decision is Decision.REQUIRE_CONFIRMATION
    assert detector.completion_attempts == 2
    assert detector.repair_attempts == 1
    assert "SEMANTIC_REPAIR_REQUIRED" in backend.calls[1][0]


def test_second_semantic_error_fails_without_more_generation():
    backend = StructuredBackend([_response(policy_ids=["UNKNOWN"])] * 2)
    detector = V3PolicyJudgeDetector(backend, load_judge_policy())

    with pytest.raises(JudgeOutputError, match="unknown_policy_id"):
        detector.detect(_event(), _authorization(), _requirement())
    assert detector.completion_attempts == 2
    assert detector.repair_attempts == 1
