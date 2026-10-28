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

"""Run non-executing benchmark replay and write a content-free result artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from financial_guardrails.benchmark_input import redact_benchmark_case_reference
from financial_guardrails.configuration import DEFAULT_POLICY_PATH, load_policy
from financial_guardrails.datasets import BenchmarkCase, cnfinbench_adapter, finvault_adapter, inspect_json_dataset
from financial_guardrails.evaluation import (
    EvaluationRecord,
    bootstrap_confidence_intervals,
    score_slices,
    summarize_records,
)
from financial_guardrails.finvault_policy import DEFAULT_FINVAULT_POLICY_PATH
from financial_guardrails.judge import DEFAULT_JUDGE_POLICY_PATH
from financial_guardrails.judge_backends import load_judge_backend_registry
from financial_guardrails.results import EvaluationArtifact, ExperimentManifest, write_evaluation_artifact
from financial_guardrails.runner import evaluate_cases
from financial_guardrails.splits import assign_nonfinal_cross_validation_folds, assign_splits, benchmark_group_id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", choices=("cnfinbench-pooled", "finvault-v5-fixed-full"))
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--split", choices=("development", "calibration", "pilot", "final", "all"), default="pilot")
    parser.add_argument(
        "--judge-mode", choices=("rules_only", "all_events", "rules_first_cascade"), default="rules_only"
    )
    parser.add_argument("--backend", choices=("rules_only", "navigator", "hipergator"), default="rules_only")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument(
        "--input-view",
        choices=("legacy_raw", "v3_clean"),
        default="legacy_raw",
        help="Versioned detector input; v3_clean hides benchmark hints and raw case IDs.",
    )
    parser.add_argument(
        "--reviewed-groups-file",
        type=Path,
        help="Private source-group manifest for excluding reviewed FinVault groups from a CV fold.",
    )
    parser.add_argument("--resume-checkpoint", type=Path)
    parser.add_argument(
        "--judge-policy-path",
        type=Path,
        default=DEFAULT_JUDGE_POLICY_PATH,
        help="Versioned judge-policy file; defaults to the frozen Version 1 policy.",
    )
    parser.add_argument(
        "--outcome-score-all-events",
        action="store_true",
        help="Collect LLM outcome scores after rule interventions without changing enforcement decisions.",
    )
    selection_group = parser.add_mutually_exclusive_group()
    selection_group.add_argument(
        "--max-cases",
        type=int,
        help="Evaluate a deterministic prefix of the selected split; intended for reliability gates, not reporting.",
    )
    parser.add_argument(
        "--cv-fold",
        type=int,
        help="Evaluate one source-group-disjoint fold from the non-final pool; use only after freezing configuration.",
    )
    selection_group.add_argument(
        "--case-id-file",
        type=Path,
        help="Evaluate exactly the newline-delimited case IDs in this file; intended for targeted reliability replay.",
    )
    parser.add_argument("--inference-code-commit")
    parser.add_argument("--judge-policy-sha256")
    parser.add_argument("--bootstrap-iterations", type=int, default=1000)
    args = parser.parse_args()
    if (args.judge_mode == "rules_only") != (args.backend == "rules_only"):
        parser.error("rules_only mode requires the rules_only backend, and judge modes require a judge backend")
    if args.max_cases is not None and args.max_cases < 1:
        parser.error("--max-cases must be at least 1")
    if args.cv_fold is not None and (args.cv_fold < 0 or args.cv_fold >= 4):
        parser.error("--cv-fold must be between 0 and 3")
    if args.cv_fold is not None and (args.max_cases is not None or args.case_id_file is not None):
        parser.error("--cv-fold cannot be combined with --max-cases or --case-id-file")
    if args.outcome_score_all_events and args.judge_mode != "rules_first_cascade":
        parser.error("--outcome-score-all-events requires --judge-mode rules_first_cascade")
    if args.reviewed_groups_file and (args.dataset != "finvault-v5-fixed-full" or args.cv_fold is None):
        parser.error("--reviewed-groups-file requires FinVault and --cv-fold")
    if args.dataset == "finvault-v5-fixed-full" and args.cv_fold is not None and args.input_view == "v3_clean":
        if not args.reviewed_groups_file:
            parser.error("Version 3 FinVault CV requires --reviewed-groups-file")

    adapter = (
        cnfinbench_adapter(args.data_dir) if args.dataset == "cnfinbench-pooled" else finvault_adapter(args.data_dir)
    )
    all_cases = tuple(adapter.cases())
    assignment = {item.case_id: item for item in assign_splits(all_cases)}
    selection_name = args.split
    if args.cv_fold is None:
        cases = (
            all_cases
            if args.split == "all"
            else tuple(case for case in all_cases if assignment[case.case_id].split == args.split)
        )
    else:
        cv_assignment = {item.case_id: item for item in assign_nonfinal_cross_validation_folds(all_cases)}
        cases = tuple(
            case
            for case in all_cases
            if cv_assignment.get(case.case_id, None) and cv_assignment[case.case_id].fold == args.cv_fold
        )
        selection_name = f"cv{args.cv_fold}"
    reviewed_groups_sha256 = _sha256(args.reviewed_groups_file) if args.reviewed_groups_file else None
    if args.reviewed_groups_file:
        reviewed_groups = _load_reviewed_groups(
            args.reviewed_groups_file, args.dataset, adapter.data_path, adapter.metadata_path, all_cases
        )
        cases = tuple(case for case in cases if benchmark_group_id(case) not in reviewed_groups)
    case_selection_sha256 = _sha256(args.case_id_file) if args.case_id_file else None
    if args.case_id_file:
        requested_ids = _load_case_ids(args.case_id_file)
        selected_by_id = {case.case_id: case for case in cases}
        missing = set(requested_ids) - set(selected_by_id)
        if missing:
            parser.error("--case-id-file contains IDs outside the selected split")
        cases = tuple(selected_by_id[case_id] for case_id in requested_ids)
    elif args.max_cases is not None:
        cases = tuple(sorted(cases, key=lambda case: case.case_id)[: args.max_cases])
    if not cases:
        raise SystemExit("selected split is empty")
    code_commit = args.inference_code_commit or _git_commit()
    if args.inference_code_commit and not _valid_commit(args.inference_code_commit):
        parser.error("--inference-code-commit must be a 40-character lowercase Git SHA")
    dataset_sha256 = inspect_json_dataset(adapter.data_path).sha256
    metadata_sha256 = _sha256(adapter.metadata_path)
    policy_sha256 = _sha256(DEFAULT_POLICY_PATH)
    judge_policy_sha256 = args.judge_policy_sha256 or _sha256(args.judge_policy_path)
    if args.judge_policy_sha256 and not _valid_sha256(args.judge_policy_sha256):
        parser.error("--judge-policy-sha256 must be a 64-character lowercase SHA-256 digest")
    benchmark_policy_sha256 = (
        _sha256(DEFAULT_FINVAULT_POLICY_PATH) if args.dataset == "finvault-v5-fixed-full" else None
    )
    fingerprint_fields = {
        "code_commit": code_commit,
        "dataset_sha256": dataset_sha256,
        "metadata_sha256": metadata_sha256,
        "policy_sha256": policy_sha256,
        "judge_policy_sha256": judge_policy_sha256,
        "benchmark_policy_sha256": benchmark_policy_sha256,
        "backend": args.backend,
        "judge_mode": args.judge_mode,
        "split": args.split,
        "max_cases": args.max_cases,
        "case_selection_sha256": case_selection_sha256,
        "cv_fold": args.cv_fold,
        "outcome_score_mode": "score_all_outcome_events" if args.outcome_score_all_events else "enforcement_only",
    }
    if args.input_view != "legacy_raw":
        fingerprint_fields["input_view"] = args.input_view
    if reviewed_groups_sha256:
        fingerprint_fields["reviewed_groups_sha256"] = reviewed_groups_sha256
    fingerprint = hashlib.sha256(json.dumps(fingerprint_fields, sort_keys=True).encode()).hexdigest()[:12]
    run_id = f"{args.dataset}-{selection_name}-{args.backend}-{args.judge_mode}-{fingerprint}"
    started = datetime.now(timezone.utc)
    records = evaluate_cases(
        cases,
        judge_mode=args.judge_mode,
        backend_name=args.backend,
        judge_policy_path=args.judge_policy_path,
        outcome_score_mode="score_all_outcome_events" if args.outcome_score_all_events else "enforcement_only",
        input_view=args.input_view,
        checkpoint_path=args.resume_checkpoint or args.output_dir / f"{run_id}.checkpoint.jsonl",
        progress_sink=_MilestoneReporter(),
    )
    records = tuple(
        record.model_copy(update={"slices": {**record.slices, "split": assignment[record.case_id].split}})
        for record in records
    )
    completed = datetime.now(timezone.utc)
    policy = load_policy()
    registry = load_judge_backend_registry()
    backend_spec = registry.backends.get(args.backend)
    manifest = ExperimentManifest(
        run_id=run_id,
        started_at=started,
        completed_at=completed,
        code_commit=code_commit,
        dataset_key=args.dataset,
        dataset_sha256=dataset_sha256,
        metadata_sha256=metadata_sha256,
        expected_records=len(cases),
        case_limit=args.max_cases,
        case_selection_sha256=case_selection_sha256,
        cross_validation_fold=args.cv_fold,
        reviewed_groups_sha256=reviewed_groups_sha256,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        policy_sha256=policy_sha256,
        judge_policy_sha256=judge_policy_sha256,
        benchmark_policy_sha256=benchmark_policy_sha256,
        backend=args.backend,
        model_id=backend_spec.model if backend_spec else "deterministic-rules",
        model_revision=backend_spec.revision if backend_spec else None,
        judge_mode=args.judge_mode,
        outcome_score_mode="score_all_outcome_events" if args.outcome_score_all_events else "enforcement_only",
        input_view=args.input_view,
        positive_label=1,
        generation_settings=backend_spec.request_options if backend_spec else {},
        software_versions={"python": platform.python_version()},
        hardware={"platform": platform.platform()},
        pricing_usd_per_million_tokens=(
            {"input": backend_spec.input_cost_per_million_usd, "output": backend_spec.output_cost_per_million_usd}
            if backend_spec
            else {}
        ),
        bootstrap_iterations=args.bootstrap_iterations,
        inference_elapsed_seconds=_inference_elapsed_seconds(records),
    )
    artifact = EvaluationArtifact(
        manifest=manifest,
        records=records,
        metrics=summarize_records(records, run_elapsed_seconds=_inference_elapsed_seconds(records)),
        confidence_intervals=bootstrap_confidence_intervals(records, iterations=args.bootstrap_iterations),
        slice_metrics={key: score_slices(records, key) for key in ("split", "risk_type", "behavior_mode")},
    )
    destination = args.output_dir / f"{run_id}.json"
    write_evaluation_artifact(destination, artifact)
    print(f"Wrote {len(records)} content-free records to {destination}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_commit() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()


def _valid_commit(value: str) -> bool:
    return len(value) == 40 and all(character in "0123456789abcdef" for character in value)


def _valid_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _load_case_ids(path: Path) -> tuple[str, ...]:
    try:
        case_ids = tuple(line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    except OSError as exc:
        raise ValueError("could not read --case-id-file") from exc
    if not case_ids:
        raise ValueError("--case-id-file must contain at least one case ID")
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("--case-id-file contains duplicate case IDs")
    return case_ids


def _load_reviewed_groups(
    path: Path,
    dataset_key: str,
    data_path: Path,
    metadata_path: Path,
    all_cases: tuple[BenchmarkCase, ...],
) -> frozenset[str]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("could not read reviewed source groups") from exc
    if not isinstance(value, dict) or value.get("schema_version") != "1" or value.get("dataset_key") != dataset_key:
        raise ValueError("reviewed source-group manifest has the wrong dataset or schema")
    if value.get("dataset_sha256") != _sha256(data_path) or value.get("metadata_sha256") != _sha256(metadata_path):
        raise ValueError("reviewed source groups do not match the dataset checksum")
    packet = path.parent.parent / "reviewers" / "blinded-traces.json"
    if not packet.is_file() or value.get("review_packet_sha256") != _sha256(packet):
        raise ValueError("reviewed source groups do not match the review packet")
    raw_groups = value.get("reviewed_source_groups")
    if not isinstance(raw_groups, list) or not raw_groups or any(not isinstance(group, str) for group in raw_groups):
        raise ValueError("reviewed source groups are missing or invalid")
    groups = frozenset(raw_groups)
    if len(groups) != len(raw_groups) or value.get("reviewed_group_count") != len(groups):
        raise ValueError("reviewed source-group count does not match")
    if value.get("reviewed_case_count") != 60:
        raise ValueError("reviewed source-group manifest has the wrong sample size")
    assigned = {item.case_id: item for item in assign_splits(all_cases)}
    development_groups = {item.group_id for item in assigned.values() if item.split == "development"}
    if not groups.issubset(development_groups):
        raise ValueError("reviewed source groups include unknown or non-development groups")
    if _groups_in_review_packet(packet, all_cases) != groups:
        raise ValueError("reviewed source groups do not match the cases in the review packet")
    return groups


def _groups_in_review_packet(packet_path: Path, all_cases: tuple[BenchmarkCase, ...]) -> frozenset[str]:
    try:
        rows = json.loads(packet_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("could not read the review packet") from exc
    if not isinstance(rows, list) or len(rows) != 60:
        raise ValueError("review packet must contain exactly 60 cases")
    by_first_user: dict[str, list[BenchmarkCase]] = {}
    for case in all_cases:
        first_user = next((message.content for message in case.messages if message.role == "user"), None)
        if first_user is not None:
            normalized = redact_benchmark_case_reference(first_user, case.case_id)
            by_first_user.setdefault(normalized, []).append(case)
    matched_ids: set[str] = set()
    groups: set[str] = set()
    for row in rows:
        messages = row.get("messages") if isinstance(row, dict) else None
        if not isinstance(messages, list):
            raise ValueError("review packet contains an invalid case")
        first_user = next(
            (
                message.get("content")
                for message in messages
                if isinstance(message, dict) and message.get("role") == "user"
            ),
            None,
        )
        matches = by_first_user.get(first_user, []) if isinstance(first_user, str) else []
        if len(matches) != 1 or matches[0].case_id in matched_ids:
            raise ValueError("review packet case cannot be uniquely matched to the frozen dataset")
        matched_ids.add(matches[0].case_id)
        groups.add(benchmark_group_id(matches[0]))
    return frozenset(groups)


def _inference_elapsed_seconds(records: tuple[EvaluationRecord, ...]) -> float:
    return sum(record.latency_seconds or 0 for record in records)


class _MilestoneReporter:
    def __init__(self) -> None:
        self.last_percent = -10
        self.started = time.monotonic()

    def __call__(self, completed: int, total: int) -> None:
        percent = completed * 100 // total
        milestone = min(100, percent // 10 * 10)
        if milestone <= self.last_percent and completed != total:
            return
        self.last_percent = milestone
        elapsed = time.monotonic() - self.started
        print(
            f"PROGRESS {milestone}% ({completed}/{total} cases, elapsed {elapsed:.0f}s)",
            flush=True,
        )


if __name__ == "__main__":
    main()
