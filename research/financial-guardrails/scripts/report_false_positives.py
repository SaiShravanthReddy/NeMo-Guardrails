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

"""Summarize content-free attack-attempt false positives in one artifact."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Iterable
from enum import Enum
from pathlib import Path

from financial_guardrails.evaluation import EvaluationRecord
from financial_guardrails.results import read_evaluation_artifact


def _value(item: object | None) -> str:
    """Return an enum value or a stable string for report rendering."""
    if item is None:
        return "unavailable"
    if isinstance(item, Enum):
        return str(item.value)
    return str(item)


def false_positives(records: Iterable[EvaluationRecord]) -> tuple[EvaluationRecord, ...]:
    """Return completed normal cases that received an attack intervention."""
    return tuple(record for record in records if record.label == 0 and record.prediction is True)


def _table(title: str, counts: Counter[str]) -> str:
    lines = [f"## {title}", "", "| Value | Count |", "| --- | ---: |"]
    lines.extend(f"| {value} | {count} |" for value, count in counts.most_common())
    return "\n".join(lines)


def _decision_policies(record: EvaluationRecord) -> tuple[tuple[str, ...], str]:
    """Return policy IDs and whether the artifact recorded primary attribution."""
    if record.primary_policy_ids:
        return record.primary_policy_ids, "primary"
    if record.policy_ids:
        return record.policy_ids, "matched_fallback"
    return ("unavailable",), "unavailable"


def render(records: Iterable[EvaluationRecord]) -> str:
    """Render aggregate provenance for attack-attempt false positives."""
    false_positive_records = false_positives(records)
    decisions = Counter(_value(record.decision) for record in false_positive_records)
    policy_pairs = [_decision_policies(record) for record in false_positive_records]
    policies = Counter(policy for policy_ids, _source in policy_pairs for policy in policy_ids)
    policy_provenance = Counter(source for _policy_ids, source in policy_pairs)
    surfaces = Counter(_value(record.surface) for record in false_positive_records)
    sources = Counter(
        "deterministic_rule" if record.rules_intervened else "judge_only" for record in false_positive_records
    )
    return "\n\n".join(
        (
            "# Attack-attempt false-positive analysis\n\n"
            f"False positives: {len(false_positive_records)}. The report contains aggregate, content-free telemetry only.",
            _table("Decision", decisions),
            _table("Decision policy ID", policies),
            _table("Policy attribution", policy_provenance),
            _table("First detection surface", surfaces),
            _table("Intervention source", sources),
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    args = parser.parse_args()
    artifact = read_evaluation_artifact(args.artifact)
    print(render(artifact.records))


if __name__ == "__main__":
    main()
