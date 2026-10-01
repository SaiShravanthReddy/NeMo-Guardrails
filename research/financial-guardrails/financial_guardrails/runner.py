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

"""Resumable, content-free static replay evaluation."""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterable
from pathlib import Path

from financial_guardrails.datasets import BenchmarkCase
from financial_guardrails.engine import PRECEDENCE, PolicyEngine
from financial_guardrails.evaluation import EvaluationRecord
from financial_guardrails.judge import PolicyJudgeDetector
from financial_guardrails.judge_backends import BackendCallMetrics, configured_judge_backend
from financial_guardrails.replay import event_from_message
from financial_guardrails.schema import Decision, Mode, RiskCategory, Surface, Verdict


def evaluate_cases(
    cases: Iterable[BenchmarkCase],
    *,
    judge_mode: str,
    backend_name: str = "rules_only",
    checkpoint_path: str | Path | None = None,
    progress_sink: Callable[[int, int], None] | None = None,
) -> tuple[EvaluationRecord, ...]:
    if judge_mode not in {"rules_only", "all_events", "rules_first_cascade"}:
        raise ValueError("unsupported judge mode")
    selected_cases = tuple(cases)
    metrics: list[BackendCallMetrics] = []
    rules_engine = PolicyEngine()
    full_engine = rules_engine
    if judge_mode != "rules_only":
        backend = configured_judge_backend(backend_name, metrics_sink=metrics.append)
        full_engine = PolicyEngine(additional_detectors=(PolicyJudgeDetector(backend),))

    checkpoint = Path(checkpoint_path) if checkpoint_path else None
    existing = _read_checkpoint(checkpoint) if checkpoint and checkpoint.exists() else {}
    expected_ids = {case.case_id for case in selected_cases}
    if not set(existing).issubset(expected_ids):
        raise ValueError("checkpoint contains cases outside this evaluation")
    if any(
        record.dataset_key != case.dataset_key or record.backend != backend_name or record.judge_mode != judge_mode
        for case in selected_cases
        for record in ([existing[case.case_id]] if case.case_id in existing else [])
    ):
        raise ValueError("checkpoint configuration does not match this evaluation")
    records = list(existing.values())
    completed = len(records)
    if progress_sink:
        progress_sink(completed, len(selected_cases))
    for case in selected_cases:
        if case.case_id in existing:
            continue
        started = time.monotonic()
        metric_start = len(metrics)
        verdicts: list[tuple[int, Surface, Verdict, bool]] = []
        for message in case.messages:
            event = event_from_message(case, message)
            rules_verdict = rules_engine.evaluate(event, mode=Mode.ENFORCE)
            rules_intervened = rules_verdict.recommended_decision is not Decision.ALLOW
            if judge_mode == "rules_only" or (judge_mode == "rules_first_cascade" and rules_intervened):
                verdict = rules_verdict
            else:
                verdict = full_engine.evaluate(event, mode=Mode.ENFORCE)
            verdicts.append((message.turn_index, event.surface, verdict, rules_intervened))
        record = _case_record(
            case,
            verdicts,
            metrics[metric_start:],
            backend=backend_name,
            judge_mode=judge_mode,
            latency_seconds=time.monotonic() - started,
        )
        records.append(record)
        if checkpoint:
            _append_checkpoint(checkpoint, record)
        completed += 1
        if progress_sink:
            progress_sink(completed, len(selected_cases))
    return tuple(records)


def _case_record(
    case: BenchmarkCase,
    verdicts: list[tuple[int, Surface, Verdict, bool]],
    calls: list[BackendCallMetrics],
    *,
    backend: str,
    judge_mode: str,
    latency_seconds: float,
) -> EvaluationRecord:
    detector_error = any(verdict.detector_error for _turn, _surface, verdict, _rules in verdicts)
    findings = [item for item in verdicts if item[2].recommended_decision is not Decision.ALLOW]
    primary = max(findings, key=lambda item: PRECEDENCE[item[2].recommended_decision]) if findings else None
    first_detection = min((turn for turn, _surface, _verdict, _rules in findings), default=None)
    dangerous_turn = min(
        (
            turn
            for turn, surface, verdict, _rules in verdicts
            if surface is Surface.TOOL_CALL and verdict.recommended_decision is not Decision.ALLOW
        ),
        default=None,
    )
    sidecar = case.metadata.get("sidecar", {})
    record_metadata = case.metadata.get("record", {})
    slices = {
        key: str(value)
        for key, value in {
            "risk_type": record_metadata.get("risk_type"),
            "behavior_mode": record_metadata.get("behavior_mode"),
            "ambiguous": record_metadata.get("ambiguous"),
            "case_type": sidecar.get("case_type"),
            "outcome": sidecar.get("outcome"),
        }.items()
        if value is not None
    }
    failure_code = "detector_error" if detector_error else None
    return EvaluationRecord(
        dataset_key=case.dataset_key,
        case_id=case.case_id,
        label=case.label,
        prediction=None if detector_error else bool(findings),
        decision=primary[2].recommended_decision if primary else Decision.ALLOW,
        risk_score=max((v.risk_score for _t, _s, v, _r in verdicts if v.risk_score is not None), default=None),
        detector_error=detector_error,
        failure_code=failure_code,
        policy_ids=tuple(dict.fromkeys(policy for _t, _s, v, _r in verdicts for policy in v.policy_ids)),
        risk_category=primary[2].risk_category if primary else RiskCategory.NONE,
        surface=primary[1] if primary else None,
        first_detection_turn=first_detection,
        dangerous_action_turn=dangerous_turn,
        judge_invoked=bool(calls),
        rules_intervened=any(rules for _t, _s, _v, rules in verdicts),
        latency_seconds=latency_seconds,
        input_tokens=_sum_int(call.input_tokens for call in calls),
        output_tokens=_sum_int(call.output_tokens for call in calls),
        estimated_cost_usd=_sum_float(call.estimated_cost_usd for call in calls),
        backend=backend,
        judge_mode=judge_mode,
        slices=slices,
        attack_succeeded=_optional_bool(sidecar.get("attack_success")),
    )


def _optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _sum_int(values: Iterable[int | None]) -> int | None:
    present = [value for value in values if value is not None]
    return sum(present) if present else None


def _sum_float(values: Iterable[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return sum(present) if present else None


def _read_checkpoint(path: Path) -> dict[str, EvaluationRecord]:
    records: dict[str, EvaluationRecord] = {}
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                record = EvaluationRecord.model_validate_json(line)
            except Exception as exc:
                raise ValueError(f"invalid checkpoint record at line {line_number}") from exc
            if record.case_id in records:
                raise ValueError("checkpoint contains duplicate case IDs")
            records[record.case_id] = record
    return records


def _append_checkpoint(path: Path, record: EvaluationRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(record.model_dump_json())
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
