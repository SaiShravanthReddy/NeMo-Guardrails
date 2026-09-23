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

"""Bounded, auditable rules. These are classifiers, not semantic safety models."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal
from urllib.parse import unquote, urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

Direction = Literal["input", "output"]


class Policy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    max_chars: int = Field(default=20000, ge=1, le=100000)
    redact_email: bool = True
    block_payment_cards: bool = True
    allowed_link_hosts: list[str] = Field(default_factory=list)
    protected_values: list[str] = Field(default_factory=list, repr=False)

    @field_validator("allowed_link_hosts")
    @classmethod
    def exact_hosts(cls, hosts: list[str]) -> list[str]:
        for host in hosts:
            if not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", host):
                raise ValueError("Use exact lowercase ASCII hostnames, without URL paths or wildcards")
        return hosts

    @field_validator("protected_values")
    @classmethod
    def nonempty_protected_values(cls, values: list[str]) -> list[str]:
        if any(len(normalize(value)) < 8 for value in values):
            raise ValueError("Protected values must contain at least eight normalized characters")
        return values


@dataclass(frozen=True)
class Decision:
    decision: Literal["allow", "redact", "block", "error"]
    content: str
    policies: tuple[str, ...] = ()


def normalize(text: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFKC", text) if unicodedata.category(char) != "Cf")


# Anchoring reduces false positives on ordinary explanations of prompt attacks.
INJECTION = re.compile(
    r"(?:^|[\n.!?;]\s*)(?:please\s+)?(?:"
    r"(?:ignore|disregard|override)\s+(?:all\s+)?(?:previous|prior|system|developer)\s+(?:instructions|rules|prompts)"
    r"|(?:reveal|print|show|repeat)\s+(?:your\s+|the\s+)?(?:hidden\s+)?(?:system|developer)\s+prompt"
    r"|忽略(?:之前|以前|所有|系统|开发者).{0,8}(?:指令|规则)"
    r"|(?:输出|泄露|显示)(?:你的|完整的)?系统提示词)",
    re.IGNORECASE,
)
FINANCIAL_ABUSE = re.compile(
    r"(?:^|[\n.!?;]\s*)(?:please\s+)?(?:"
    r"(?:(?:help|teach|show)\s+me\s+(?:how\s+to\s+)?|how\s+(?:do|can)\s+i\s+)"
    r"(?:launder\s+money|evade\s+(?:aml|kyc)\s+checks|forge\s+(?:bank\s+statements|income\s+documents))"
    r"|(?:教我|帮我)(?:如何)?(?:洗钱|伪造银行流水|绕过反洗钱审查))",
    re.IGNORECASE,
)
EMAIL = re.compile(r"(?<![\w.+-])[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9-]+(?:\.[A-Z0-9-]+)+", re.IGNORECASE)
CARD = re.compile(r"(?<!\w)(?:[0-9][ -]?){12,18}[0-9](?!\w)")
PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
LINK = re.compile(r"(?:[a-z][a-z0-9+.-]*://|www\.|(?<!:)//)[^\s<>\"']+", re.IGNORECASE)
DANGEROUS_SCHEME = re.compile(r"\b(?:javascript|data|file|vbscript)\s*:", re.IGNORECASE)


def is_payment_card(value: str) -> bool:
    digits = [int(c) for c in value if c.isdigit()]
    if not 13 <= len(digits) <= 19 or len(set(digits)) == 1:
        return False
    total = 0
    for index, digit in enumerate(reversed(digits)):
        if index % 2:
            digit *= 2
            digit = digit - 9 if digit > 9 else digit
        total += digit
    return total % 10 == 0


def restricted_link(text: str, allowed_hosts: list[str]) -> bool:
    if DANGEROUS_SCHEME.search(text):
        return True
    for match in LINK.finditer(text):
        candidate = match.group().rstrip(".,;!?)\u3002")
        try:
            parts = urlsplit(candidate)
            if (
                parts.scheme.lower() != "https"
                or parts.username is not None
                or parts.password is not None
                or parts.hostname not in allowed_hosts
                or parts.port not in (None, 443)
                or "\\" in candidate
                or any(ord(c) < 32 for c in candidate)
            ):
                return True
        except ValueError:
            return True
    return False


class RuleClassifier:
    def __init__(self, policy: Policy):
        self.policy = policy

    def classify(self, text: str, direction: Direction) -> Decision:
        if direction not in ("input", "output") or not isinstance(text, str) or not text.strip():
            raise ValueError("A nonempty text message and an explicit direction are required")
        if len(text) > self.policy.max_chars:
            return Decision("block", "", ("LIMIT-01",))
        normalized = normalize(text)
        matches = []
        if direction == "input" and INJECTION.search(normalized):
            matches.append("INJ-01")
        if FINANCIAL_ABUSE.search(normalized):
            matches.append("FIN-01")
        if PRIVATE_KEY.search(normalized):
            matches.append("DLP-02")
        decoded = unquote(normalized)
        if any(normalize(value) in decoded for value in self.policy.protected_values):
            matches.append("DLP-02")
        if self.policy.block_payment_cards and any(is_payment_card(m.group()) for m in CARD.finditer(normalized)):
            matches.append("DLP-01")
        # Output destinations are restricted; user-supplied links can be discussed.
        if direction == "output" and restricted_link(normalized, self.policy.allowed_link_hosts):
            matches.append("URL-01")
        if matches:
            return Decision("block", "", tuple(dict.fromkeys(matches)))
        if self.policy.redact_email:
            masked = EMAIL.sub("[EMAIL]", normalized)
            if masked != normalized:
                return Decision("redact", masked, ("DLP-01",))
        return Decision("allow", text)
