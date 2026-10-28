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

from financial_guardrails.schema import Decision
from scripts.v3_judge_preflight import _effective_control_action


def test_authorization_confirmation_is_preserved_over_judge_allow():
    assert _effective_control_action(Decision.REQUIRE_CONFIRMATION, Decision.ALLOW) is Decision.REQUIRE_CONFIRMATION


def test_judge_block_is_preserved_over_authorization_allow():
    assert _effective_control_action(Decision.ALLOW, Decision.BLOCK) is Decision.BLOCK
