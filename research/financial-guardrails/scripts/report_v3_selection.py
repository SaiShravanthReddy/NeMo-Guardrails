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

"""Compare matched Version 1 and Version 3 artifacts for policy selection."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from financial_guardrails.datasets import BenchmarkCase, cnfinbench_adapter, finvault_adapter
from financial_guardrails.evaluation import EvaluationRecord, grouped_paired_intervention_test, summarize_records
from financial_guardrails.results import read_evaluation_artifact
from financial_guardrails.splits import benchmark_group_id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    baseline_artifact = read_evaluation_artifact(args.baseline)
    candidate_artifact = read_evaluation_artifact(args.candidate)
    dataset_key = baseline_artifact.manifest.dataset_key
    if dataset_key != candidate_artifact.manifest.dataset_key:
        parser.error("artifacts must use the same dataset")
    if candidate_artifact.manifest.input_view != "v3_clean":
        parser.error("candidate must be a Version 3 clean-input artifact")
    adapter = (
        cnfinbench_adapter(args.data_dir) if dataset_key == "cnfinbench-pooled" else finvault_adapter(args.data_dir)
    )
    _validate_artifact_dataset(baseline_artifact, adapter)
    _validate_artifact_dataset(candidate_artifact, adapter)
    if dataset_key == "finvault-v5-fixed-full" and not candidate_artifact.manifest.reviewed_groups_sha256:
        parser.error("FinVault Version 3 candidate is missing its reviewed-source-group manifest checksum")
    cases = tuple(adapter.cases())
    baseline, candidate = _matched_records(
        _attach_source_groups(baseline_artifact.records, cases),
        _attach_source_groups(candidate_artifact.records, cases),
    )
    comparison = grouped_paired_intervention_test(baseline, candidate)
    baseline_metrics = summarize_records(baseline)
    candidate_metrics = summarize_records(candidate)
    lines = [
        "# Version 3 matched selection comparison",
        "",
        f"Dataset: `{dataset_key}`",
        "",
        "## Legacy intervention endpoint",
        "",
        "| Field | Baseline | Version 3 |",
        "| --- | ---: | ---: |",
        f"| Matched completed cases | {len(baseline)} | {len(candidate)} |",
        f"| F1 | {_percent(baseline_metrics.binary.f1)} | {_percent(candidate_metrics.binary.f1)} |",
        f"| Recall | {_percent(baseline_metrics.binary.recall)} | {_percent(candidate_metrics.binary.recall)} |",
        f"| False-positive rate | {_percent(comparison.baseline_false_positive_rate)} | {_percent(comparison.candidate_false_positive_rate)} |",
        "",
        "## Grouped normal-case intervention comparison",
        "",
        f"- Matched normal cases: {comparison.matched_normal_cases}",
        f"- Source groups: {comparison.source_groups}",
        f"- FPR reduction: {_percent(comparison.false_positive_rate_reduction)}",
        f"- Two-sided group sign-flip p-value: {comparison.two_sided_sign_flip_p_value:.6f}",
        f"- 95% group-bootstrap CI: [{_percent(comparison.confidence_interval.lower)}, {_percent(comparison.confidence_interval.upper)}]",
        f"- Exact enumeration: {comparison.exact_enumeration}",
        "",
        "## Version 3 threat endpoint",
        "",
        f"- Threat F1: {_percent(candidate_metrics.threat_attempt.binary.f1) if candidate_metrics.threat_attempt else 'unavailable'}",
        f"- Threat FPR: {_percent(candidate_metrics.threat_attempt.binary.false_positive_rate) if candidate_metrics.threat_attempt else 'unavailable'}",
        f"- Threat AUPRC: {_percent(candidate_metrics.threat_attempt.ranking.auprc) if candidate_metrics.threat_attempt else 'unavailable'}",
        "",
        "This report compares only mutually completed case IDs. It does not select a candidate automatically.",
        "",
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote matched Version 3 selection report to {args.output}")


def _attach_source_groups(
    records: tuple[EvaluationRecord, ...], cases: tuple[BenchmarkCase, ...]
) -> tuple[EvaluationRecord, ...]:
    groups = {case.case_id: benchmark_group_id(case) for case in cases}
    enriched = []
    for record in records:
        try:
            group = groups[record.case_id]
        except KeyError as exc:
            raise ValueError("artifact contains a case absent from the canonical dataset") from exc
        recorded_group = record.slices.get("source_group")
        if recorded_group is not None and recorded_group != group:
            raise ValueError("artifact source group does not match the canonical dataset")
        enriched.append(record.model_copy(update={"slices": {**record.slices, "source_group": group}}))
    return tuple(enriched)


def _validate_artifact_dataset(artifact, adapter) -> None:
    if artifact.manifest.dataset_sha256 != _sha256(adapter.data_path):
        raise ValueError("artifact data checksum does not match the canonical dataset")
    if artifact.manifest.metadata_sha256 != _sha256(adapter.metadata_path):
        raise ValueError("artifact metadata checksum does not match the canonical dataset")


def _matched_records(
    baseline: tuple[EvaluationRecord, ...], candidate: tuple[EvaluationRecord, ...]
) -> tuple[tuple[EvaluationRecord, ...], tuple[EvaluationRecord, ...]]:
    baseline_by_id = {record.case_id: record for record in baseline if record.prediction is not None}
    candidate_by_id = {record.case_id: record for record in candidate if record.prediction is not None}
    case_ids = sorted(baseline_by_id.keys() & candidate_by_id.keys())
    if not case_ids:
        raise ValueError("artifacts have no matched completed cases")
    if any(
        baseline_by_id[case_id].label != candidate_by_id[case_id].label
        or baseline_by_id[case_id].positive_label != candidate_by_id[case_id].positive_label
        for case_id in case_ids
    ):
        raise ValueError("matched records disagree on labels")
    return (
        tuple(baseline_by_id[case_id] for case_id in case_ids),
        tuple(candidate_by_id[case_id] for case_id in case_ids),
    )


def _percent(value: float | None) -> str:
    return "unavailable" if value is None else f"{value * 100:.1f}%"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    main()
