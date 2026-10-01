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

"""Evaluation-only policy for FinVault's recorded tool vocabulary."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from financial_guardrails.schema import Decision, DetectorResult, Evidence, RiskCategory, SecurityEvent, Surface

DEFAULT_FINVAULT_POLICY_PATH = Path(__file__).resolve().parents[1] / "policies" / "finvault_tools_v1.yml"


class FinVaultToolRule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: Literal["allow", "require_confirmation", "block"]
    observed_calls: int = Field(ge=1)
    allowed_arguments: tuple[str, ...]
    conditional_block_arguments: dict[str, Any] = Field(default_factory=dict)
    rationale: str = Field(min_length=1)


class FinVaultToolPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str
    policy_id: str
    policy_version: str
    dataset_key: Literal["finvault-v5-fixed-full"]
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tools: dict[str, FinVaultToolRule]


def load_finvault_policy(path: str | Path = DEFAULT_FINVAULT_POLICY_PATH) -> FinVaultToolPolicy:
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError("FinVault tool policy could not be loaded") from exc
    return FinVaultToolPolicy.model_validate(raw)


class FinVaultToolPolicyDetector:
    """Classify recorded calls without claiming production authorization."""

    name = "finvault_tool_policy"

    def __init__(self, policy: FinVaultToolPolicy | None = None):
        self.policy = policy or load_finvault_policy()

    def detect(self, event: SecurityEvent) -> DetectorResult:
        if event.surface is not Surface.TOOL_CALL:
            return DetectorResult(detector=self.name)
        rule = self.policy.tools.get(event.tool_name or "")
        if rule is None:
            return self._result(Decision.BLOCK, "FINVAULT-TOOL-UNKNOWN", "Tool is absent from the frozen policy.")
        if not set(event.arguments).issubset(rule.allowed_arguments):
            return self._result(
                Decision.BLOCK,
                "FINVAULT-TOOL-ARGUMENTS",
                "Tool call contains an argument absent from the frozen schema.",
            )
        if any(event.arguments.get(key) == value for key, value in rule.conditional_block_arguments.items()):
            return self._result(
                Decision.BLOCK,
                "FINVAULT-TOOL-DANGEROUS-ARGUMENT",
                "Tool call activates an explicitly prohibited override or bypass argument.",
            )
        decision = Decision(rule.decision)
        if decision is Decision.ALLOW:
            return DetectorResult(detector=self.name)
        policy_id = "FINVAULT-TOOL-DENY" if decision is Decision.BLOCK else "FINVAULT-TOOL-CONFIRM"
        return self._result(decision, policy_id, rule.rationale)

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
                    summary="FinVault evaluation tool policy condition",
                ),
            ),
            explanation=explanation,
        )
