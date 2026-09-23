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

"""Audit records intentionally omit message text, arguments, and detector excerpts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from financial_guardrails.schema import SecurityEvent, Verdict


class AuditSink(Protocol):
    def record(self, event: SecurityEvent, verdict: Verdict) -> None: ...


@dataclass
class InMemoryAuditSink:
    records: list[dict] = field(default_factory=list)

    def record(self, event: SecurityEvent, verdict: Verdict) -> None:
        self.records.append(
            {
                "recorded_at": datetime.now(UTC).isoformat(),
                "event_id": event.event_id,
                "surface": event.surface.value,
                "source_role": event.source_role.value,
                "trust": event.trust.value,
                "mode": verdict.mode.value,
                "decision": verdict.decision.value,
                "recommended_decision": verdict.recommended_decision.value,
                "policy_ids": list(verdict.policy_ids),
                "risk_category": verdict.risk_category.value,
                "detector_error": verdict.detector_error,
            }
        )
