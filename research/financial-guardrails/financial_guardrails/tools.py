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

"""Example read-only tool boundary, with authorization supplied by trusted code."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from financial_guardrails.integration import FinancialGuard


class ToolDenied(PermissionError):
    pass


@dataclass(frozen=True)
class Principal:
    subject: str
    account_ids: frozenset[str]
    permissions: frozenset[str]


class AccountTools:
    """Only a read-only lookup is enabled; all other tool names are denied."""

    def __init__(self, guard: FinancialGuard, lookup: Callable[[str], Awaitable[str]]):
        self.guard = guard
        self.lookup = lookup

    async def execute(self, name: str, arguments: dict, principal: Principal) -> str:
        if (
            not principal.subject
            or name != "get_account_summary"
            or "account:read" not in principal.permissions
            or not isinstance(arguments, dict)
            or set(arguments) != {"account_id"}
            or not isinstance(arguments["account_id"], str)
            or arguments["account_id"] not in principal.account_ids
        ):
            raise ToolDenied("TOOL-01: tool or account access denied")
        account_id = arguments["account_id"]
        argument_check = await self.guard.check(json.dumps({"account_id": account_id}), "output")
        if argument_check.decision != "allow":
            raise ToolDenied("Tool arguments cannot be released")
        result = await self.lookup(account_id)
        # Tool results are untrusted input, then screened before release to a user/model.
        input_check = await self.guard.check(result, "input")
        if input_check.decision == "block":
            raise ToolDenied("Tool result contains prohibited instructions or data")
        output_check = await self.guard.check(input_check.content, "output")
        if output_check.decision == "block":
            raise ToolDenied("Tool result cannot be released")
        return output_check.content
