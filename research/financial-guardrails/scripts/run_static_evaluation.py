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
from datetime import datetime, timezone
from pathlib import Path

from financial_guardrails.configuration import DEFAULT_POLICY_PATH, load_policy
from financial_guardrails.datasets import cnfinbench_adapter, finvault_adapter, inspect_json_dataset
from financial_guardrails.evaluation import bootstrap_confidence_intervals, score_slices, summarize_records
from financial_guardrails.judge import DEFAULT_JUDGE_POLICY_PATH
from financial_guardrails.judge_backends import load_judge_backend_registry
from financial_guardrails.results import EvaluationArtifact, ExperimentManifest, write_evaluation_artifact
from financial_guardrails.runner import evaluate_cases
from financial_guardrails.splits import assign_splits


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
    parser.add_argument("--bootstrap-iterations", type=int, default=1000)
    args = parser.parse_args()
    if (args.judge_mode == "rules_only") != (args.backend == "rules_only"):
        parser.error("rules_only mode requires the rules_only backend, and judge modes require a judge backend")

    adapter = (
        cnfinbench_adapter(args.data_dir) if args.dataset == "cnfinbench-pooled" else finvault_adapter(args.data_dir)
    )
    all_cases = tuple(adapter.cases())
    assignment = {item.case_id: item for item in assign_splits(all_cases)}
    cases = (
        all_cases
        if args.split == "all"
        else tuple(case for case in all_cases if assignment[case.case_id].split == args.split)
    )
    if not cases:
        raise SystemExit("selected split is empty")
    code_commit = _git_commit()
    dataset_sha256 = inspect_json_dataset(adapter.data_path).sha256
    metadata_sha256 = _sha256(adapter.metadata_path)
    policy_sha256 = _sha256(DEFAULT_POLICY_PATH)
    judge_policy_sha256 = _sha256(DEFAULT_JUDGE_POLICY_PATH)
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "code_commit": code_commit,
                "dataset_sha256": dataset_sha256,
                "metadata_sha256": metadata_sha256,
                "policy_sha256": policy_sha256,
                "judge_policy_sha256": judge_policy_sha256,
                "backend": args.backend,
                "judge_mode": args.judge_mode,
                "split": args.split,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()[:12]
    run_id = f"{args.dataset}-{args.split}-{args.backend}-{args.judge_mode}-{fingerprint}"
    started = datetime.now(timezone.utc)
    records = evaluate_cases(
        cases,
        judge_mode=args.judge_mode,
        backend_name=args.backend,
        checkpoint_path=args.output_dir / f"{run_id}.checkpoint.jsonl",
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
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        policy_sha256=policy_sha256,
        judge_policy_sha256=judge_policy_sha256,
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
    )
    artifact = EvaluationArtifact(
        manifest=manifest,
        records=records,
        metrics=summarize_records(records, run_elapsed_seconds=(completed - started).total_seconds()),
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


if __name__ == "__main__":
    main()
