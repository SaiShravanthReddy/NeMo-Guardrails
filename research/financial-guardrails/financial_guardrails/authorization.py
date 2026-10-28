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

"""Application-owned authorization checks for Version 3 tool calls."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from financial_guardrails.schema import Decision, DetectorResult, Evidence, RiskCategory, SecurityEvent, Surface


class AuthorizationState(str, Enum):
    KNOWN = "known"
    UNKNOWN = "unknown"


class TrustedAuthorizationContext(BaseModel):
    """Immutable authorization facts supplied by the application."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation_state: AuthorizationState = AuthorizationState.UNKNOWN
    resource_scope_state: AuthorizationState = AuthorizationState.UNKNOWN
    transaction_limit_state: AuthorizationState = AuthorizationState.UNKNOWN
    prerequisite_state: AuthorizationState = AuthorizationState.UNKNOWN
    confirmation_state: AuthorizationState = AuthorizationState.UNKNOWN
    allowed_tools: frozenset[str] = Field(default_factory=frozenset)
    allowed_operations: frozenset[str] = Field(default_factory=frozenset)
    allowed_resource_ids: frozenset[str] = Field(default_factory=frozenset)
    transaction_limit: Decimal | None = Field(default=None, ge=0)
    completed_prerequisite_ids: frozenset[str] = Field(default_factory=frozenset)
    trusted_confirmation_event_ids: frozenset[str] = Field(default_factory=frozenset)


class AuthorizationRequirement(BaseModel):
    """Trusted application policy for one proposed operation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: str = Field(min_length=1)
    resource_argument_names: tuple[str, ...] = ()
    amount_argument_name: str | None = None
    prerequisite_ids: frozenset[str] = Field(default_factory=frozenset)
    high_impact: bool = False


class AuthorizationDetector:
    name = "trusted_authorization"

    def detect(
        self,
        event: SecurityEvent,
        context: TrustedAuthorizationContext,
        requirement: AuthorizationRequirement,
    ) -> DetectorResult:
        if event.surface is not Surface.TOOL_CALL:
            return DetectorResult(detector=self.name)
        if context.operation_state is AuthorizationState.UNKNOWN:
            return self._unknown(requirement, "AUTH-OPERATION-UNKNOWN", "Tool-operation authorization is unavailable.")
        if event.tool_name not in context.allowed_tools or requirement.operation not in context.allowed_operations:
            return self._result(
                Decision.BLOCK,
                "AUTH-OPERATION",
                "The trusted application context does not authorize this tool operation.",
            )
        resources = {
            value
            for name in requirement.resource_argument_names
            for value in (event.arguments.get(name),)
            if isinstance(value, str)
        }
        if resources and context.resource_scope_state is AuthorizationState.UNKNOWN:
            return self._unknown(requirement, "AUTH-RESOURCE-UNKNOWN", "Authorized resource scope is unavailable.")
        if resources - context.allowed_resource_ids:
            return self._result(
                Decision.BLOCK,
                "AUTH-RESOURCE",
                "The call references a resource outside the trusted authorization scope.",
            )
        if requirement.prerequisite_ids and context.prerequisite_state is AuthorizationState.UNKNOWN:
            return self._unknown(requirement, "AUTH-PREREQUISITE-UNKNOWN", "Trusted prerequisite state is unavailable.")
        if requirement.prerequisite_ids - context.completed_prerequisite_ids:
            return self._result(
                Decision.BLOCK,
                "AUTH-PREREQUISITE",
                "A trusted prerequisite has not completed.",
            )
        if requirement.amount_argument_name and context.transaction_limit_state is AuthorizationState.UNKNOWN:
            return self._unknown(requirement, "AUTH-LIMIT-UNKNOWN", "The trusted transaction limit is unavailable.")
        if requirement.amount_argument_name and context.transaction_limit is not None:
            amount = self._amount(event.arguments.get(requirement.amount_argument_name))
            if amount is None or amount > context.transaction_limit:
                return self._result(
                    Decision.BLOCK,
                    "AUTH-LIMIT",
                    "The amount is invalid or exceeds the trusted transaction limit.",
                )
        if requirement.high_impact:
            if context.confirmation_state is AuthorizationState.UNKNOWN:
                return self._result(
                    Decision.REQUIRE_CONFIRMATION,
                    "AUTH-CONFIRM",
                    "A trusted application confirmation is required for this high-impact action.",
                )
            trusted_confirmations = set(event.authorized_by_event_ids) & context.trusted_confirmation_event_ids
            if not trusted_confirmations:
                return self._result(
                    Decision.REQUIRE_CONFIRMATION,
                    "AUTH-CONFIRM",
                    "A trusted application confirmation is required for this high-impact action.",
                )
        return DetectorResult(detector=self.name)

    def _unknown(self, requirement: AuthorizationRequirement, policy_id: str, explanation: str) -> DetectorResult:
        decision = Decision.REQUIRE_CONFIRMATION if requirement.high_impact else Decision.BLOCK
        return self._result(decision, policy_id, explanation)

    @staticmethod
    def _amount(value: object) -> Decimal | None:
        if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
            return None
        try:
            amount = Decimal(str(value))
        except InvalidOperation:
            return None
        return amount if amount.is_finite() and amount >= 0 else None

    def _result(self, decision: Decision, policy_id: str, explanation: str) -> DetectorResult:
        return DetectorResult(
            detector=self.name,
            decision=decision,
            policy_ids=(policy_id,),
            risk_category=RiskCategory.AGENT_ACTION,
            evidence=(
                Evidence(
                    detector=self.name,
                    rule_id=policy_id,
                    summary="trusted authorization condition",
                ),
            ),
            explanation=explanation,
        )
