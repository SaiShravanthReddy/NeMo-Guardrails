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

from __future__ import annotations

from collections.abc import Iterable

from financial_guardrails.configuration import PolicyConfig, load_policy
from financial_guardrails.detectors import (
    ContentSafetyDetector,
    DataLeakageDetector,
    Detector,
    LimitDetector,
    LinkDetector,
    PromptDefenseDetector,
    ToolPolicyDetector,
)
from financial_guardrails.schema import (
    Decision,
    DetectorResult,
    DetectorStatus,
    Evidence,
    Mode,
    RiskCategory,
    SecurityEvent,
    Surface,
    Verdict,
)

PRECEDENCE = {
    Decision.ALLOW: 0,
    Decision.LOG_ONLY: 1,
    Decision.SANITIZE: 2,
    Decision.REQUIRE_CONFIRMATION: 3,
    Decision.BLOCK: 4,
}


class PolicyEngine:
    def __init__(self, config: PolicyConfig | None = None, detectors: Iterable[Detector] | None = None):
        self.config = config or load_policy()
        self.detectors = list(
            detectors
            or (
                PromptDefenseDetector(),
                LimitDetector(self.config),
                ContentSafetyDetector(),
                DataLeakageDetector(self.config),
                LinkDetector(self.config),
                ToolPolicyDetector(self.config),
            )
        )

    def evaluate(self, event: SecurityEvent, mode: Mode | None = None) -> Verdict:
        selected_mode = mode or self.config.default_mode
        results: list[DetectorResult] = []
        for detector in self.detectors:
            try:
                result = detector.detect(event)
                if not isinstance(result, DetectorResult):
                    raise TypeError("detector returned an invalid result")
            except Exception:
                result = DetectorResult(
                    detector=detector.name,
                    status=DetectorStatus.ERROR,
                    decision=self._failure_decision(event),
                    policy_ids=("DETECTOR-ERROR",),
                    risk_category=RiskCategory.DETECTOR_FAILURE,
                    evidence=(Evidence(detector=detector.name, rule_id="DETECTOR-ERROR", summary="detector failed"),),
                    explanation="A required detector did not return a valid decision.",
                    error_code="detector_failure",
                )
            results.append(result)

        recommended = max(
            (result.decision for result in results),
            key=lambda decision: PRECEDENCE[decision],
            default=Decision.ALLOW,
        )
        content = event.content
        if recommended is Decision.SANITIZE:
            for result in results:
                if result.sanitized_content is not None:
                    content = result.sanitized_content
        elif recommended is Decision.BLOCK:
            content = ""

        findings = [result for result in results if result.decision is not Decision.ALLOW]
        decision = recommended
        if selected_mode is Mode.DETECT and findings:
            decision = Decision.LOG_ONLY
            content = event.content

        primary = max(findings, key=lambda result: PRECEDENCE[result.decision]) if findings else None
        return Verdict(
            policy_id=self.config.policy_id,
            policy_version=self.config.policy_version,
            mode=selected_mode,
            decision=decision,
            recommended_decision=recommended,
            policy_ids=tuple(dict.fromkeys(policy for result in findings for policy in result.policy_ids)),
            risk_category=primary.risk_category if primary else RiskCategory.NONE,
            evidence=tuple(item for result in findings for item in result.evidence),
            explanation=primary.explanation if primary else "No configured policy matched.",
            detector_error=any(result.status is DetectorStatus.ERROR for result in results),
            detector_statuses={result.detector: result.status for result in results},
            content=content,
        )

    def _failure_decision(self, event: SecurityEvent) -> Decision:
        high_impact = event.surface is Surface.TOOL_CALL or event.tool_name in {
            *self.config.tools.confirmation_required,
            *self.config.tools.denied,
        }
        return self.config.failure_policy.high_impact if high_impact else self.config.failure_policy.ordinary
