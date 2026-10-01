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

from pathlib import Path

from financial_guardrails.finvault_policy import FinVaultToolPolicyDetector, load_finvault_policy
from financial_guardrails.schema import Decision, SecurityEvent, SourceRole, Surface, TrustLevel


def _call(name, arguments):
    return SecurityEvent(
        event_id="tool-1",
        surface=Surface.TOOL_CALL,
        source_role=SourceRole.ASSISTANT,
        trust=TrustLevel.TRUSTED,
        tool_name=name,
        arguments=arguments,
    )


def test_policy_is_frozen_to_supplied_dataset():
    policy = load_finvault_policy()
    assert policy.dataset_sha256 == "743ff07b0604fb55094046a68b5c3afa327f2b3c31c3c80fab3737b7f033cbe6"
    assert len(policy.tools) == 197
    assert sum(rule.observed_calls for rule in policy.tools.values()) == 4838


def test_policy_does_not_depend_on_external_draft_files():
    assert Path(__file__).resolve().parents[1].joinpath("policies/finvault_tools_v1.yml").is_file()


def test_read_only_tool_is_allowed():
    result = FinVaultToolPolicyDetector().detect(_call("query_policy", {"policy_id": "p-1"}))
    assert result.decision is Decision.ALLOW


def test_consequential_action_requires_confirmation():
    result = FinVaultToolPolicyDetector().detect(
        _call("issue_policy", {"app_id": "a-1", "override_risk": False, "skip_verification": False})
    )
    assert result.decision is Decision.REQUIRE_CONFIRMATION


def test_dangerous_argument_blocks_even_on_otherwise_allowed_tool():
    result = FinVaultToolPolicyDetector().detect(
        _call("generate_sales_script", {"hide_risks": True, "product_id": "p-1"})
    )
    assert result.decision is Decision.BLOCK
    assert result.policy_ids == ("FINVAULT-TOOL-DANGEROUS-ARGUMENT",)


def test_unknown_tool_and_argument_fail_closed():
    detector = FinVaultToolPolicyDetector()
    assert detector.detect(_call("unknown", {})).decision is Decision.BLOCK
    assert detector.detect(_call("query_policy", {"unexpected": True})).decision is Decision.BLOCK
