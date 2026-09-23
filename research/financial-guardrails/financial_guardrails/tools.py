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

"""Application-owned enforcement hooks for tool calls and tool results."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from financial_guardrails.integration import FinancialGuard
from financial_guardrails.schema import Decision, SecurityEvent, SourceRole, Surface, TrustLevel


class ToolDenied(PermissionError):
    pass


class ToolConfirmationRequired(PermissionError):
    pass


@dataclass(frozen=True)
class Principal:
    subject: str
    account_ids: frozenset[str]
    permissions: frozenset[str]


class GuardedTools:
    def __init__(
        self,
        guard: FinancialGuard,
        tools: dict[str, Callable[..., Awaitable[str]]],
        confirmation_verifier: Callable[[tuple[str, ...], str, dict[str, Any], Principal], bool] | None = None,
    ):
        self.guard = guard
        self.tools = tools
        self.confirmation_verifier = confirmation_verifier

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        principal: Principal,
        confirmed_by: tuple[str, ...] = (),
    ) -> str:
        verified_confirmations = (
            confirmed_by
            if confirmed_by
            and self.confirmation_verifier is not None
            and self.confirmation_verifier(confirmed_by, name, arguments, principal)
            else ()
        )
        call = SecurityEvent(
            event_id="tool-call",
            surface=Surface.TOOL_CALL,
            source_role=SourceRole.ASSISTANT,
            trust=TrustLevel.UNTRUSTED,
            actor_id=principal.subject,
            tool_name=name,
            arguments=arguments,
            permissions=principal.permissions,
            allowed_resource_ids=principal.account_ids,
            authorized_by_event_ids=verified_confirmations,
        )
        verdict = self.guard.evaluate(call)
        if verdict.decision is Decision.REQUIRE_CONFIRMATION:
            raise ToolConfirmationRequired("TOOL-CONFIRM: trusted confirmation required")
        if verdict.decision is not Decision.ALLOW:
            raise ToolDenied(f"tool denied by {','.join(verdict.policy_ids)}")
        implementation = self.tools.get(name)
        if implementation is None:
            raise ToolDenied("tool implementation is unavailable")
        result = await implementation(**arguments)
        result_event = SecurityEvent(
            event_id="tool-result",
            surface=Surface.TOOL_RESULT,
            source_role=SourceRole.TOOL,
            trust=TrustLevel.UNTRUSTED,
            content=result,
            tool_name=name,
        )
        result_verdict = self.guard.evaluate(result_event)
        if result_verdict.decision in (Decision.BLOCK, Decision.REQUIRE_CONFIRMATION):
            raise ToolDenied(f"tool result denied by {','.join(result_verdict.policy_ids)}")
        return result_verdict.content


class AccountTools(GuardedTools):
    """Compatibility wrapper for the original read-only example."""

    def __init__(self, guard: FinancialGuard, lookup: Callable[[str], Awaitable[str]]):
        async def get_account_summary(account_id: str) -> str:
            return await lookup(account_id)

        super().__init__(guard, {"get_account_summary": get_account_summary})
