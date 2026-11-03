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

"""Audit Version 3 outcome-score coverage without exposing case content."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

from financial_guardrails.datasets import finvault_adapter, inspect_json_dataset
from financial_guardrails.evaluation import EvaluationRecord
from financial_guardrails.replay import event_from_message
from financial_guardrails.results import ExperimentManifest
from financial_guardrails.schema import Surface
from financial_guardrails.splits import assign_nonfinal_cross_validation_folds, benchmark_group_id

from scripts.run_static_evaluation import _load_reviewed_groups


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", nargs=4, type=Path, help="V3 FinVault CV fold artifacts, folds 0 through 3")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--reviewed-groups-file", type=Path, required=True)
    parser.add_argument(
        "--replay-case-ids-file",
        type=Path,
        help="Optional private file for cases with outcome-judge errors and usable outcome events",
    )
    args = parser.parse_args()

    adapter = finvault_adapter(args.data_dir)
    cases = tuple(adapter.cases())
    groups = _load_reviewed_groups(
        args.reviewed_groups_file,
        "finvault-v5-fixed-full",
        adapter.data_path,
        adapter.metadata_path,
        cases,
    )
    eligible_cases = tuple(case for case in cases if benchmark_group_id(case) not in groups)
    fold_by_id = {assignment.case_id: assignment.fold for assignment in assign_nonfinal_cross_validation_folds(cases)}
    expected_by_fold = {
        fold: {case.case_id for case in eligible_cases if fold_by_id.get(case.case_id) == fold} for fold in range(4)
    }
    cases_by_id = {case.case_id: case for case in cases}
    dataset_sha256 = inspect_json_dataset(adapter.data_path).sha256
    metadata_sha256 = _sha256(adapter.metadata_path)
    reviewed_groups_sha256 = _sha256(args.reviewed_groups_file)

    identities = set()
    replay_candidates: list[str] = []
    total = Counter()
    failure_codes = Counter()
    for path in args.artifacts:
        payload = _read_json(path)
        manifest = ExperimentManifest.model_validate(payload.get("manifest"))
        fold = manifest.cross_validation_fold
        if fold not in expected_by_fold or fold in identities:
            raise ValueError("artifacts must contain CV folds 0, 1, 2, and 3 exactly once")
        if (
            manifest.dataset_key != "finvault-v5-fixed-full"
            or manifest.dataset_sha256 != dataset_sha256
            or manifest.metadata_sha256 != metadata_sha256
            or manifest.reviewed_groups_sha256 != reviewed_groups_sha256
            or manifest.input_view != "v3_clean"
        ):
            raise ValueError("artifact provenance does not match this FinVault V3 audit")
        identities.add(fold)
        raw_records = payload.get("records")
        if not isinstance(raw_records, list):
            raise ValueError("artifact records must be a list")
        records = tuple(EvaluationRecord.model_validate(item) for item in raw_records)
        record_ids = [record.case_id for record in records]
        if len(record_ids) != len(set(record_ids)) or set(record_ids) != expected_by_fold[fold]:
            raise ValueError(f"fold {fold} artifact case IDs do not match the reviewed-group CV selection")
        if len(records) != manifest.expected_records:
            raise ValueError(f"fold {fold} record count does not match its manifest")

        fold_counts = Counter()
        for record in records:
            case = cases_by_id[record.case_id]
            label = case.metadata.get("evaluation", {}).get("attack_success")
            if type(label) is not bool:
                continue
            fold_counts["eligible"] += 1
            has_score = record.attack_success_risk_score is not None
            has_prediction = record.attack_success_prediction is not None
            if record.outcome_score_failure_code:
                failure_codes[record.outcome_score_failure_code] += 1
            fold_counts["scored"] += has_score
            fold_counts["predicted"] += has_prediction
            outcome_events = tuple(
                event
                for message in case.messages
                if (event := event_from_message(case, message, input_view="v3_clean")).surface
                in {Surface.OUTPUT, Surface.TOOL_CALL, Surface.TOOL_RESULT}
            )
            if has_score:
                continue
            if record.outcome_score_detector_error or record.attack_success_detector_error:
                fold_counts["judge_error_missing_score"] += 1
                if outcome_events:
                    replay_candidates.append(record.case_id)
            elif not outcome_events:
                fold_counts["no_outcome_events"] += 1
            else:
                fold_counts["missing_score_with_evidence"] += 1
            if has_prediction:
                fold_counts["prediction_without_score"] += 1

        fold_counts["outcome_score_mode_mismatches"] = sum(
            record.outcome_score_mode != manifest.outcome_score_mode for record in records
        )
        _print_fold(fold, fold_counts)
        total.update(fold_counts)

    if identities != {0, 1, 2, 3}:
        raise ValueError("artifacts must contain CV folds 0, 1, 2, and 3 exactly once")
    _print_fold("all", total)
    print(f"replay_candidates_with_judge_error_and_events={len(set(replay_candidates))}")
    print(f"outcome_score_failure_codes={dict(sorted(failure_codes.items()))}")
    if args.replay_case_ids_file:
        _write_private_ids(args.replay_case_ids_file, sorted(set(replay_candidates)))
        print(f"private_replay_case_ids_file_written={args.replay_case_ids_file}")


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read artifact: {path.name}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"artifact must contain a JSON object: {path.name}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _print_fold(fold: int | str, counts: Counter) -> None:
    eligible = counts["eligible"]
    scored = counts["scored"]
    predicted = counts["predicted"]
    coverage = "n/a" if eligible == 0 else f"{scored / eligible:.1%}"
    print(
        f"fold={fold} eligible={eligible} scored={scored} score_coverage={coverage} "
        f"predicted={predicted} judge_error_missing_score={counts['judge_error_missing_score']} "
        f"no_outcome_events={counts['no_outcome_events']} "
        f"missing_score_with_evidence={counts['missing_score_with_evidence']} "
        f"prediction_without_score={counts['prediction_without_score']} "
        f"legacy_score_mode_mismatches={counts['outcome_score_mode_mismatches']}"
    )


def _write_private_ids(path: Path, case_ids: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write("\n".join(case_ids))
        if case_ids:
            stream.write("\n")
    path.chmod(0o600)


if __name__ == "__main__":
    main()
