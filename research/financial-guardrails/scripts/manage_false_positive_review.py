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

"""Prepare and validate content-free Version 2 false-positive review worksheets."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

ReviewOutcome = Literal["allow_candidate", "confirmation_appropriate", "keep_intervention", "ambiguous"]
ReviewBasis = Literal[
    "read_only_or_reversible",
    "trusted_authorization_missing",
    "real_security_concern",
    "insufficient_context",
]


class ReviewWorksheetRow(BaseModel):
    """Content-free review fields; raw traces and free-text notes are prohibited."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(min_length=1)
    decision: str | None
    decision_policy_ids: tuple[str, ...]
    policy_attribution: Literal["primary", "matched_fallback", "unavailable"]
    first_detection_surface: str | None
    first_detection_turn: int | None = Field(default=None, ge=0)
    intervention_source: Literal["deterministic_rule", "judge_only"]
    review_outcome: ReviewOutcome | None = None
    review_basis: ReviewBasis | None = None

    @model_validator(mode="after")
    def validate_review_fields(self):
        if (self.review_outcome is None) != (self.review_basis is None):
            raise ValueError("review_outcome and review_basis must be completed together")
        if self.review_outcome == "allow_candidate" and self.review_basis != "read_only_or_reversible":
            raise ValueError("allow_candidate requires read_only_or_reversible")
        return self


def prepare(candidates: list[dict[str, object]]) -> list[ReviewWorksheetRow]:
    """Convert review candidates into blank, schema-checked worksheet rows."""
    rows = [ReviewWorksheetRow.model_validate(candidate) for candidate in candidates]
    case_ids = [row.case_id for row in rows]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("review candidates contain duplicate case IDs")
    return rows


def validate(rows: list[ReviewWorksheetRow]) -> Counter[str]:
    """Require a completed, unique, content-free classification for every row."""
    if not rows:
        raise ValueError("review worksheet is empty")
    case_ids = [row.case_id for row in rows]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("review worksheet contains duplicate case IDs")
    if any(row.review_outcome is None for row in rows):
        raise ValueError("review worksheet contains incomplete classifications")
    return Counter(cast(ReviewOutcome, row.review_outcome) for row in rows)


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("candidates", type=Path)
    prepare_parser.add_argument("--output", required=True, type=Path)
    validate_parser = commands.add_parser("validate")
    validate_parser.add_argument("worksheet", type=Path)
    args = parser.parse_args()

    if args.command == "prepare":
        candidates = _load_json(args.candidates)
        if not isinstance(candidates, list):
            raise ValueError("review candidates must be a JSON list")
        rows = prepare(cast(list[dict[str, object]], candidates))
        _write_json(args.output, [row.model_dump(mode="json") for row in rows])
        print(f"Wrote {len(rows)} blank content-free review rows to {args.output}")
        return

    worksheet = _load_json(args.worksheet)
    if not isinstance(worksheet, list):
        raise ValueError("review worksheet must be a JSON list")
    counts = validate([ReviewWorksheetRow.model_validate(row) for row in worksheet])
    print(dict(sorted(counts.items())))


if __name__ == "__main__":
    main()
