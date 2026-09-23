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

"""Application hook for screening retrieved chunks before prompt construction."""

from __future__ import annotations

from financial_guardrails.integration import FinancialGuard
from financial_guardrails.schema import Decision, SecurityEvent, SourceRole, Surface, TrustLevel, Verdict


class RetrievalDenied(PermissionError):
    pass


def screen_retrieved_chunks(guard: FinancialGuard, chunks: list[str]) -> tuple[list[str], tuple[Verdict, ...]]:
    screened: list[str] = []
    verdicts: list[Verdict] = []
    for index, chunk in enumerate(chunks):
        verdict = guard.evaluate(
            SecurityEvent(
                event_id=f"retrieval-{index}",
                surface=Surface.RETRIEVAL,
                source_role=SourceRole.RETRIEVED_CONTENT,
                trust=TrustLevel.UNTRUSTED,
                content=chunk,
            )
        )
        verdicts.append(verdict)
        if verdict.decision in (Decision.BLOCK, Decision.REQUIRE_CONFIRMATION):
            raise RetrievalDenied(f"retrieval blocked by {','.join(verdict.policy_ids)}")
        screened.append(verdict.content)
    return screened, tuple(verdicts)
