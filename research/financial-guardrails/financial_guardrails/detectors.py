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

from __future__ import annotations

import ipaddress
import re
import unicodedata
from collections.abc import Iterable
from typing import Protocol
from urllib.parse import unquote, urlsplit

from financial_guardrails.configuration import PolicyConfig
from financial_guardrails.schema import (
    Decision,
    DetectorResult,
    Evidence,
    RiskCategory,
    SecurityEvent,
    Surface,
    TrustLevel,
)


class Detector(Protocol):
    name: str

    def detect(self, event: SecurityEvent) -> DetectorResult: ...


def normalize(text: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFKC", text) if unicodedata.category(char) != "Cf")


def evidence(name: str, rule: str, summary: str, match: re.Match[str] | None = None) -> Evidence:
    return Evidence(
        detector=name,
        rule_id=rule,
        summary=summary,
        start=match.start() if match else None,
        end=match.end() if match else None,
        redacted_excerpt="[REDACTED]" if match else None,
    )


INJECTION = re.compile(
    r"(?:^|[\n.!?;]\s*)(?:please\s+)?(?:"
    r"(?:ignore|disregard|override)\s+(?:all\s+)?(?:previous|prior|system|developer)\s+(?:instructions|rules|prompts)"
    r"|(?:reveal|print|show|repeat)\s+(?:your\s+|the\s+)?(?:hidden\s+)?(?:system|developer)\s+prompt"
    r"|忽略(?:之前|以前|所有|系统|开发者).{0,8}(?:指令|规则)"
    r"|(?:输出|泄露|显示)(?:你的|完整的)?系统提示词)",
    re.IGNORECASE,
)
JAILBREAK = re.compile(
    r"(?:^|[\n.!?;]\s*)(?:you are now (?:dan|in developer mode)|act as .*? with no (?:rules|restrictions)|"
    r"bypass (?:the )?(?:safety|guardrails?|filters?)|do anything now)",
    re.IGNORECASE,
)


class PromptDefenseDetector:
    name = "prompt_defense_rules"

    def detect(self, event: SecurityEvent) -> DetectorResult:
        if event.surface is Surface.SYSTEM:
            return DetectorResult(detector=self.name)
        text = normalize(event.content)
        injection = INJECTION.search(text)
        jailbreak = JAILBREAK.search(text)
        if injection:
            policy = "INJ-02" if event.trust is TrustLevel.UNTRUSTED else "INJ-01"
            return DetectorResult(
                detector=self.name,
                decision=Decision.BLOCK,
                policy_ids=(policy,),
                risk_category=RiskCategory.PROMPT_INJECTION,
                evidence=(evidence(self.name, policy, "instruction-override pattern", injection),),
                explanation="Untrusted instructions cannot override the active control context.",
            )
        if jailbreak:
            return DetectorResult(
                detector=self.name,
                decision=Decision.BLOCK,
                policy_ids=("JAIL-01",),
                risk_category=RiskCategory.JAILBREAK,
                evidence=(evidence(self.name, "JAIL-01", "jailbreak role or bypass pattern", jailbreak),),
                explanation="The request attempts to disable or evade safeguards.",
            )
        return DetectorResult(detector=self.name)


class LimitDetector:
    name = "message_limits"

    def __init__(self, config: PolicyConfig):
        self.max_chars = config.limits["max_chars"]

    def detect(self, event: SecurityEvent) -> DetectorResult:
        if len(event.content) <= self.max_chars:
            return DetectorResult(detector=self.name)
        return DetectorResult(
            detector=self.name,
            decision=Decision.BLOCK,
            policy_ids=("LIMIT-01",),
            risk_category=RiskCategory.RESOURCE_LIMIT,
            evidence=(evidence(self.name, "LIMIT-01", "message exceeds configured character limit"),),
            explanation="The message exceeds the configured processing limit.",
        )


HARMFUL_RULES = {
    "SAFE-FRAUD": re.compile(
        r"(?:help|teach|show)\s+me\s+(?:how\s+to\s+)?(?:launder money|evade (?:aml|kyc)|forge (?:bank|income)|steal credentials)",
        re.IGNORECASE,
    ),
    "SAFE-MALWARE": re.compile(
        r"(?:write|build|create)\s+(?:me\s+)?(?:ransomware|credential[- ]stealing malware|a phishing kit)",
        re.IGNORECASE,
    ),
    "SAFE-VIOLENCE": re.compile(
        r"(?:give me|provide)\s+(?:detailed )?instructions to (?:kill|poison|bomb)", re.IGNORECASE
    ),
    "SAFE-SELF-HARM": re.compile(r"(?:best|least painful) way to (?:kill myself|commit suicide)", re.IGNORECASE),
}


class ContentSafetyDetector:
    name = "content_safety_rules"

    def detect(self, event: SecurityEvent) -> DetectorResult:
        text = normalize(event.content)
        for policy, pattern in HARMFUL_RULES.items():
            match = pattern.search(text)
            if match:
                return DetectorResult(
                    detector=self.name,
                    decision=Decision.BLOCK,
                    policy_ids=(policy,),
                    risk_category=RiskCategory.HARMFUL_CONTENT,
                    evidence=(evidence(self.name, policy, "explicit harmful-assistance request", match),),
                    explanation="The content requests operational assistance in a prohibited category.",
                )
        return DetectorResult(detector=self.name)


EMAIL = re.compile(r"(?<![\w.+-])[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9-]+(?:\.[A-Z0-9-]+)+", re.IGNORECASE)
CARD = re.compile(r"(?<!\w)(?:[0-9][ -]?){12,18}[0-9](?!\w)")
PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
CREDENTIAL = re.compile(
    r"\b(?:api[_ -]?key|access[_ -]?token|client[_ -]?secret|password)\s*[:=]\s*[\"']?[A-Za-z0-9_./+\-=]{12,}",
    re.IGNORECASE,
)
ACCOUNT_NUMBER = re.compile(r"\b(?:account|routing)\s*(?:number|no\.?|#)\s*[:=]?\s*\d{8,17}\b", re.IGNORECASE)
SYSTEM_LEAK = re.compile(r"\b(?:system|developer) (?:prompt|instructions?)\s*[:=]", re.IGNORECASE)


def is_payment_card(value: str) -> bool:
    digits = [int(char) for char in value if char.isdigit()]
    if not 13 <= len(digits) <= 19 or len(set(digits)) == 1:
        return False
    total = 0
    for index, digit in enumerate(reversed(digits)):
        if index % 2:
            digit = digit * 2
            digit = digit - 9 if digit > 9 else digit
        total += digit
    return total % 10 == 0


class DataLeakageDetector:
    name = "data_leakage_rules"

    def __init__(self, config: PolicyConfig):
        self.config = config.data_loss_prevention

    def detect(self, event: SecurityEvent) -> DetectorResult:
        text = normalize(event.content)
        decoded = unquote(text)
        blockers: list[tuple[str, re.Match[str] | None, str]] = []
        if self.config.block_private_keys and (match := PRIVATE_KEY.search(text)):
            blockers.append(("DLP-CREDENTIAL", match, "private-key material"))
        if match := CREDENTIAL.search(text):
            blockers.append(("DLP-CREDENTIAL", match, "credential-like assignment"))
        if event.surface in (Surface.OUTPUT, Surface.TOOL_RESULT) and (match := ACCOUNT_NUMBER.search(text)):
            blockers.append(("DLP-FINANCIAL", match, "sensitive financial identifier"))
        if event.surface is Surface.OUTPUT and (match := SYSTEM_LEAK.search(text)):
            blockers.append(("DLP-SYSTEM", match, "system-instruction disclosure"))
        if self.config.block_payment_cards:
            blockers.extend(
                ("DLP-FINANCIAL", match, "payment-card number")
                for match in CARD.finditer(text)
                if is_payment_card(match.group())
            )
        if any(normalize(value) in decoded for value in self.config.protected_values):
            blockers.append(("DLP-PROTECTED", None, "configured protected value"))
        if blockers:
            return DetectorResult(
                detector=self.name,
                decision=Decision.BLOCK,
                policy_ids=tuple(dict.fromkeys(item[0] for item in blockers)),
                risk_category=RiskCategory.DATA_LEAKAGE,
                evidence=tuple(evidence(self.name, rule, summary, match) for rule, match, summary in blockers),
                explanation="Sensitive data must not cross this boundary.",
            )
        if self.config.redact_email and (matches := list(EMAIL.finditer(text))):
            return DetectorResult(
                detector=self.name,
                decision=Decision.SANITIZE,
                policy_ids=("DLP-PII",),
                risk_category=RiskCategory.DATA_LEAKAGE,
                evidence=tuple(evidence(self.name, "DLP-PII", "email address", match) for match in matches),
                explanation="Email addresses are masked before release.",
                sanitized_content=EMAIL.sub("[EMAIL]", text),
            )
        return DetectorResult(detector=self.name)


URL = re.compile(r"(?:[a-z][a-z0-9+.-]*://|www\.|(?<!:)//)[^\s<>\"']+", re.IGNORECASE)
DANGEROUS_SCHEME = re.compile(r"\b(?:javascript|data|file|vbscript)\s*:", re.IGNORECASE)


def unsafe_urls(text: str, allowed_hosts: Iterable[str], denied_hosts: Iterable[str]) -> list[str]:
    if DANGEROUS_SCHEME.search(text):
        return ["dangerous-scheme"]
    unsafe = []
    allowed = set(allowed_hosts)
    denied = set(denied_hosts)
    for match in URL.finditer(text):
        candidate = match.group().rstrip(".,;!?)\u3002")
        try:
            parts = urlsplit(candidate)
            host = (parts.hostname or "").encode("idna").decode("ascii").lower()
            try:
                address = ipaddress.ip_address(host.strip("[]"))
                nonpublic_ip = not address.is_global
            except ValueError:
                nonpublic_ip = False
            if (
                parts.scheme.lower() != "https"
                or parts.username is not None
                or parts.password is not None
                or host in denied
                or host not in allowed
                or parts.port not in (None, 443)
                or nonpublic_ip
                or "\\" in candidate
                or any(ord(char) < 32 for char in candidate)
            ):
                unsafe.append(host or "invalid-url")
        except (UnicodeError, ValueError):
            unsafe.append("invalid-url")
    return unsafe


class LinkDetector:
    name = "link_rules"

    def __init__(self, config: PolicyConfig):
        self.config = config.links

    def detect(self, event: SecurityEvent) -> DetectorResult:
        if event.surface not in (Surface.OUTPUT, Surface.TOOL_RESULT):
            return DetectorResult(detector=self.name)
        matches = unsafe_urls(event.content, self.config.allowed_hosts, self.config.denied_hosts)
        if not matches:
            return DetectorResult(detector=self.name)
        return DetectorResult(
            detector=self.name,
            decision=Decision.BLOCK,
            policy_ids=("URL-01",),
            risk_category=RiskCategory.MALICIOUS_LINK,
            evidence=(evidence(self.name, "URL-01", "URL violates local destination policy"),),
            explanation="The destination is not permitted by the local URL policy.",
        )


class ToolPolicyDetector:
    name = "tool_policy"

    def __init__(self, config: PolicyConfig):
        self.config = config.tools

    def detect(self, event: SecurityEvent) -> DetectorResult:
        if event.surface is not Surface.TOOL_CALL:
            return DetectorResult(detector=self.name)
        tool_name = event.tool_name or ""
        if tool_name in self.config.denied or tool_name not in self.config.allowed:
            return self._result(Decision.BLOCK, "TOOL-DENY", "Tool is denied or absent from the allowlist.")
        rule = self.config.allowed[tool_name]
        if rule.required_permission not in event.permissions:
            return self._result(Decision.BLOCK, "TOOL-PERMISSION", "The principal lacks the required permission.")
        if set(event.arguments) != set(rule.allowed_arguments):
            return self._result(Decision.BLOCK, "TOOL-ARGUMENTS", "Tool arguments do not match the configured schema.")
        resource_ids = {
            value for key, value in event.arguments.items() if key.endswith("account_id") and isinstance(value, str)
        }
        if resource_ids - event.allowed_resource_ids:
            return self._result(
                Decision.BLOCK, "TOOL-RESOURCE", "The principal is not authorized for a referenced account."
            )
        transfers_data = any(key in event.arguments for key in self.config.external_transfer_arguments)
        if transfers_data and "data:export" not in event.permissions:
            return self._result(Decision.BLOCK, "TOOL-TRANSFER", "External data transfer is not authorized.")
        if (tool_name in self.config.confirmation_required or transfers_data) and not event.authorized_by_event_ids:
            return self._result(
                Decision.REQUIRE_CONFIRMATION,
                "TOOL-CONFIRM",
                "A trusted application confirmation is required for this high-impact action.",
            )
        return DetectorResult(detector=self.name)

    def _result(self, decision: Decision, policy: str, explanation: str) -> DetectorResult:
        return DetectorResult(
            detector=self.name,
            decision=decision,
            policy_ids=(policy,),
            risk_category=RiskCategory.AGENT_ACTION,
            evidence=(evidence(self.name, policy, "tool policy condition"),),
            explanation=explanation,
        )
