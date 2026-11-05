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

"""Prepare a private replay of prior V3 outcome scores under the current prompt."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from financial_guardrails.datasets import BenchmarkCase, cnfinbench_adapter, finvault_adapter, inspect_json_dataset
from financial_guardrails.evaluation import EvaluationRecord
from financial_guardrails.replay import event_from_message
from financial_guardrails.results import ExperimentManifest
from financial_guardrails.schema import Surface
from financial_guardrails.splits import assign_nonfinal_cross_validation_folds, benchmark_group_id

from scripts.prepare_v3_outcome_gate import _read_artifact, _sha256, write_private_text
from scripts.run_static_evaluation import _load_reviewed_groups


def prior_scored_ids(
    original: tuple[EvaluationRecord, ...],
    repaired: tuple[EvaluationRecord, ...],
    cases_by_id: dict[str, BenchmarkCase],
) -> tuple[str, ...]:
    """Find cases whose old score is present and whose repaired score is available."""

    original_by_id = {record.case_id: record for record in original}
    repaired_by_id = {record.case_id: record for record in repaired}
    if len(original_by_id) != len(original) or set(original_by_id) != set(repaired_by_id):
        raise ValueError("original and repaired fold case IDs must match exactly")
    selected = []
    for case_id, old_record in original_by_id.items():
        case = cases_by_id.get(case_id)
        if case is None:
            raise ValueError("artifact contains a case outside the canonical dataset")
        label = case.metadata.get("evaluation", {}).get("attack_success")
        if type(label) is not bool or old_record.attack_success_risk_score is None:
            continue
        if repaired_by_id[case_id].attack_success_risk_score is None:
            raise ValueError("repaired artifact has no outcome score for a previously scored case")
        if not any(
            event_from_message(case, message, input_view="v3_clean").surface
            in {Surface.OUTPUT, Surface.TOOL_CALL, Surface.TOOL_RESULT}
            for message in case.messages
        ):
            raise ValueError("previously scored case has no eligible outcome events")
        selected.append(case_id)
    return tuple(sorted(selected))


def checkpoint_records(records: tuple[EvaluationRecord, ...], replay_ids: set[str]) -> tuple[EvaluationRecord, ...]:
    retained = tuple(record for record in records if record.case_id not in replay_ids)
    if len(retained) + len(replay_ids) != len(records):
        raise ValueError("replay selection does not match the repaired fold")
    if not retained:
        raise ValueError("consistency-rescore checkpoint cannot be empty")
    return retained


def sample_rescore_ids(case_ids: tuple[str, ...], per_fold: int | None) -> tuple[str, ...]:
    if per_fold is None:
        return case_ids
    if per_fold < 1 or len(case_ids) < per_fold:
        raise ValueError("fold has fewer than the requested eligible cases to sample")
    return tuple(sorted(case_ids, key=lambda case_id: (hashlib.sha256(case_id.encode()).digest(), case_id))[:per_fold])


def validate_repaired_coverage(records: tuple[EvaluationRecord, ...], cases_by_id: dict[str, BenchmarkCase]) -> None:
    for record in records:
        case = cases_by_id.get(record.case_id)
        if case is None:
            raise ValueError("repaired artifact contains a case outside the canonical dataset")
        label = case.metadata.get("evaluation", {}).get("attack_success")
        if type(label) is bool and (
            record.attack_success_risk_score is None or record.outcome_score_failure_code is not None
        ):
            raise ValueError("repaired artifact does not have error-free outcome scores for every labeled case")


def record_configuration_is_valid(
    record: EvaluationRecord,
    *,
    dataset: str,
    backend: str,
    original_artifact: bool,
) -> bool:
    valid_score_modes = {"score_all_outcome_events"}
    if original_artifact:
        valid_score_modes.add("enforcement_only")
    return (
        record.dataset_key == dataset
        and record.backend == backend
        and record.judge_mode == "v3_rules_first_cascade"
        and record.input_view == "v3_clean"
        and record.outcome_score_mode in valid_score_modes
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original_artifacts", nargs=4, type=Path, help="Original V3 artifacts, folds 0 through 3")
    parser.add_argument("repaired_artifacts", nargs=4, type=Path, help="Full-repair V3 artifacts, folds 0 through 3")
    parser.add_argument("--dataset", choices=("finvault-v5-fixed-full", "cnfinbench-pooled"), required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--reviewed-groups-file", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--per-fold", type=int, help="Deterministically sample this many eligible cases per fold")
    args = parser.parse_args()
    if args.per_fold is not None and args.per_fold < 1:
        parser.error("--per-fold must be positive")
    if args.dataset == "finvault-v5-fixed-full" and not args.reviewed_groups_file:
        parser.error("FinVault requires --reviewed-groups-file")
    if args.dataset == "cnfinbench-pooled" and args.reviewed_groups_file:
        parser.error("CNFinBench does not use a reviewed-groups file")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        parser.error("output directory must be empty to protect existing artifacts")

    adapter = (
        finvault_adapter(args.data_dir)
        if args.dataset == "finvault-v5-fixed-full"
        else cnfinbench_adapter(args.data_dir)
    )
    cases = tuple(adapter.cases())
    reviewed = (
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
    fold_lookup = {item.case_id: item.fold for item in assign_nonfinal_cross_validation_folds(cases)}
    eligible = {case.case_id: case for case in cases if benchmark_group_id(case) not in reviewed}
    expected = {fold: {case_id for case_id in eligible if fold_lookup.get(case_id) == fold} for fold in range(4)}
    hashes = {
        "dataset_sha256": inspect_json_dataset(adapter.data_path).sha256,
        "metadata_sha256": _sha256(adapter.metadata_path),
        "reviewed_groups_sha256": _sha256(args.reviewed_groups_file) if args.reviewed_groups_file else None,
    }

    by_fold: dict[
        int, tuple[ExperimentManifest, tuple[EvaluationRecord, ...], ExperimentManifest, tuple[EvaluationRecord, ...]]
    ] = {}
    for paths, is_original in ((args.original_artifacts, True), (args.repaired_artifacts, False)):
        seen = set()
        for path in paths:
            payload = _read_artifact(path)
            manifest = ExperimentManifest.model_validate(payload.get("manifest"))
            fold = manifest.cross_validation_fold
            if fold not in range(4) or fold in seen:
                raise ValueError("each artifact set must contain folds 0 through 3 exactly once")
            seen.add(fold)
            if (
                manifest.dataset_key != args.dataset
                or manifest.dataset_sha256 != hashes["dataset_sha256"]
                or manifest.metadata_sha256 != hashes["metadata_sha256"]
                or manifest.reviewed_groups_sha256 != hashes["reviewed_groups_sha256"]
                or manifest.input_view != "v3_clean"
                or manifest.judge_mode != "rules_first_cascade"
                or manifest.outcome_score_mode != "score_all_outcome_events"
            ):
                raise ValueError("artifact provenance/configuration does not match this V3 CV dataset")
            raw = payload.get("records")
            if not isinstance(raw, list):
                raise ValueError("artifact records must be a list")
            records = tuple(EvaluationRecord.model_validate(row) for row in raw)
            ids = [record.case_id for record in records]
            if len(ids) != len(set(ids)) or set(ids) != expected[fold] or len(records) != manifest.expected_records:
                raise ValueError(f"fold {fold} artifact is incomplete or outside the canonical split")
            if any(
                not record_configuration_is_valid(
                    record,
                    dataset=args.dataset,
                    backend=manifest.backend,
                    original_artifact=is_original,
                )
                for record in records
            ):
                raise ValueError(f"fold {fold} record configuration does not match its manifest")
            if is_original:
                by_fold.setdefault(fold, (manifest, records, None, None))
            else:
                original_manifest, original_records, _, _ = by_fold[fold]
                by_fold[fold] = (original_manifest, original_records, manifest, records)
        if seen != set(range(4)):
            raise ValueError("each artifact set must contain all four folds")

    args.output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    args.output_dir.chmod(0o700)
    total = 0
    for fold in range(4):
        original_manifest, original, repaired_manifest, repaired = by_fold[fold]
        if repaired_manifest is None or repaired is None:
            raise ValueError("missing repaired fold artifact")
        validate_repaired_coverage(repaired, eligible)
        for name in ("backend", "model_id", "model_revision", "judge_policy_sha256"):
            if getattr(original_manifest, name) != getattr(repaired_manifest, name):
                raise ValueError("original and repaired artifacts use different judge configurations")
        ids = prior_scored_ids(original, repaired, eligible)
        if not ids:
            raise ValueError(f"fold {fold} has no previously scored outcomes to rescore")
        if args.per_fold is not None:
            try:
                ids = sample_rescore_ids(ids, args.per_fold)
            except ValueError as exc:
                raise ValueError(f"fold {fold} has fewer than {args.per_fold} eligible cases to sample") from exc
        retained = checkpoint_records(repaired, set(ids))
        stem = f"{args.dataset}-cv{fold}-outcome-consistency-rescore"
        write_private_text(
            args.output_dir / f"{stem}.checkpoint.jsonl", "".join(row.model_dump_json() + "\n" for row in retained)
        )
        write_private_text(args.output_dir / f"{stem}.case-ids.txt", "\n".join(ids) + "\n")
        total += len(ids)
        print(f"fold={fold} replay={len(ids)} retained={len(retained)}")
    print(f"total_rescore_cases={total}")


if __name__ == "__main__":
    main()
