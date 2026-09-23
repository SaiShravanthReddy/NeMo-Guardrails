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

"""NeMo wiring with request-local evidence that an actual classifier ran."""

from __future__ import annotations

import json
import os
from contextvars import ContextVar
from pathlib import Path

from financial_guardrails.policy import Decision, Direction, Policy, RuleClassifier
from nemoguardrails import RailsConfig
from nemoguardrails.actions import action
from nemoguardrails.actions.actions import ActionResult
from nemoguardrails.rails.llm.llmrails import LLMRails
from nemoguardrails.rails.llm.options import RailStatus, RailType

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config"
_audit: ContextVar[list[Decision] | None] = ContextVar("financial_guard_audit", default=None)


class GuardUnavailable(RuntimeError):
    """Validation did not complete; callers must withhold content/tool execution."""


def register_policy_action(rails: LLMRails) -> None:
    settings = dict(rails.config.custom_data["financial_guardrails"])
    protected_values = os.environ.get("FIN_GUARD_PROTECTED_VALUES")
    if protected_values is not None:
        settings["protected_values"] = json.loads(protected_values)
    classifier = RuleClassifier(Policy.model_validate(settings))

    @action(name="screen_financial_text", is_system_action=True)
    async def screen(text: str, direction: Direction):
        try:
            verdict = classifier.classify(text, direction)
            if not isinstance(verdict, Decision) or verdict.decision not in ("allow", "redact", "block"):
                raise ValueError("Invalid classifier decision")
        except Exception:
            verdict = Decision("error", "", ("CHECK-ERROR",))
        audit = _audit.get()
        if audit is not None:
            audit.append(verdict)
        updates = {}
        if verdict.decision == "redact":
            updates["user_message" if direction == "input" else "bot_message"] = verdict.content
        return ActionResult(return_value=verdict.decision, context_updates=updates)

    rails.register_action(screen, name="screen_financial_text")


class FinancialGuard:
    """Checks one text surface at a time; the caller owns generation and history."""

    def __init__(self, config_path: str | Path = CONFIG_PATH):
        config = RailsConfig.from_path(str(config_path))
        if config.models:
            raise ValueError("The offline profile must not configure provider models")
        expected = {"input": ["financial check input"], "output": ["financial check output"]}
        for direction, flows in expected.items():
            if getattr(config.rails, direction).flows != flows:
                raise ValueError(f"Missing or unexpected {direction} rails")
        # Import the concrete engine: custom actions require the Colang runtime.
        self.rails = LLMRails(config)

    async def check(self, text: str, direction: Direction = "input") -> Decision:
        if direction not in ("input", "output") or not isinstance(text, str) or not text.strip():
            raise ValueError("A nonempty text message and an explicit direction are required")
        audit: list[Decision] = []
        token = _audit.set(audit)
        try:
            role = "user" if direction == "input" else "assistant"
            rail_type = RailType.INPUT if direction == "input" else RailType.OUTPUT
            result = await self.rails.check_async([{"role": role, "content": text}], rail_types=[rail_type])
            if len(audit) != 1 or audit[0].decision == "error":
                raise GuardUnavailable("The required financial classifier did not complete")
            verdict = audit[0]
            expected = {"allow": RailStatus.PASSED, "redact": RailStatus.MODIFIED, "block": RailStatus.BLOCKED}
            if result.status != expected[verdict.decision]:
                raise GuardUnavailable("Classifier and rail outcomes disagree")
            if verdict.decision != "block" and result.content != verdict.content:
                raise GuardUnavailable("The checked content differs from the rail result")
            return verdict
        except GuardUnavailable:
            raise
        except Exception:
            raise GuardUnavailable("The financial guardrail could not complete") from None
        finally:
            _audit.reset(token)
