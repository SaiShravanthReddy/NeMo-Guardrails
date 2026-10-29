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

"""Separate Version 3 event routing with application-owned authorization."""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from financial_guardrails.authorization import (
    AuthorizationDetector,
    AuthorizationRequirement,
    TrustedAuthorizationContext,
)
from financial_guardrails.benchmark_input import opaque_event_id
from financial_guardrails.datasets import BenchmarkCase
from financial_guardrails.engine import PRECEDENCE, THREAT_PRECEDENCE, PolicyEngine
from financial_guardrails.evaluation import EvaluationRecord
from financial_guardrails.finvault_v3_policy import FinVaultV3BoundaryDetector
from financial_guardrails.judge import JudgeOutputError
from financial_guardrails.judge_backends import BackendCallMetrics
from financial_guardrails.outcome_judge import OutcomeJudgeResponse, TrustedOutcomeContext, V3OutcomeJudge
from financial_guardrails.replay import event_from_message
from financial_guardrails.schema import (
    Decision,
    DetectorResult,
    DetectorStatus,
    Evidence,
    Mode,
    RiskCategory,
    SecurityEvent,
    Surface,
    Verdict,
)
from financial_guardrails.splits import benchmark_group_id
from financial_guardrails.v3_judge import V3PolicyJudgeDetector


class TrustedAuthorizationResolver(Protocol):
    """Resolve application facts using only an opaque event identifier."""

    def resolve(self, event_id: str) -> tuple[TrustedAuthorizationContext, AuthorizationRequirement]: ...


class TrustedOutcomeResolver(Protocol):
    """Resolve application execution facts using only an opaque conversation ID."""

    def resolve(self, conversation_id: str) -> TrustedOutcomeContext: ...


@dataclass(frozen=True)
class V3EventResult:
    """Content-free routing result for one Version 3 event."""

    verdict: Verdict
    authorization_result: DetectorResult
    deterministic_result: Verdict
    judge_invoked: bool


class V3EventEvaluator:
    """Apply authorization and rules before routing unresolved events to the V3 judge."""

    def __init__(
        self,
        *,
        rules_engine: PolicyEngine,
        authorization_resolver: TrustedAuthorizationResolver,
        judge: V3PolicyJudgeDetector,
    ):
        self.rules_engine = rules_engine
        self.authorization_resolver = authorization_resolver
        self.judge = judge
        self.authorization_detector = AuthorizationDetector()

    def evaluate(self, event: SecurityEvent) -> V3EventResult:
        if event.surface is Surface.TOOL_CALL:
            authorization, requirement = self.authorization_resolver.resolve(event.event_id)
        else:
            authorization = TrustedAuthorizationContext()
            requirement = AuthorizationRequirement(operation="message")
        authorization_result = self.authorization_detector.detect(event, authorization, requirement)
        deterministic = self.rules_engine.evaluate(event, mode=Mode.ENFORCE)
        if _intervenes(authorization_result.decision) or _intervenes(deterministic.recommended_decision):
            return V3EventResult(
                verdict=_merge(event, self.rules_engine, authorization_result, deterministic),
                authorization_result=authorization_result,
                deterministic_result=deterministic,
                judge_invoked=False,
            )
        try:
            judge_result = self.judge.detect(event, authorization, requirement)
        except (JudgeOutputError, TimeoutError, RuntimeError, ValueError) as exc:
            judge_result = _failed_judge_result(event, self.rules_engine, exc)
        return V3EventResult(
            verdict=_merge(event, self.rules_engine, authorization_result, deterministic, judge_result),
            authorization_result=authorization_result,
            deterministic_result=deterministic,
            judge_invoked=True,
        )


def v3_rules_engine_for_dataset(dataset_key: str) -> PolicyEngine:
    """Build the isolated Version 3 deterministic policy stack for one dataset."""

    if dataset_key == "finvault-v5-fixed-full":
        return PolicyEngine(additional_detectors=(FinVaultV3BoundaryDetector(),), include_tool_policy=False)
    if dataset_key == "cnfinbench-pooled":
        return PolicyEngine()
    raise ValueError("unsupported Version 3 dataset")


class V3OutcomeEvaluator:
    """Run independent outcome assessment with application-owned execution facts."""

    def __init__(self, *, outcome_resolver: TrustedOutcomeResolver, outcome_judge: V3OutcomeJudge):
        self.outcome_resolver = outcome_resolver
        self.outcome_judge = outcome_judge

    def assess(self, conversation_id: str, events: tuple[SecurityEvent, ...]) -> OutcomeJudgeResponse:
        return self.outcome_judge.assess(events, self.outcome_resolver.resolve(conversation_id))


def evaluate_v3_cases(
    cases: Iterable[BenchmarkCase],
    *,
    event_evaluator: V3EventEvaluator,
    outcome_evaluator: V3OutcomeEvaluator | None,
    backend: str,
    checkpoint_path: str | Path | None = None,
    progress_sink: Callable[[int, int], None] | None = None,
    backend_metrics: list[BackendCallMetrics] | None = None,
) -> tuple[EvaluationRecord, ...]:
    """Replay Version 3 with clean benchmark input and application-owned facts."""

    selected_cases = tuple(cases)
    checkpoint = Path(checkpoint_path) if checkpoint_path else None
    existing = _read_checkpoint(checkpoint) if checkpoint and checkpoint.exists() else {}
    expected_ids = {case.case_id for case in selected_cases}
    if not set(existing).issubset(expected_ids):
        raise ValueError("checkpoint contains cases outside this evaluation")
    if any(
        record.dataset_key != case.dataset_key
        or record.backend != backend
        or record.judge_mode != "v3_rules_first_cascade"
        or record.input_view != "v3_clean"
        for case in selected_cases
        for record in ([existing[case.case_id]] if case.case_id in existing else [])
    ):
        raise ValueError("checkpoint configuration does not match this evaluation")

    records = list(existing.values())
    metrics = backend_metrics if backend_metrics is not None else []
    if progress_sink:
        progress_sink(len(records), len(selected_cases))
    for case in selected_cases:
        if case.case_id in existing:
            continue
        started = time.monotonic()
        metric_start = len(metrics)
        event_attempt_start = event_evaluator.judge.completion_attempts
        event_repair_start = event_evaluator.judge.repair_attempts
        outcome_attempt_start = (
            outcome_evaluator.outcome_judge.completion_attempts if outcome_evaluator is not None else 0
        )
        outcome_repair_start = outcome_evaluator.outcome_judge.repair_attempts if outcome_evaluator is not None else 0
        try:
            events = tuple(event_from_message(case, message, input_view="v3_clean") for message in case.messages)
            results = tuple(event_evaluator.evaluate(event) for event in events)
            outcome_events = tuple(
                event for event in events if event.surface in {Surface.OUTPUT, Surface.TOOL_CALL, Surface.TOOL_RESULT}
            )
            outcome = None
            outcome_error = False
            if outcome_evaluator and outcome_events:
                try:
                    outcome = outcome_evaluator.assess(_opaque_conversation_id(case), outcome_events)
                except (JudgeOutputError, TimeoutError, RuntimeError, ValueError):
                    outcome_error = True
            record = build_v3_evaluation_record(
                case,
                results,
                outcome,
                backend=backend,
                outcome_error=outcome_error,
                judge_attempts=(
                    event_evaluator.judge.completion_attempts
                    - event_attempt_start
                    + (
                        outcome_evaluator.outcome_judge.completion_attempts - outcome_attempt_start
                        if outcome_evaluator is not None
                        else 0
                    )
                ),
                judge_backend_calls=len(metrics[metric_start:]),
                judge_retries=(
                    event_evaluator.judge.repair_attempts
                    - event_repair_start
                    + (
                        outcome_evaluator.outcome_judge.repair_attempts - outcome_repair_start
                        if outcome_evaluator is not None
                        else 0
                    )
                ),
                judge_invoked=any(item.judge_invoked for item in results) or outcome is not None or outcome_error,
                rules_intervened=any(_intervenes(item.deterministic_result.recommended_decision) for item in results),
                calls=metrics[metric_start:],
            ).model_copy(update={"latency_seconds": time.monotonic() - started, "slices": _slices(case)})
        except (JudgeOutputError, TimeoutError, ValueError):
            record = _v3_error_record(case, backend=backend, latency_seconds=time.monotonic() - started)
        records.append(record)
        if checkpoint:
            _append_checkpoint(checkpoint, record)
        if progress_sink:
            progress_sink(len(records), len(selected_cases))
    return tuple(records)


def build_v3_evaluation_record(
    case: BenchmarkCase,
    event_results: tuple[V3EventResult, ...],
    outcome: OutcomeJudgeResponse | None,
    *,
    backend: str,
    outcome_error: bool = False,
    judge_attempts: int = 0,
    judge_backend_calls: int = 0,
    judge_retries: int = 0,
    judge_invoked: bool | None = None,
    rules_intervened: bool = False,
    calls: list[BackendCallMetrics] | None = None,
) -> EvaluationRecord:
    """Build a content-free record with independent attempt and outcome fields."""

    verdicts = [item.verdict for item in event_results]
    primary = max(verdicts, key=lambda verdict: PRECEDENCE[verdict.recommended_decision]) if verdicts else None
    threats = [verdict for verdict in verdicts if verdict.threat_assessment is not None]
    detector_error = any(verdict.detector_error for verdict in verdicts)
    evaluation_metadata = case.metadata.get("evaluation", {})
    return EvaluationRecord(
        dataset_key=case.dataset_key,
        case_id=case.case_id,
        label=case.label,
        prediction=None if detector_error else any(_intervenes(verdict.recommended_decision) for verdict in verdicts),
        decision=primary.recommended_decision if primary else Decision.ALLOW,
        # Version 3 threat and outcome scores have independent semantics. Do not
        # repurpose the Version 1 intervention score for either metric.
        risk_score=None,
        threat_assessment=(
            max((verdict.threat_assessment for verdict in threats), key=THREAT_PRECEDENCE.__getitem__)
            if threats
            else None
        ),
        threat_score=max(
            (verdict.threat_score for verdict in threats if verdict.threat_score is not None), default=None
        ),
        detector_error=detector_error,
        failure_code="v3_detector_error" if detector_error else None,
        policy_ids=tuple(dict.fromkeys(policy for verdict in verdicts for policy in verdict.policy_ids)),
        primary_policy_ids=primary.policy_ids if primary else (),
        risk_category=primary.risk_category if primary else RiskCategory.NONE,
        judge_invoked=any(item.judge_invoked for item in event_results) if judge_invoked is None else judge_invoked,
        judge_attempts=judge_attempts,
        judge_backend_calls=judge_backend_calls,
        rules_intervened=rules_intervened,
        input_tokens=_sum_int(call.input_tokens for call in calls or ()),
        output_tokens=_sum_int(call.output_tokens for call in calls or ()),
        estimated_cost_usd=_sum_float(call.estimated_cost_usd for call in calls or ()),
        retries=judge_retries,
        backend=backend,
        judge_mode="v3_rules_first_cascade",
        input_view="v3_clean",
        attack_succeeded=(
            evaluation_metadata.get("attack_success")
            if isinstance(evaluation_metadata.get("attack_success"), bool)
            else None
        ),
        attack_success_prediction=outcome.attack_succeeded if outcome else None,
        attack_success_risk_score=outcome.outcome_score if outcome else None,
        attack_success_detector_error=outcome_error,
        outcome_score_detector_error=outcome_error,
    )


def _opaque_conversation_id(case: BenchmarkCase) -> str:
    return opaque_event_id(case.dataset_key, case.case_id, -1)


def _slices(case: BenchmarkCase) -> dict[str, str]:
    record_metadata = case.metadata.get("record", {})
    sidecar = case.metadata.get("sidecar", {})
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
    if case.dataset_key in {"cnfinbench-pooled", "finvault-v5-fixed-full"}:
        slices["source_group"] = benchmark_group_id(case)
    return slices


def _v3_error_record(case: BenchmarkCase, *, backend: str, latency_seconds: float) -> EvaluationRecord:
    return EvaluationRecord(
        dataset_key=case.dataset_key,
        case_id=case.case_id,
        label=case.label,
        prediction=None,
        decision=None,
        detector_error=True,
        failure_code="v3_detector_error",
        backend=backend,
        judge_mode="v3_rules_first_cascade",
        input_view="v3_clean",
        latency_seconds=latency_seconds,
        slices=_slices(case),
    )


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


def _intervenes(decision: Decision) -> bool:
    return decision in {Decision.BLOCK, Decision.SANITIZE, Decision.REQUIRE_CONFIRMATION}


def _failed_judge_result(event: SecurityEvent, engine: PolicyEngine, exc: Exception) -> DetectorResult:
    high_impact = event.surface is Surface.TOOL_CALL or event.tool_name in {
        *engine.config.tools.confirmation_required,
        *engine.config.tools.denied,
    }
    decision = engine.config.failure_policy.high_impact if high_impact else engine.config.failure_policy.ordinary
    return DetectorResult(
        detector="v3_policy_judge",
        status=DetectorStatus.ERROR,
        decision=decision,
        policy_ids=("DETECTOR-ERROR",),
        risk_category=RiskCategory.DETECTOR_FAILURE,
        evidence=(
            Evidence(
                detector="v3_policy_judge",
                rule_id="DETECTOR-ERROR",
                summary="Version 3 policy judge failed after bounded validation.",
            ),
        ),
        explanation="The Version 3 policy judge did not return a usable decision.",
        error_code=_judge_error_code(exc),
    )


def _judge_error_code(exc: Exception) -> str:
    if isinstance(exc, TimeoutError):
        return "detector_timeout"
    if isinstance(exc, JudgeOutputError):
        return exc.code
    if "backend request failed" in str(exc).lower():
        return "judge_backend_request_failed"
    return "detector_failure"


def _merge(
    event: SecurityEvent,
    engine: PolicyEngine,
    *results: DetectorResult | Verdict,
) -> Verdict:
    """Create a Version 3 verdict without dropping threat-only audit findings."""

    detector_results: list[DetectorResult] = []
    for result in results:
        if isinstance(result, Verdict):
            detector_results.append(
                DetectorResult(
                    detector="deterministic_rules",
                    status=DetectorStatus.ERROR if result.detector_error else DetectorStatus.OK,
                    decision=result.recommended_decision,
                    policy_ids=result.policy_ids,
                    risk_category=result.risk_category,
                    evidence=result.evidence,
                    explanation=result.explanation,
                    threat_assessment=result.threat_assessment,
                    threat_score=result.threat_score,
                )
            )
        else:
            detector_results.append(result)
    recommended = max((result.decision for result in detector_results), key=PRECEDENCE.__getitem__)
    audit = [
        result
        for result in detector_results
        if result.decision is not Decision.ALLOW or result.threat_assessment is not None
    ]
    primary = max(audit, key=lambda result: PRECEDENCE[result.decision]) if audit else None
    return Verdict(
        policy_id=engine.config.policy_id,
        policy_version=engine.config.policy_version,
        mode=Mode.ENFORCE,
        decision=recommended,
        recommended_decision=recommended,
        policy_ids=tuple(dict.fromkeys(policy for result in audit for policy in result.policy_ids)),
        risk_category=primary.risk_category if primary else RiskCategory.NONE,
        evidence=tuple(evidence for result in audit for evidence in result.evidence),
        explanation=primary.explanation if primary else "No configured policy matched.",
        detector_error=any(result.status is DetectorStatus.ERROR for result in detector_results),
        detector_statuses={result.detector: result.status for result in detector_results},
        detector_error_codes={
            result.detector: result.error_code or "detector_failure"
            for result in detector_results
            if result.status is DetectorStatus.ERROR
        },
        content="" if recommended is Decision.BLOCK else event.content,
        threat_assessment=next(
            (result.threat_assessment for result in reversed(audit) if result.threat_assessment is not None), None
        ),
        threat_score=max((result.threat_score for result in audit if result.threat_score is not None), default=None),
    )
