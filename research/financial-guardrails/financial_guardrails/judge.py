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

"""Provider-independent policy judge with strict, fail-closed output parsing."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from pathlib import Path
from typing import Protocol

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from financial_guardrails.schema import Decision, DetectorResult, Evidence, RiskCategory, SecurityEvent

DEFAULT_JUDGE_POLICY_PATH = Path(__file__).resolve().parents[1] / "policies" / "llm_judge_v1.yml"


class JudgePolicyEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    category: RiskCategory
    requirement: str = Field(min_length=1)


class JudgePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str
    policy_id: str
    policy_version: str
    instructions: tuple[str, ...]
    policies: tuple[JudgePolicyEntry, ...]


class JudgeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: Decision
    policy_ids: tuple[str, ...] = ()
    risk_category: RiskCategory = RiskCategory.NONE
    evidence_summary: str = Field(default="", max_length=240)
    explanation: str = Field(default="", max_length=500)
    sanitized_content: str | None = None

    @model_validator(mode="after")
    def validate_decision_fields(self):
        if self.decision is Decision.ALLOW:
            if self.policy_ids or self.risk_category is not RiskCategory.NONE or self.sanitized_content is not None:
                raise ValueError("allow responses cannot contain findings or sanitized content")
        else:
            if not self.policy_ids or self.risk_category is RiskCategory.NONE:
                raise ValueError("non-allow responses require policy IDs and a risk category")
        if self.decision is Decision.SANITIZE and self.sanitized_content is None:
            raise ValueError("sanitize responses require sanitized_content")
        if self.decision is not Decision.SANITIZE and self.sanitized_content is not None:
            raise ValueError("sanitized_content is only valid for sanitize responses")
        return self


class JudgeBackend(Protocol):
    name: str

    def complete(self, prompt: str) -> str: ...


def load_judge_policy(path: str | Path = DEFAULT_JUDGE_POLICY_PATH) -> JudgePolicy:
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError("judge policy configuration could not be loaded") from exc
    return JudgePolicy.model_validate(raw)


def build_judge_prompt(event: SecurityEvent, policy: JudgePolicy) -> str:
    response_schema = {
        "decision": "allow|block|sanitize|require_confirmation|log_only",
        "policy_ids": ["matching policy IDs"],
        "risk_category": "none|prompt_injection|jailbreak|harmful_content|data_leakage|malicious_link|agent_action",
        "evidence_summary": "short description without sensitive or verbatim content",
        "explanation": "short policy-grounded reason",
        "sanitized_content": "required only for sanitize; otherwise null",
    }
    trusted_policy = {
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "instructions": policy.instructions,
        "policies": [entry.model_dump(mode="json") for entry in policy.policies],
    }
    untrusted_event = {
        "event_id": event.event_id,
        "surface": event.surface.value,
        "source_role": event.source_role.value,
        "trust": event.trust.value,
        "content": event.content,
        "tool_name": event.tool_name,
        "arguments": event.arguments,
        "permissions": sorted(event.permissions),
        "allowed_resource_ids": sorted(event.allowed_resource_ids),
        "authorized_by_event_ids": event.authorized_by_event_ids,
    }
    return "\n".join(
        (
            "You are the Open Lakera security policy judge.",
            "TRUSTED_POLICY_JSON:",
            json.dumps(trusted_policy, ensure_ascii=False, sort_keys=True),
            "UNTRUSTED_EVENT_JSON:",
            json.dumps(untrusted_event, ensure_ascii=False, sort_keys=True),
            "RESPONSE_SCHEMA_JSON:",
            json.dumps(response_schema, sort_keys=True),
            "Return only the response JSON object.",
        )
    )


class PolicyJudgeDetector:
    def __init__(
        self,
        backend: JudgeBackend,
        policy: JudgePolicy | None = None,
        timeout_seconds: float = 30,
    ):
        self.backend = backend
        self.policy = policy or load_judge_policy()
        self.timeout_seconds = timeout_seconds
        self.name = f"policy_judge:{backend.name}"
        self._policy_ids = {entry.id for entry in self.policy.policies}
        self._policy_categories = {entry.id: entry.category for entry in self.policy.policies}
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="policy-judge")

    def detect(self, event: SecurityEvent) -> DetectorResult:
        prompt = build_judge_prompt(event, self.policy)
        future = self._executor.submit(self.backend.complete, prompt)
        try:
            raw = future.result(timeout=self.timeout_seconds)
        except FutureTimeout as exc:
            future.cancel()
            raise TimeoutError("policy judge timed out") from exc
        if not isinstance(raw, str):
            raise ValueError("policy judge returned a non-text response")
        try:
            response = JudgeResponse.model_validate_json(raw)
        except Exception as exc:
            raise ValueError("policy judge returned malformed output") from exc
        unknown = set(response.policy_ids) - self._policy_ids
        if unknown:
            raise ValueError("policy judge returned an unknown policy ID")
        if response.policy_ids and response.risk_category not in {
            self._policy_categories[policy_id] for policy_id in response.policy_ids
        }:
            raise ValueError("policy judge returned a risk category inconsistent with its policy IDs")
        if response.decision is Decision.ALLOW:
            return DetectorResult(detector=self.name)
        return DetectorResult(
            detector=self.name,
            decision=response.decision,
            policy_ids=response.policy_ids,
            risk_category=response.risk_category,
            evidence=(
                Evidence(
                    detector=self.name,
                    rule_id=response.policy_ids[0],
                    summary=response.evidence_summary or "policy judge finding",
                ),
            ),
            explanation=response.explanation or "The policy judge identified a security risk.",
            sanitized_content=response.sanitized_content,
        )
