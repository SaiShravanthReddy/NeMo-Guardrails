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

"""Separate Version 3 event routing with application-owned authorization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from financial_guardrails.authorization import (
    AuthorizationDetector,
    AuthorizationRequirement,
    TrustedAuthorizationContext,
)
from financial_guardrails.engine import PRECEDENCE, PolicyEngine
from financial_guardrails.outcome_judge import OutcomeJudgeResponse, TrustedOutcomeContext, V3OutcomeJudge
from financial_guardrails.schema import (
    Decision,
    DetectorResult,
    DetectorStatus,
    Mode,
    RiskCategory,
    SecurityEvent,
    Verdict,
)
from financial_guardrails.v3_judge import V3PolicyJudgeDetector


class TrustedAuthorizationResolver(Protocol):
    """Resolve application facts using only an opaque event identifier."""

    def resolve(self, event_id: str) -> tuple[TrustedAuthorizationContext, AuthorizationRequirement]: ...


class TrustedOutcomeResolver(Protocol):
    """Resolve application execution facts using only an opaque conversation ID."""

    def resolve(self, conversation_id: str) -> TrustedOutcomeContext: ...


@dataclass(frozen=True)
class V3EventResult:
    """Content-free routing result for one Version 3 event."""

    verdict: Verdict
    authorization_result: DetectorResult
    deterministic_result: Verdict
    judge_invoked: bool


class V3EventEvaluator:
    """Apply authorization and rules before routing unresolved events to the V3 judge."""

    def __init__(
        self,
        *,
        rules_engine: PolicyEngine,
        authorization_resolver: TrustedAuthorizationResolver,
        judge: V3PolicyJudgeDetector,
    ):
        self.rules_engine = rules_engine
        self.authorization_resolver = authorization_resolver
        self.judge = judge
        self.authorization_detector = AuthorizationDetector()

    def evaluate(self, event: SecurityEvent) -> V3EventResult:
        authorization, requirement = self.authorization_resolver.resolve(event.event_id)
        authorization_result = self.authorization_detector.detect(event, authorization, requirement)
        deterministic = self.rules_engine.evaluate(event, mode=Mode.ENFORCE)
        if _intervenes(authorization_result.decision) or _intervenes(deterministic.recommended_decision):
            return V3EventResult(
                verdict=_merge(event, self.rules_engine, authorization_result, deterministic),
                authorization_result=authorization_result,
                deterministic_result=deterministic,
                judge_invoked=False,
            )
        judge_result = self.judge.detect(event, authorization, requirement)
        return V3EventResult(
            verdict=_merge(event, self.rules_engine, authorization_result, deterministic, judge_result),
            authorization_result=authorization_result,
            deterministic_result=deterministic,
            judge_invoked=True,
        )


class V3OutcomeEvaluator:
    """Run independent outcome assessment with application-owned execution facts."""

    def __init__(self, *, outcome_resolver: TrustedOutcomeResolver, outcome_judge: V3OutcomeJudge):
        self.outcome_resolver = outcome_resolver
        self.outcome_judge = outcome_judge

    def assess(self, conversation_id: str, events: tuple[SecurityEvent, ...]) -> OutcomeJudgeResponse:
        return self.outcome_judge.assess(events, self.outcome_resolver.resolve(conversation_id))


def _intervenes(decision: Decision) -> bool:
    return decision in {Decision.BLOCK, Decision.SANITIZE, Decision.REQUIRE_CONFIRMATION}


def _merge(
    event: SecurityEvent,
    engine: PolicyEngine,
    *results: DetectorResult | Verdict,
) -> Verdict:
    """Create a Version 3 verdict without dropping threat-only audit findings."""

    detector_results: list[DetectorResult] = []
    for result in results:
        if isinstance(result, Verdict):
            detector_results.append(
                DetectorResult(
                    detector="deterministic_rules",
                    status=DetectorStatus.ERROR if result.detector_error else DetectorStatus.OK,
                    decision=result.recommended_decision,
                    policy_ids=result.policy_ids,
                    risk_category=result.risk_category,
                    evidence=result.evidence,
                    explanation=result.explanation,
                    threat_assessment=result.threat_assessment,
                    threat_score=result.threat_score,
                )
            )
        else:
            detector_results.append(result)
    recommended = max((result.decision for result in detector_results), key=PRECEDENCE.__getitem__)
    audit = [
        result
        for result in detector_results
        if result.decision is not Decision.ALLOW or result.threat_assessment is not None
    ]
    primary = max(audit, key=lambda result: PRECEDENCE[result.decision]) if audit else None
    return Verdict(
        policy_id=engine.config.policy_id,
        policy_version=engine.config.policy_version,
        mode=Mode.ENFORCE,
        decision=recommended,
        recommended_decision=recommended,
        policy_ids=tuple(dict.fromkeys(policy for result in audit for policy in result.policy_ids)),
        risk_category=primary.risk_category if primary else RiskCategory.NONE,
        evidence=tuple(evidence for result in audit for evidence in result.evidence),
        explanation=primary.explanation if primary else "No configured policy matched.",
        detector_error=any(result.status is DetectorStatus.ERROR for result in detector_results),
        detector_statuses={result.detector: result.status for result in detector_results},
        content="" if recommended is Decision.BLOCK else event.content,
        threat_assessment=next(
            (result.threat_assessment for result in reversed(audit) if result.threat_assessment is not None), None
        ),
        threat_score=max((result.threat_score for result in audit if result.threat_score is not None), default=None),
    )
