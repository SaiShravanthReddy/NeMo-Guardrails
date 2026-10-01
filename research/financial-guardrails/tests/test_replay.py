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

import pytest
from financial_guardrails.replay import parse_finvault_tool_call


def test_parses_reviewed_finvault_literal_format():
    parsed = parse_finvault_tool_call("{'tool': 'lookup', 'args': {'active': true, 'count': -2}}")
    assert parsed.name == "lookup"
    assert parsed.arguments == {"active": True, "count": -2}


@pytest.mark.parametrize(
    "value",
    [
        "run_tool()",
        "{'tool': 'x', 'args': __import__('os').environ}",
        "{'tool': 'x', 'args': {}, 'unexpected': 'field'}",
        "{'tool': '', 'args': {}}",
    ],
)
def test_rejects_executable_or_unsupported_forms(value):
    with pytest.raises(ValueError):
        parse_finvault_tool_call(value)
