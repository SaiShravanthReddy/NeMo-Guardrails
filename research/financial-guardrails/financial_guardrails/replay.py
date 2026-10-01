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

"""Safe conversion of benchmark traces into guardrail events.

The replay path inspects recorded actions. It never imports, resolves, or executes a
tool named by a benchmark record.
"""

from __future__ import annotations

import ast
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from financial_guardrails.datasets import BenchmarkCase, BenchmarkMessage
from financial_guardrails.schema import SecurityEvent, SourceRole, Surface, TrustLevel


class ParsedToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    arguments: dict[str, Any]


def parse_finvault_tool_call(text: str) -> ParsedToolCall:
    """Parse FinVault's recorded ``{'tool': ..., 'args': ...}`` form safely."""
    try:
        node = ast.parse(text, mode="eval").body
    except (SyntaxError, ValueError) as exc:
        raise ValueError("invalid recorded tool-call syntax") from exc
    value = _literal(node)
    if not isinstance(value, dict) or not set(value).issubset({"tool", "args", "reasoning", "parameters"}):
        raise ValueError("recorded tool call has unsupported fields")
    name = value.get("tool")
    arguments = value.get("args")
    if not isinstance(name, str) or not name.strip() or not isinstance(arguments, dict):
        raise ValueError("recorded tool call requires a tool name and argument object")
    if any(not isinstance(key, str) for key in arguments):
        raise ValueError("recorded tool arguments require string keys")
    return ParsedToolCall(name=name, arguments=arguments)


def event_from_message(case: BenchmarkCase, message: BenchmarkMessage) -> SecurityEvent:
    event_id = f"{case.case_id}:{message.turn_index}"
    if message.kind == "tool_call":
        parsed = parse_finvault_tool_call(message.content)
        return SecurityEvent(
            event_id=event_id,
            content=message.content,
            surface=Surface.TOOL_CALL,
            source_role=SourceRole.ASSISTANT,
            trust=TrustLevel.TRUSTED,
            tool_name=parsed.name,
            arguments=parsed.arguments,
        )
    if message.kind == "tool_result":
        return SecurityEvent(
            event_id=event_id,
            content=message.content,
            surface=Surface.TOOL_RESULT,
            source_role=SourceRole.TOOL,
            trust=TrustLevel.UNTRUSTED,
        )
    if message.role == "user":
        return SecurityEvent(
            event_id=event_id,
            content=message.content,
            surface=Surface.INPUT,
            source_role=SourceRole.USER,
            trust=TrustLevel.USER_INTENT,
        )
    return SecurityEvent(
        event_id=event_id,
        content=message.content,
        surface=Surface.OUTPUT,
        source_role=SourceRole.ASSISTANT,
        trust=TrustLevel.TRUSTED,
    )


def _literal(node: ast.AST) -> Any:
    if isinstance(node, ast.Name) and node.id in {"true", "false"}:
        return node.id == "true"
    if isinstance(node, ast.Constant) and isinstance(node.value, (str, int, float, bool, type(None))):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        operand = _literal(node.operand)
        if isinstance(operand, (int, float)) and not isinstance(operand, bool):
            return -operand
        raise ValueError("recorded tool call contains an invalid negative value")
    if isinstance(node, ast.List):
        return [_literal(item) for item in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_literal(item) for item in node.elts)
    if isinstance(node, ast.Dict):
        result = {}
        for key, value in zip(node.keys, node.values, strict=True):
            if key is None:
                raise ValueError("recorded tool call cannot unpack a dictionary")
            result[_literal(key)] = _literal(value)
        return result
    raise ValueError("recorded tool call contains a non-literal value")
