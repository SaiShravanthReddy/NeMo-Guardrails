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

"""Export content-free false-positive review candidates from one result artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from financial_guardrails.evaluation import EvaluationRecord
from financial_guardrails.results import read_evaluation_artifact

from scripts.report_false_positives import false_positives


def _policy_attribution(record: EvaluationRecord) -> tuple[tuple[str, ...], str]:
    if record.primary_policy_ids:
        return record.primary_policy_ids, "primary"
    if record.policy_ids:
        return record.policy_ids, "matched_fallback"
    return (), "unavailable"


def review_candidates(records: tuple[EvaluationRecord, ...]) -> list[dict[str, object]]:
    """Return deterministic, content-free fields needed for authorized trace review."""
    candidates = []
    for record in sorted(false_positives(records), key=lambda item: item.case_id):
        policy_ids, attribution = _policy_attribution(record)
        candidates.append(
            {
                "case_id": record.case_id,
                "decision": record.decision.value if record.decision else None,
                "decision_policy_ids": list(policy_ids),
                "policy_attribution": attribution,
                "first_detection_surface": record.surface.value if record.surface else None,
                "first_detection_turn": record.first_detection_turn,
                "intervention_source": "deterministic_rule" if record.rules_intervened else "judge_only",
            }
        )
    return candidates


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--output", required=True, type=Path, help="Private content-free JSON destination.")
    args = parser.parse_args()
    artifact = read_evaluation_artifact(args.artifact)
    candidates = review_candidates(artifact.records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(candidates, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(candidates)} content-free false-positive review candidates to {args.output}")


if __name__ == "__main__":
    main()
