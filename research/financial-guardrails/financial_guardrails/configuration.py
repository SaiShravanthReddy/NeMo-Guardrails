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

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from financial_guardrails.schema import Decision, Mode

DEFAULT_POLICY_PATH = Path(__file__).resolve().parents[1] / "policies" / "open_lakera_v1.yml"


class DLPConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    redact_email: bool
    block_payment_cards: bool
    block_private_keys: bool
    protected_values: list[str] = Field(default_factory=list, repr=False)

    @field_validator("protected_values")
    @classmethod
    def protect_nontrivial_values(cls, values: list[str]) -> list[str]:
        if any(len(value.strip()) < 8 for value in values):
            raise ValueError("protected values must contain at least eight characters")
        return values


class LinkConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    allowed_hosts: list[str]
    denied_hosts: list[str]

    @field_validator("allowed_hosts", "denied_hosts")
    @classmethod
    def exact_hosts(cls, hosts: list[str]) -> list[str]:
        import re

        if any(not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", host) for host in hosts):
            raise ValueError("host policy requires exact lowercase ASCII hostnames")
        return hosts


class ToolRule(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    risk: Literal["low", "high"]
    required_permission: str
    allowed_arguments: list[str]


class ToolConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    allowed: dict[str, ToolRule]
    confirmation_required: list[str]
    denied: list[str]
    external_transfer_arguments: list[str]


class FailurePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    high_impact: Decision
    ordinary: Decision


class PolicyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str
    policy_id: str
    policy_version: str
    default_mode: Mode
    limits: dict[str, int]
    data_loss_prevention: DLPConfig
    links: LinkConfig
    tools: ToolConfig
    failure_policy: FailurePolicy


def load_policy(path: str | Path = DEFAULT_POLICY_PATH) -> PolicyConfig:
    try:
        raw: dict[str, Any] = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError("policy configuration could not be loaded") from exc
    protected = os.environ.get("OPEN_LAKERA_PROTECTED_VALUES")
    if protected:
        import json

        raw["data_loss_prevention"]["protected_values"] = json.loads(protected)
    return PolicyConfig.model_validate(raw)
