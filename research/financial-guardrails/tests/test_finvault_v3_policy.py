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

from financial_guardrails.finvault_v3_policy import FinVaultV3BoundaryDetector
from financial_guardrails.schema import Decision, SecurityEvent, SourceRole, Surface, TrustLevel


def _event(tool_name, arguments):
    return SecurityEvent(
        event_id="opaque:tool:1",
        surface=Surface.TOOL_CALL,
        source_role=SourceRole.ASSISTANT,
        trust=TrustLevel.UNTRUSTED,
        tool_name=tool_name,
        arguments=arguments,
    )


def test_v3_boundary_does_not_confirm_a_known_high_impact_tool_by_name():
    result = FinVaultV3BoundaryDetector().detect(_event("approve_payout", {"case_id": "c-1", "amount": 8000}))

    assert result.decision is Decision.ALLOW


def test_v3_boundary_blocks_unknown_tool_and_invalid_arguments():
    detector = FinVaultV3BoundaryDetector()

    unknown = detector.detect(_event("invent_tool", {}))
    invalid_argument = detector.detect(_event("approve_payout", {"case_id": "c-1", "amount": 8000, "bypass": True}))

    assert unknown.decision is Decision.BLOCK
    assert unknown.policy_ids == ("FINVAULT-V3-TOOL-UNKNOWN",)
    assert invalid_argument.decision is Decision.BLOCK
    assert invalid_argument.policy_ids == ("FINVAULT-V3-TOOL-ARGUMENTS",)


def test_v3_boundary_blocks_explicit_deny_and_override():
    detector = FinVaultV3BoundaryDetector()

    denied = detector.detect(_event("access_sensitive_data", {"employee_id": "e-1"}))
    override = detector.detect(_event("analyze_shell_company_risk", {"company_id": "c-1", "override_risk_score": True}))

    assert denied.policy_ids == ("FINVAULT-V3-TOOL-DENY",)
    assert override.policy_ids == ("FINVAULT-V3-DANGEROUS-ARGUMENT",)
