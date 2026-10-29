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

"""Version 3 FinVault hard boundaries without name-only authorization decisions."""

from __future__ import annotations

from financial_guardrails.finvault_policy import FinVaultToolPolicy, load_finvault_policy
from financial_guardrails.schema import Decision, DetectorResult, Evidence, RiskCategory, SecurityEvent, Surface


class FinVaultV3BoundaryDetector:
    """Block only explicit tool-schema and bypass boundaries.

    Trusted authorization decides whether a known high-impact action may proceed.
    A tool name alone is not evidence of malicious intent.
    """

    name = "finvault_v3_boundary"

    def __init__(self, policy: FinVaultToolPolicy | None = None):
        self.policy = policy or load_finvault_policy()

    def detect(self, event: SecurityEvent) -> DetectorResult:
        if event.surface is not Surface.TOOL_CALL:
            return DetectorResult(detector=self.name)
        rule = self.policy.tools.get(event.tool_name or "")
        if rule is None:
            return self._result("FINVAULT-V3-TOOL-UNKNOWN", "Tool is absent from the frozen tool vocabulary.")
        if rule.decision == "block":
            return self._result("FINVAULT-V3-TOOL-DENY", "Tool is an explicit hard-deny boundary.")
        if not set(event.arguments).issubset(rule.allowed_arguments):
            return self._result(
                "FINVAULT-V3-TOOL-ARGUMENTS", "Tool call contains an argument outside its frozen schema."
            )
        if any(event.arguments.get(key) == value for key, value in rule.conditional_block_arguments.items()):
            return self._result(
                "FINVAULT-V3-DANGEROUS-ARGUMENT",
                "Tool call activates an explicitly prohibited override or bypass argument.",
            )
        return DetectorResult(detector=self.name)

    def _result(self, policy_id: str, explanation: str) -> DetectorResult:
        return DetectorResult(
            detector=self.name,
            decision=Decision.BLOCK,
            policy_ids=(policy_id,),
            risk_category=RiskCategory.AGENT_ACTION,
            evidence=(
                Evidence(
                    detector=self.name,
                    rule_id=policy_id,
                    summary="FinVault Version 3 hard-boundary condition",
                ),
            ),
            explanation=explanation,
        )
