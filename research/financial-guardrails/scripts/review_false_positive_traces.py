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

"""Privately classify false-positive traces while saving only content-free results."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections.abc import Iterable
from pathlib import Path

from financial_guardrails.datasets import BenchmarkMessage, finvault_adapter

from scripts.manage_false_positive_review import ReviewWorksheetRow

_CHOICES = {
    "a": ("allow_candidate", "read_only_or_reversible"),
    "c": ("confirmation_appropriate", "trusted_authorization_missing"),
    "k": ("keep_intervention", "real_security_concern"),
    "m": ("ambiguous", "insufficient_context"),
}


def _read_rows(path: Path) -> list[ReviewWorksheetRow]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError("review worksheet must be a JSON list")
    return [ReviewWorksheetRow.model_validate(item) for item in value]


def _write_rows(path: Path, rows: list[ReviewWorksheetRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(json.dumps([row.model_dump(mode="json") for row in rows], indent=2))
        stream.write("\n")
    temporary.replace(path)


def classify(row: ReviewWorksheetRow, choice: str) -> ReviewWorksheetRow:
    """Return one content-free classification selected by an authorized reviewer."""
    try:
        outcome, basis = _CHOICES[choice]
    except KeyError as exc:
        raise ValueError("review choice must be a, c, k, or m") from exc
    return row.model_copy(update={"review_outcome": outcome, "review_basis": basis})


def _render_private_trace(case_id: str, messages: Iterable[BenchmarkMessage]) -> None:
    print(f"\n=== PRIVATE FINVAULT TRACE: {case_id} ===")
    print("Do not copy this content into Git, Slack, or the review worksheet.")
    for message in messages:
        print(f"\n[{message.original_role} / {message.kind}]")
        print(message.content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("worksheet", type=Path)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args()
    if not sys.stdin.isatty():
        raise SystemExit("private trace review requires an interactive terminal")
    rows = _read_rows(args.worksheet)
    cases = {case.case_id: case for case in finvault_adapter(args.data_dir).cases()}
    missing = [row.case_id for row in rows if row.case_id not in cases]
    if missing:
        raise ValueError("review worksheet contains case IDs absent from the supplied FinVault data")

    for index, row in enumerate(rows):
        if row.review_outcome is not None:
            continue
        _render_private_trace(row.case_id, cases[row.case_id].messages)
        while True:
            choice = input("Classify: [a]llow, [c]onfirm, [k]eep intervention, a[m]biguous, [q]uit: ").strip().lower()
            if choice == "q":
                print("Stopped. Completed classifications were saved after each trace.")
                return
            try:
                rows[index] = classify(row, choice)
            except ValueError:
                print("Enter a, c, k, m, or q.")
                continue
            _write_rows(args.worksheet, rows)
            break
    print("All review rows are classified. Validate the worksheet before proposing a policy change.")


if __name__ == "__main__":
    main()
