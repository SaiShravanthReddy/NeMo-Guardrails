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

"""Versioned evaluation view that hides benchmark answer cues from detectors."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Literal

InputView = Literal["legacy_raw", "v3_clean"]

_ANNOTATION_KEYS = frozenset(
    {
        "target_vulnerability",
        "related_vulnerability",
        "business_scenario",
        "attack_intent_detected",
        "triggered_vulnerabilities",
        "vulnerabilities_triggered",
        "vuln_id",
        "security_alerts",
        "risk_flags",
    }
)
_SCENARIO_DESCRIPTION = re.compile(r"^Description:[^\r\n]*(?:\r?\n|$)", re.MULTILINE)
_BRACKETED_CASE_ID = re.compile(r"\[Case ID:(?:\[[^\]\r\n]*\]|[^\]\r\n])*\]", re.IGNORECASE)


def opaque_event_id(dataset_key: str, case_id: str, turn_index: int) -> str:
    """Hide label-bearing case prefixes while keeping stable event identities."""
    digest = hashlib.sha256(f"{dataset_key}\0{case_id}".encode()).hexdigest()
    return f"v3:{digest}:{turn_index}"


def redact_benchmark_case_reference(content: str, case_id: str) -> str:
    """Remove benchmark identifiers, including copies inside nested text."""
    without_exact_id = content.replace(case_id, "[BENCHMARK_ID_REDACTED]")
    return _BRACKETED_CASE_ID.sub("[Case ID: REDACTED]", without_exact_id)


def clean_finvault_tool_result(content: str) -> str:
    """Remove generator annotations while preserving recorded business evidence."""
    try:
        value = json.loads(content)
    except json.JSONDecodeError:
        return _SCENARIO_DESCRIPTION.sub("", content)
    cleaned, changed = _without_annotations(value)
    return json.dumps(cleaned, ensure_ascii=False, indent=2) if changed else content


def _without_annotations(value: Any) -> tuple[Any, bool]:
    if isinstance(value, dict):
        changed = False
        cleaned = {}
        for key, child in value.items():
            if key in _ANNOTATION_KEYS:
                changed = True
            else:
                cleaned_child, child_changed = _without_annotations(child)
                cleaned[key] = cleaned_child
                changed |= child_changed
        return cleaned, changed
    if isinstance(value, list):
        items = [_without_annotations(child) for child in value]
        return [child for child, _changed in items], any(changed for _child, changed in items)
    return value, False
