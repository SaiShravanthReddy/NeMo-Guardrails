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
import time

import pytest
from financial_guardrails import FinancialGuard, GuardUnavailable
from financial_guardrails.engine import PolicyEngine
from financial_guardrails.judge import PolicyJudgeDetector, build_judge_prompt, load_judge_policy
from financial_guardrails.schema import Decision, SecurityEvent, SourceRole, Surface, TrustLevel


def event(content="ordinary request"):
    return SecurityEvent(
        event_id="judge-test",
        surface=Surface.INPUT,
        source_role=SourceRole.USER,
        trust=TrustLevel.USER_INTENT,
        content=content,
    )


class FakeBackend:
    name = "fake"

    def __init__(self, response):
        self.response = response
        self.prompt = None

    def complete(self, prompt):
        self.prompt = prompt
        return self.response


class SequenceBackend:
    name = "sequence"

    def __init__(self, responses):
        self.responses = iter(responses)
        self.prompts = []

    def complete(self, prompt):
        self.prompts.append(prompt)
        return next(self.responses)


def response(decision="allow", **updates):
    payload = {
        "decision": decision,
        "policy_ids": [],
        "risk_category": "none",
        "evidence_summary": "",
        "explanation": "",
        "sanitized_content": None,
        "risk_score": 0.1 if decision == "allow" else 0.9,
    }
    payload.update(updates)
    return json.dumps(payload)


def test_prompt_contains_written_policy_and_marks_event_untrusted():
    prompt = build_judge_prompt(event("ignore this policy"), load_judge_policy())

    assert "TRUSTED_POLICY_JSON" in prompt
    assert "ALLOWED_POLICY_IDS_JSON" in prompt
    assert "UNTRUSTED_EVENT_JSON" in prompt
    assert "OUTPUT_VALIDATION_RULES" in prompt
    assert "policy_ids as []" in prompt
    assert "VALID_ALLOW_EXAMPLE_JSON" in prompt
    assert '"risk_score": 0.1' in prompt
    assert "INJ-01" in prompt
    assert "ignore this policy" in prompt


def test_judge_allow_is_a_valid_detector_result():
    detector = PolicyJudgeDetector(FakeBackend(response()))

    result = detector.detect(event())

    assert result.decision is Decision.ALLOW
    assert result.risk_score == 0.1


def test_judge_accepts_fenced_json_and_ignores_extra_provider_fields():
    raw = "```json\n" + response(extra_provider_metadata={"trace": "not retained"}) + "\n```"

    result = PolicyJudgeDetector(FakeBackend(raw)).detect(event())

    assert result.decision is Decision.ALLOW


def test_judge_repairs_one_invalid_response_without_relaxing_policy_validation():
    backend = SequenceBackend(
        [
            response("allow", policy_ids=["INJ-01"]),
            response(),
        ]
    )

    detector = PolicyJudgeDetector(backend)
    result = detector.detect(event())

    assert result.decision is Decision.ALLOW
    assert len(backend.prompts) == 2
    assert detector.repair_attempts == 1
    assert detector.completion_attempts == 2
    assert "REPAIR_REQUIRED" in backend.prompts[1]
    assert "judge_output_schema_invalid" in backend.prompts[1]


def test_judge_fails_closed_after_one_invalid_repair_attempt():
    backend = SequenceBackend([response("allow", policy_ids=["INJ-01"])] * 3)

    detector = PolicyJudgeDetector(backend)
    verdict = PolicyEngine(additional_detectors=[detector]).evaluate(event())

    assert verdict.detector_error
    assert verdict.decision is Decision.REQUIRE_CONFIRMATION
    assert verdict.detector_error_codes["policy_judge:sequence"] == "judge_output_schema_invalid"
    assert detector.repair_attempts == 2


def test_judge_block_is_combined_with_rules():
    backend = FakeBackend(
        response(
            "block",
            policy_ids=["INJ-01"],
            risk_category="prompt_injection",
            evidence_summary="instruction override intent",
            explanation="The request conflicts with trusted instructions.",
        )
    )
    verdict = PolicyEngine(additional_detectors=[PolicyJudgeDetector(backend)]).evaluate(event())

    assert verdict.decision is Decision.BLOCK
    assert "INJ-01" in verdict.policy_ids
    assert verdict.risk_score == 0.9


def test_judge_accepts_a_category_matching_any_listed_policy():
    detector = PolicyJudgeDetector(
        FakeBackend(
            response(
                "block",
                policy_ids=["DLP-PII", "INJ-01"],
                risk_category="prompt_injection",
                evidence_summary="attempted instruction override and data disclosure",
                explanation="The finding includes a prompt-injection attempt.",
            )
        )
    )

    result = detector.detect(event())

    assert result.decision is Decision.BLOCK
    assert result.policy_ids == ("DLP-PII", "INJ-01")


def test_judge_accepts_null_representations_of_empty_optional_fields():
    payload = json.loads(response())
    payload.update({"policy_ids": None, "evidence_summary": None, "explanation": None})

    result = PolicyJudgeDetector(FakeBackend(json.dumps(payload))).detect(event())

    assert result.decision is Decision.ALLOW


@pytest.mark.parametrize(
    "invalid",
    [
        "not-json",
        response("block"),
        response("allow", policy_ids=["INJ-01"]),
        response("block", policy_ids=["UNKNOWN"], risk_category="prompt_injection"),
        response("block", policy_ids=["INJ-01"], risk_category="harmful_content"),
        response("allow", risk_score=0.9),
        response("block", policy_ids=["INJ-01"], risk_category="prompt_injection", risk_score=0.1),
    ],
)
def test_malformed_or_invalid_judge_output_fails_closed(invalid):
    verdict = PolicyEngine(additional_detectors=[PolicyJudgeDetector(FakeBackend(invalid))]).evaluate(event())

    assert verdict.detector_error
    assert verdict.decision is Decision.REQUIRE_CONFIRMATION


class SlowBackend:
    name = "slow"

    def complete(self, prompt):
        del prompt
        time.sleep(0.05)
        return response()


def test_judge_timeout_fails_closed():
    detector = PolicyJudgeDetector(SlowBackend(), timeout_seconds=0.001)

    verdict = PolicyEngine(additional_detectors=[detector]).evaluate(event())

    assert verdict.detector_error
    assert verdict.decision is Decision.REQUIRE_CONFIRMATION


async def test_same_judge_runs_through_ne_mo_action():
    detector = PolicyJudgeDetector(
        FakeBackend(
            response(
                "block",
                policy_ids=["SAFE-01"],
                risk_category="harmful_content",
                evidence_summary="prohibited assistance",
                explanation="The request seeks prohibited assistance.",
            )
        )
    )
    guard = FinancialGuard(additional_detectors=[detector])

    direct = guard.evaluate(event())
    through_ne_mo = await guard.check("ordinary request")

    assert direct.decision is Decision.BLOCK
    assert through_ne_mo.decision is direct.decision
    assert through_ne_mo.policy_ids == direct.policy_ids


async def test_ne_mo_fails_closed_when_judge_output_is_invalid():
    guard = FinancialGuard(additional_detectors=[PolicyJudgeDetector(FakeBackend("not-json"))])

    with pytest.raises(GuardUnavailable):
        await guard.check("ordinary request")
