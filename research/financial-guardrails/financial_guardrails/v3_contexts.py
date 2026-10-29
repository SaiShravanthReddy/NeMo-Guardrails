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

"""Version 3 application-owned facts keyed by opaque replay identifiers."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from financial_guardrails.authorization import AuthorizationRequirement, TrustedAuthorizationContext
from financial_guardrails.outcome_judge import TrustedOutcomeContext


class TrustedAuthorizationFact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(pattern=r"^v3:[0-9a-f]{64}:-?\d+$")
    authorization: TrustedAuthorizationContext
    requirement: AuthorizationRequirement


class TrustedOutcomeFact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    conversation_id: str = Field(pattern=r"^v3:[0-9a-f]{64}:-1$")
    outcome: TrustedOutcomeContext


class TrustedFactsBundle(BaseModel):
    """External application facts; benchmark content and labels are prohibited."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "v3-trusted-facts-1"
    authorization_facts: tuple[TrustedAuthorizationFact, ...]
    outcome_facts: tuple[TrustedOutcomeFact, ...]

    def authorization_for(self, event_id: str) -> tuple[TrustedAuthorizationContext, AuthorizationRequirement]:
        try:
            fact = {item.event_id: item for item in self.authorization_facts}[event_id]
        except KeyError as exc:
            raise ValueError("trusted authorization facts are unavailable for this opaque event") from exc
        return fact.authorization, fact.requirement

    def outcome_for(self, conversation_id: str) -> TrustedOutcomeContext:
        try:
            return {item.conversation_id: item for item in self.outcome_facts}[conversation_id].outcome
        except KeyError as exc:
            raise ValueError("trusted outcome facts are unavailable for this opaque conversation") from exc


def load_trusted_facts(path: str | Path) -> TrustedFactsBundle:
    """Load complete external facts and reject duplicate opaque identifiers."""

    try:
        bundle = TrustedFactsBundle.model_validate_json(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("trusted facts could not be loaded") from exc
    authorization_ids = [item.event_id for item in bundle.authorization_facts]
    outcome_ids = [item.conversation_id for item in bundle.outcome_facts]
    if len(set(authorization_ids)) != len(authorization_ids):
        raise ValueError("trusted facts contain duplicate authorization event IDs")
    if len(set(outcome_ids)) != len(outcome_ids):
        raise ValueError("trusted facts contain duplicate outcome conversation IDs")
    return bundle
