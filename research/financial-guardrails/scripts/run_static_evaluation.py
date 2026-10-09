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

from financial_guardrails.configuration import DEFAULT_POLICY_PATH, load_policy
from financial_guardrails.datasets import cnfinbench_adapter, finvault_adapter, inspect_json_dataset
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
from financial_guardrails.splits import assign_nonfinal_cross_validation_folds, assign_splits


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
    parser.add_argument("--resume-checkpoint", type=Path)
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
    judge_policy_sha256 = args.judge_policy_sha256 or _sha256(DEFAULT_JUDGE_POLICY_PATH)
    if args.judge_policy_sha256 and not _valid_sha256(args.judge_policy_sha256):
        parser.error("--judge-policy-sha256 must be a 64-character lowercase SHA-256 digest")
    benchmark_policy_sha256 = (
        _sha256(DEFAULT_FINVAULT_POLICY_PATH) if args.dataset == "finvault-v5-fixed-full" else None
    )
    fingerprint = hashlib.sha256(
        json.dumps(
            {
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
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()[:12]
    run_id = f"{args.dataset}-{selection_name}-{args.backend}-{args.judge_mode}-{fingerprint}"
    started = datetime.now(timezone.utc)
    records = evaluate_cases(
        cases,
        judge_mode=args.judge_mode,
        backend_name=args.backend,
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
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        policy_sha256=policy_sha256,
        judge_policy_sha256=judge_policy_sha256,
        benchmark_policy_sha256=benchmark_policy_sha256,
        backend=args.backend,
        model_id=backend_spec.model if backend_spec else "deterministic-rules",
        model_revision=backend_spec.revision if backend_spec else None,
        judge_mode=args.judge_mode,
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
