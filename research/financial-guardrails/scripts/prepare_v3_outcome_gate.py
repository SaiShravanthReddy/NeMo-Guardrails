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

# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES.
# SPDX-License-Identifier: Apache-2.0

"""Prepare a private 12-case V3 outcome-score replay gate from four CV artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Sequence

from financial_guardrails.datasets import BenchmarkCase, cnfinbench_adapter, finvault_adapter, inspect_json_dataset
from financial_guardrails.evaluation import EvaluationRecord
from financial_guardrails.replay import event_from_message
from financial_guardrails.results import ExperimentManifest
from financial_guardrails.schema import Surface
from financial_guardrails.splits import assign_nonfinal_cross_validation_folds, benchmark_group_id

from scripts.run_static_evaluation import _load_reviewed_groups

OUTCOME_SURFACES = {Surface.OUTPUT, Surface.TOOL_CALL, Surface.TOOL_RESULT}


def select_replay_ids(
    records: Sequence[EvaluationRecord],
    cases_by_id: dict[str, BenchmarkCase],
    *,
    per_fold: int | None = 3,
) -> tuple[str, ...]:
    """Choose reproducible cases with labeled outcomes and missing scores."""

    if per_fold is not None and per_fold < 1:
        raise ValueError("per-fold replay count must be positive")
    candidates = []
    for record in records:
        case = cases_by_id.get(record.case_id)
        label = case.metadata.get("evaluation", {}).get("attack_success") if case else None
        if case is None or type(label) is not bool or record.attack_success_risk_score is not None:
            continue
        has_outcome_events = any(
            event_from_message(case, message, input_view="v3_clean").surface in OUTCOME_SURFACES
            for message in case.messages
        )
        if has_outcome_events:
            candidates.append(record.case_id)
    ordered = sorted(candidates, key=lambda case_id: (hashlib.sha256(case_id.encode()).digest(), case_id))
    return tuple(ordered if per_fold is None else ordered[:per_fold])


def retained_checkpoint_records(
    records: Sequence[EvaluationRecord], replay_ids: set[str]
) -> tuple[EvaluationRecord, ...]:
    """Keep all non-sampled cases and align legacy record mode with its manifest."""

    retained = tuple(
        record.model_copy(update={"outcome_score_mode": "score_all_outcome_events"})
        for record in records
        if record.case_id not in replay_ids
    )
    if len(retained) + len(replay_ids) != len(records):
        raise ValueError("replay IDs contain cases absent from this fold")
    if not retained:
        raise ValueError("gate checkpoint cannot retain zero records")
    return retained


def write_private_text(path: Path, value: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(value)
    path.chmod(0o600)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", nargs=4, type=Path, help="V3 CV artifacts for folds 0 through 3")
    parser.add_argument(
        "--dataset", choices=("finvault-v5-fixed-full", "cnfinbench-pooled"), default="finvault-v5-fixed-full"
    )
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--reviewed-groups-file", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--per-fold", type=int, default=3)
    selection.add_argument("--all-missing", action="store_true")
    args = parser.parse_args()
    if not args.all_missing and args.per_fold < 1:
        parser.error("--per-fold must be positive")
    if args.dataset == "finvault-v5-fixed-full" and not args.reviewed_groups_file:
        parser.error("FinVault gate preparation requires --reviewed-groups-file")
    if args.dataset == "cnfinbench-pooled" and args.reviewed_groups_file:
        parser.error("CNFinBench gate preparation does not use a reviewed-groups file")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        parser.error("output directory must be empty to protect existing review data")

    adapter = (
        finvault_adapter(args.data_dir)
        if args.dataset == "finvault-v5-fixed-full"
        else cnfinbench_adapter(args.data_dir)
    )
    cases = tuple(adapter.cases())
    groups = (
        _load_reviewed_groups(
            args.reviewed_groups_file,
            args.dataset,
            adapter.data_path,
            adapter.metadata_path,
            cases,
        )
        if args.reviewed_groups_file
        else set()
    )
    eligible_cases = tuple(case for case in cases if benchmark_group_id(case) not in groups)
    fold_by_id = {assignment.case_id: assignment.fold for assignment in assign_nonfinal_cross_validation_folds(cases)}
    expected_by_fold = {
        fold: {case.case_id for case in eligible_cases if fold_by_id.get(case.case_id) == fold} for fold in range(4)
    }
    cases_by_id = {case.case_id: case for case in eligible_cases}
    dataset_sha256 = inspect_json_dataset(adapter.data_path).sha256
    metadata_sha256 = _sha256(adapter.metadata_path)
    reviewed_groups_sha256 = _sha256(args.reviewed_groups_file) if args.reviewed_groups_file else None

    artifacts_by_fold: dict[int, tuple[ExperimentManifest, tuple[EvaluationRecord, ...]]] = {}
    for path in args.artifacts:
        payload = _read_artifact(path)
        manifest = ExperimentManifest.model_validate(payload.get("manifest"))
        fold = manifest.cross_validation_fold
        if fold not in expected_by_fold or fold in artifacts_by_fold:
            raise ValueError("artifacts must contain CV folds 0, 1, 2, and 3 exactly once")
        if (
            manifest.dataset_key != args.dataset
            or manifest.dataset_sha256 != dataset_sha256
            or manifest.metadata_sha256 != metadata_sha256
            or manifest.reviewed_groups_sha256 != reviewed_groups_sha256
            or manifest.input_view != "v3_clean"
            or manifest.outcome_score_mode != "score_all_outcome_events"
            or manifest.judge_mode != "rules_first_cascade"
        ):
            raise ValueError("artifact provenance or V3 configuration does not match this replay gate")
        raw_records = payload.get("records")
        if not isinstance(raw_records, list):
            raise ValueError("artifact records must be a list")
        records = tuple(EvaluationRecord.model_validate(item) for item in raw_records)
        record_ids = [record.case_id for record in records]
        if len(record_ids) != len(set(record_ids)) or set(record_ids) != expected_by_fold[fold]:
            raise ValueError(f"fold {fold} records do not match the canonical reviewed-group split")
        if len(records) != manifest.expected_records:
            raise ValueError(f"fold {fold} record count does not match its manifest")
        if any(
            record.dataset_key != args.dataset
            or record.backend != manifest.backend
            or record.judge_mode != "v3_rules_first_cascade"
            or record.input_view != "v3_clean"
            for record in records
        ):
            raise ValueError(f"fold {fold} record configuration does not match its manifest")
        artifacts_by_fold[fold] = (manifest, records)

    if set(artifacts_by_fold) != {0, 1, 2, 3}:
        raise ValueError("artifacts must contain all four CV folds")
    _validate_shared_configuration(artifacts_by_fold)

    gate_records = {}
    for fold in range(4):
        manifest, records = artifacts_by_fold[fold]
        replay_ids = select_replay_ids(records, cases_by_id, per_fold=None if args.all_missing else args.per_fold)
        if not replay_ids:
            raise ValueError(f"fold {fold} has no eligible missing outcome scores")
        if not args.all_missing and len(replay_ids) != args.per_fold:
            raise ValueError(f"fold {fold} has fewer than {args.per_fold} eligible replay candidates")
        checkpoint_records = retained_checkpoint_records(records, set(replay_ids))
        gate_records[fold] = (manifest, replay_ids, checkpoint_records)

    args.output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    args.output_dir.chmod(0o700)
    total_replay = 0
    for fold in range(4):
        manifest, replay_ids, checkpoint_records = gate_records[fold]
        stem = f"{args.dataset}-cv{fold}-outcome-gate"
        checkpoint_path = args.output_dir / f"{stem}.checkpoint.jsonl"
        case_ids_path = args.output_dir / f"{stem}.case-ids.txt"
        write_private_text(checkpoint_path, "".join(record.model_dump_json() + "\n" for record in checkpoint_records))
        write_private_text(case_ids_path, "\n".join(replay_ids) + "\n")
        total_replay += len(replay_ids)
        print(
            f"fold={fold} expected={manifest.expected_records} retained={len(checkpoint_records)} "
            f"replay={len(replay_ids)} checkpoint={checkpoint_path.name} case_ids={case_ids_path.name}"
        )
    print(f"total_replay_cases={total_replay}")


def _validate_shared_configuration(
    artifacts: dict[int, tuple[ExperimentManifest, tuple[EvaluationRecord, ...]]],
) -> None:
    manifests = [artifacts[fold][0] for fold in range(4)]
    shared_fields = ("backend", "model_id", "model_revision", "code_commit", "judge_policy_sha256")
    if any(len({getattr(manifest, field) for manifest in manifests}) != 1 for field in shared_fields):
        raise ValueError("CV artifacts do not share one backend, model, code, and judge policy")
    outcome_policy_hashes = {manifest.generation_settings.get("outcome_policy_sha256") for manifest in manifests}
    if len(outcome_policy_hashes) != 1 or None in outcome_policy_hashes:
        raise ValueError("CV artifacts do not share one outcome-judge policy")


def _read_artifact(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read artifact: {path.name}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"artifact must be a JSON object: {path.name}")
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    main()
