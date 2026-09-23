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

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Surface(str, Enum):
    SYSTEM = "system"
    INPUT = "input"
    RETRIEVAL = "retrieval"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    OUTPUT = "output"


class SourceRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    RETRIEVED_CONTENT = "retrieved_content"
    TOOL = "tool"
    ASSISTANT = "assistant"


class TrustLevel(str, Enum):
    TRUSTED = "trusted"
    USER_INTENT = "user_intent"
    UNTRUSTED = "untrusted"


class Mode(str, Enum):
    DETECT = "detect"
    ENFORCE = "enforce"


class Decision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    SANITIZE = "sanitize"
    REQUIRE_CONFIRMATION = "require_confirmation"
    LOG_ONLY = "log_only"


class RiskCategory(str, Enum):
    NONE = "none"
    PROMPT_INJECTION = "prompt_injection"
    JAILBREAK = "jailbreak"
    HARMFUL_CONTENT = "harmful_content"
    DATA_LEAKAGE = "data_leakage"
    MALICIOUS_LINK = "malicious_link"
    AGENT_ACTION = "agent_action"
    RESOURCE_LIMIT = "resource_limit"
    DETECTOR_FAILURE = "detector_failure"


class DetectorStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    DISABLED = "disabled"


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    detector: str
    rule_id: str
    summary: str
    start: int | None = Field(default=None, ge=0)
    end: int | None = Field(default=None, ge=0)
    redacted_excerpt: str | None = None


class SecurityEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(min_length=1)
    surface: Surface
    source_role: SourceRole
    trust: TrustLevel
    content: str = ""
    actor_id: str | None = None
    tool_name: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    permissions: frozenset[str] = Field(default_factory=frozenset)
    allowed_resource_ids: frozenset[str] = Field(default_factory=frozenset)
    authorized_by_event_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_role_and_surface(self):
        expected = {
            Surface.SYSTEM: {SourceRole.SYSTEM},
            Surface.INPUT: {SourceRole.USER},
            Surface.RETRIEVAL: {SourceRole.RETRIEVED_CONTENT},
            Surface.TOOL_CALL: {SourceRole.ASSISTANT},
            Surface.TOOL_RESULT: {SourceRole.TOOL},
            Surface.OUTPUT: {SourceRole.ASSISTANT},
        }
        if self.source_role not in expected[self.surface]:
            raise ValueError("source_role is incompatible with surface")
        if self.surface is Surface.SYSTEM and self.trust is not TrustLevel.TRUSTED:
            raise ValueError("system instructions must come from trusted application configuration")
        if self.surface in (Surface.RETRIEVAL, Surface.TOOL_RESULT) and self.trust is not TrustLevel.UNTRUSTED:
            raise ValueError("retrieval and tool results must be untrusted")
        if self.surface is Surface.TOOL_CALL and not self.tool_name:
            raise ValueError("tool calls require tool_name")
        return self


class DetectorResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    detector: str
    status: DetectorStatus = DetectorStatus.OK
    decision: Decision = Decision.ALLOW
    policy_ids: tuple[str, ...] = ()
    risk_category: RiskCategory = RiskCategory.NONE
    evidence: tuple[Evidence, ...] = ()
    explanation: str = ""
    sanitized_content: str | None = None
    error_code: str | None = None


class Verdict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    policy_id: str
    policy_version: str
    mode: Mode
    decision: Decision
    recommended_decision: Decision
    policy_ids: tuple[str, ...]
    risk_category: RiskCategory
    evidence: tuple[Evidence, ...]
    explanation: str
    detector_error: bool
    detector_statuses: dict[str, DetectorStatus]
    content: str

    @property
    def intervened(self) -> bool:
        return self.mode is Mode.ENFORCE and self.decision in {
            Decision.BLOCK,
            Decision.SANITIZE,
            Decision.REQUIRE_CONFIRMATION,
        }

    @property
    def policies(self) -> tuple[str, ...]:
        """Compatibility alias for the first baseline API."""
        return self.policy_ids
