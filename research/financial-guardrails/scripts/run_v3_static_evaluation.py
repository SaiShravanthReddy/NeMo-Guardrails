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

"""Run the isolated Version 3 static replay with external trusted facts."""

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
from financial_guardrails.datasets import cnfinbench_adapter, finvault_adapter
from financial_guardrails.evaluation import bootstrap_confidence_intervals, score_slices, summarize_records
from financial_guardrails.finvault_policy import DEFAULT_FINVAULT_POLICY_PATH
from financial_guardrails.judge import load_judge_policy
from financial_guardrails.judge_backends import (
    BackendCallMetrics,
    configured_judge_backend,
    load_judge_backend_registry,
)
from financial_guardrails.outcome_judge import DEFAULT_OUTCOME_POLICY_PATH, V3OutcomeJudge, load_outcome_policy
from financial_guardrails.results import EvaluationArtifact, ExperimentManifest, write_evaluation_artifact
from financial_guardrails.splits import assign_nonfinal_cross_validation_folds, assign_splits, benchmark_group_id
from financial_guardrails.v3_contexts import load_trusted_facts, validate_trusted_facts_coverage
from financial_guardrails.v3_judge import V3PolicyJudgeDetector
from financial_guardrails.v3_runner import (
    V3EventEvaluator,
    V3OutcomeEvaluator,
    evaluate_v3_cases,
    v3_rules_engine_for_dataset,
)

from scripts.run_static_evaluation import _load_reviewed_groups

DEFAULT_V3_POLICY_PATH = Path(__file__).resolve().parents[1] / "policies" / "llm_judge_v2_1.yml"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", choices=("cnfinbench-pooled", "finvault-v5-fixed-full"))
    parser.add_argument("--trusted-facts", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--split", choices=("development", "calibration", "pilot", "final", "all"), default="pilot")
    parser.add_argument("--cv-fold", type=int)
    parser.add_argument("--reviewed-groups-file", type=Path)
    parser.add_argument("--backend", choices=("navigator", "hipergator"), required=True)
    parser.add_argument("--judge-policy-path", type=Path, default=DEFAULT_V3_POLICY_PATH)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--bootstrap-iterations", type=int, default=1000)
    args = parser.parse_args()
    if args.cv_fold is not None and not 0 <= args.cv_fold < 4:
        parser.error("--cv-fold must be between 0 and 3")
    if args.max_cases is not None and args.max_cases < 1:
        parser.error("--max-cases must be at least 1")
    if args.dataset == "finvault-v5-fixed-full" and not args.reviewed_groups_file:
        parser.error("Version 3 FinVault replay requires --reviewed-groups-file")

    adapter = (
        cnfinbench_adapter(args.data_dir) if args.dataset == "cnfinbench-pooled" else finvault_adapter(args.data_dir)
    )
    all_cases = tuple(adapter.cases())
    cases, selection_name, reviewed_groups_sha256 = _select_cases(args, all_cases, adapter)
    if not cases:
        raise SystemExit("selected split is empty")
    if args.max_cases is not None:
        cases = tuple(sorted(cases, key=lambda case: case.case_id)[: args.max_cases])

    metrics: list[BackendCallMetrics] = []
    facts = load_trusted_facts(args.trusted_facts)
    validate_trusted_facts_coverage(cases, facts)
    backend = configured_judge_backend(args.backend, metrics_sink=metrics.append)
    event_evaluator = V3EventEvaluator(
        rules_engine=v3_rules_engine_for_dataset(args.dataset),
        authorization_resolver=facts,
        judge=V3PolicyJudgeDetector(backend, load_judge_policy(args.judge_policy_path)),
    )
    outcome_evaluator = V3OutcomeEvaluator(
        outcome_resolver=facts,
        outcome_judge=V3OutcomeJudge(backend, load_outcome_policy()),
    )
    run_id = _run_id(args, selection_name, adapter.data_path, adapter.metadata_path, reviewed_groups_sha256)
    started = datetime.now(timezone.utc)
    records = evaluate_v3_cases(
        cases,
        event_evaluator=event_evaluator,
        outcome_evaluator=outcome_evaluator,
        backend=args.backend,
        checkpoint_path=args.checkpoint or args.output_dir / f"{run_id}.checkpoint.jsonl",
        progress_sink=_MilestoneReporter(),
        backend_metrics=metrics,
    )
    completed = datetime.now(timezone.utc)
    registry = load_judge_backend_registry()
    spec = registry.backends[args.backend]
    policy = load_policy()
    elapsed = sum(record.latency_seconds or 0 for record in records)
    artifact = EvaluationArtifact(
        manifest=ExperimentManifest(
            run_id=run_id,
            started_at=started,
            completed_at=completed,
            code_commit=_git_commit(),
            dataset_key=args.dataset,
            dataset_sha256=_sha256(adapter.data_path),
            metadata_sha256=_sha256(adapter.metadata_path),
            expected_records=len(cases),
            case_limit=args.max_cases,
            cross_validation_fold=args.cv_fold,
            reviewed_groups_sha256=reviewed_groups_sha256,
            policy_id=policy.policy_id,
            policy_version=policy.policy_version,
            policy_sha256=_sha256(DEFAULT_POLICY_PATH),
            judge_policy_sha256=_sha256(args.judge_policy_path),
            benchmark_policy_sha256=(
                _sha256(DEFAULT_FINVAULT_POLICY_PATH) if args.dataset == "finvault-v5-fixed-full" else None
            ),
            backend=args.backend,
            model_id=spec.model,
            model_revision=spec.revision,
            judge_mode="rules_first_cascade",
            outcome_score_mode="score_all_outcome_events",
            input_view="v3_clean",
            positive_label=1,
            generation_settings={
                **spec.request_options,
                "trusted_facts_sha256": _sha256(args.trusted_facts),
                "outcome_policy_sha256": _sha256(DEFAULT_OUTCOME_POLICY_PATH),
            },
            software_versions={"python": platform.python_version()},
            hardware={"platform": platform.platform()},
            pricing_usd_per_million_tokens={
                "input": spec.input_cost_per_million_usd,
                "output": spec.output_cost_per_million_usd,
            },
            bootstrap_iterations=args.bootstrap_iterations,
            bootstrap_group_slice_key="source_group",
            inference_elapsed_seconds=elapsed,
        ),
        records=records,
        metrics=summarize_records(records, run_elapsed_seconds=elapsed),
        confidence_intervals=bootstrap_confidence_intervals(
            records,
            iterations=args.bootstrap_iterations,
            group_slice_key="source_group",
        ),
        slice_metrics={
            key: score_slices(records, key) for key in ("split", "source_group", "risk_type", "behavior_mode")
        },
    )
    destination = args.output_dir / f"{run_id}.json"
    write_evaluation_artifact(destination, artifact)
    print(f"Wrote {len(records)} content-free Version 3 records to {destination}")


def _select_cases(args, all_cases, adapter):
    assignments = {item.case_id: item for item in assign_splits(all_cases)}
    if args.cv_fold is None:
        cases = (
            all_cases
            if args.split == "all"
            else tuple(case for case in all_cases if assignments[case.case_id].split == args.split)
        )
        selection_name = args.split
    else:
        folds = {item.case_id: item for item in assign_nonfinal_cross_validation_folds(all_cases)}
        cases = tuple(case for case in all_cases if case.case_id in folds and folds[case.case_id].fold == args.cv_fold)
        selection_name = f"cv{args.cv_fold}"
    reviewed_groups_sha256 = None
    if args.reviewed_groups_file:
        reviewed_groups = _load_reviewed_groups(
            args.reviewed_groups_file, args.dataset, adapter.data_path, adapter.metadata_path, all_cases
        )
        reviewed_groups_sha256 = _sha256(args.reviewed_groups_file)
        cases = tuple(case for case in cases if benchmark_group_id(case) not in reviewed_groups)
    return cases, selection_name, reviewed_groups_sha256


def _run_id(args, selection_name, data_path, metadata_path, reviewed_groups_sha256):
    fields = {
        "dataset": args.dataset,
        "selection": selection_name,
        "backend": args.backend,
        "data_sha256": _sha256(data_path),
        "metadata_sha256": _sha256(metadata_path),
        "trusted_facts_sha256": _sha256(args.trusted_facts),
        "judge_policy_sha256": _sha256(args.judge_policy_path),
        "reviewed_groups_sha256": reviewed_groups_sha256,
        "max_cases": args.max_cases,
    }
    fingerprint = hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()[:12]
    return f"{args.dataset}-{selection_name}-{args.backend}-v3-{fingerprint}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_commit() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()


class _MilestoneReporter:
    def __init__(self) -> None:
        self.last_percent = -10
        self.started = time.monotonic()

    def __call__(self, completed: int, total: int) -> None:
        milestone = min(100, (completed * 100 // total) // 10 * 10)
        if milestone <= self.last_percent and completed != total:
            return
        self.last_percent = milestone
        print(
            f"PROGRESS {milestone}% ({completed}/{total} cases, elapsed {time.monotonic() - self.started:.0f}s)",
            flush=True,
        )


if __name__ == "__main__":
    main()
