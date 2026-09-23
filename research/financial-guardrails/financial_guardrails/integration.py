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

"""NeMo wiring for the shared Open Lakera policy engine."""

from __future__ import annotations

from contextvars import ContextVar
from pathlib import Path

from financial_guardrails.audit import AuditSink, InMemoryAuditSink
from financial_guardrails.configuration import DEFAULT_POLICY_PATH, load_policy
from financial_guardrails.engine import PolicyEngine
from financial_guardrails.schema import Decision, Mode, SecurityEvent, SourceRole, Surface, TrustLevel, Verdict
from nemoguardrails import RailsConfig
from nemoguardrails.actions import action
from nemoguardrails.actions.actions import ActionResult
from nemoguardrails.rails.llm.llmrails import LLMRails
from nemoguardrails.rails.llm.options import RailStatus, RailType

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config"
_audit: ContextVar[list[Verdict] | None] = ContextVar("open_lakera_audit", default=None)
_mode: ContextVar[Mode | None] = ContextVar("open_lakera_mode", default=None)


class GuardUnavailable(RuntimeError):
    """Validation did not complete; callers must withhold content or side effects."""


def register_policy_action(rails: LLMRails) -> None:
    settings = rails.config.custom_data["financial_guardrails"]
    configured_path = Path(settings.get("policy_file", DEFAULT_POLICY_PATH))
    if not configured_path.is_absolute():
        configured_path = (CONFIG_PATH / configured_path).resolve()
    engine = PolicyEngine(load_policy(configured_path))
    configured_mode = Mode(settings.get("mode", engine.config.default_mode))

    @action(name="screen_financial_text", is_system_action=True)
    async def screen(text: str, direction: str):
        surfaces = {
            "input": (Surface.INPUT, SourceRole.USER, TrustLevel.USER_INTENT),
            "retrieval": (Surface.RETRIEVAL, SourceRole.RETRIEVED_CONTENT, TrustLevel.UNTRUSTED),
            "output": (Surface.OUTPUT, SourceRole.ASSISTANT, TrustLevel.TRUSTED),
        }
        surface, role, trust = surfaces[direction]
        event = SecurityEvent(
            event_id="nemo-check",
            surface=surface,
            source_role=role,
            trust=trust,
            content=text,
        )
        verdict = engine.evaluate(event, _mode.get() or configured_mode)
        audit = _audit.get()
        if audit is not None:
            audit.append(verdict)
        updates = {}
        if verdict.decision is Decision.SANITIZE:
            context_key = {"input": "user_message", "retrieval": "relevant_chunks", "output": "bot_message"}[direction]
            updates[context_key] = verdict.content
        return ActionResult(return_value=verdict.decision.value, context_updates=updates)

    rails.register_action(screen, name="screen_financial_text")


class FinancialGuard:
    """Checks NeMo input/output rails and application-owned security surfaces."""

    def __init__(
        self,
        config_path: str | Path = CONFIG_PATH,
        policy_path: str | Path = DEFAULT_POLICY_PATH,
        mode: Mode | None = None,
        audit_sink: AuditSink | None = None,
    ):
        self.audit_sink = audit_sink or InMemoryAuditSink()
        self.engine = PolicyEngine(load_policy(policy_path))
        self.mode = mode or self.engine.config.default_mode
        config = RailsConfig.from_path(str(config_path))
        if config.models:
            raise ValueError("The offline profile must not configure provider models")
        expected = {"input": ["financial check input"], "output": ["financial check output"]}
        for direction, flows in expected.items():
            if getattr(config.rails, direction).flows != flows:
                raise ValueError(f"Missing or unexpected {direction} rails")
        config.custom_data["financial_guardrails"]["policy_file"] = str(Path(policy_path).resolve())
        config.custom_data["financial_guardrails"]["mode"] = self.mode.value
        self.rails = LLMRails(config)

    def evaluate(self, event: SecurityEvent, mode: Mode | None = None) -> Verdict:
        verdict = self.engine.evaluate(event, mode or self.mode)
        self.audit_sink.record(event, verdict)
        return verdict

    async def check(self, text: str, direction: str = "input") -> Verdict:
        if direction not in ("input", "output") or not isinstance(text, str) or not text.strip():
            raise ValueError("A nonempty text message and an explicit direction are required")
        audit: list[Verdict] = []
        audit_token = _audit.set(audit)
        mode_token = _mode.set(self.mode)
        try:
            role = "user" if direction == "input" else "assistant"
            rail_type = RailType.INPUT if direction == "input" else RailType.OUTPUT
            result = await self.rails.check_async([{"role": role, "content": text}], rail_types=[rail_type])
            if len(audit) != 1 or audit[0].detector_error:
                raise GuardUnavailable("The required financial classifiers did not complete")
            verdict = audit[0]
            event = SecurityEvent(
                event_id="nemo-check",
                surface=Surface.INPUT if direction == "input" else Surface.OUTPUT,
                source_role=SourceRole.USER if direction == "input" else SourceRole.ASSISTANT,
                trust=TrustLevel.USER_INTENT if direction == "input" else TrustLevel.TRUSTED,
                content=text,
            )
            self.audit_sink.record(event, verdict)
            expected = {
                Decision.ALLOW: RailStatus.PASSED,
                Decision.LOG_ONLY: RailStatus.PASSED,
                Decision.SANITIZE: RailStatus.MODIFIED,
                Decision.REQUIRE_CONFIRMATION: RailStatus.BLOCKED,
                Decision.BLOCK: RailStatus.BLOCKED,
            }
            if result.status != expected[verdict.decision]:
                raise GuardUnavailable("Policy and NeMo rail outcomes disagree")
            if (
                verdict.decision not in (Decision.BLOCK, Decision.REQUIRE_CONFIRMATION)
                and result.content != verdict.content
            ):
                raise GuardUnavailable("The checked content differs from the NeMo rail result")
            return verdict
        except GuardUnavailable:
            raise
        except Exception:
            raise GuardUnavailable("The financial guardrail could not complete") from None
        finally:
            _mode.reset(mode_token)
            _audit.reset(audit_token)
