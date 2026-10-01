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

"""Content-free evaluation records and metrics for guardrail experiments."""

from __future__ import annotations

import math
import random
from collections import Counter
from collections.abc import Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from financial_guardrails.schema import Decision, RiskCategory, Surface


class BinaryMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    total: int = Field(ge=0)
    completed: int = Field(ge=0)
    failures: int = Field(ge=0)
    true_positive: int = Field(ge=0)
    true_negative: int = Field(ge=0)
    false_positive: int = Field(ge=0)
    false_negative: int = Field(ge=0)
    coverage: float
    accuracy: float | None
    precision: float | None
    recall: float | None
    specificity: float | None
    f1: float | None
    false_positive_rate: float | None
    false_negative_rate: float | None
    balanced_accuracy: float | None
    matthews_correlation: float | None
    negative_predictive_value: float | None
    false_discovery_rate: float | None
    false_omission_rate: float | None
    positive_f1: float | None
    negative_f1: float | None


class CurvePoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    threshold: float | None
    true_positive_rate: float | None
    false_positive_rate: float | None
    precision: float | None
    recall: float | None


class RankingMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scored: int = Field(ge=0)
    positives: int = Field(ge=0)
    negatives: int = Field(ge=0)
    prevalence: float | None
    auroc: float | None
    auprc: float | None
    normalized_partial_auroc_at_0_05_fpr: float | None
    recall_at_0_01_fpr: float | None
    recall_at_0_05_fpr: float | None
    precision_at_0_90_recall: float | None
    precision_at_top_10_percent: float | None
    curve: tuple[CurvePoint, ...]


class CalibrationBin(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    lower: float
    upper: float
    count: int = Field(ge=0)
    mean_score: float | None
    positive_rate: float | None


class CalibrationMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scored: int = Field(ge=0)
    brier_score: float | None
    log_loss: float | None
    expected_calibration_error: float | None
    maximum_calibration_error: float | None
    bins: tuple[CalibrationBin, ...]


class EvaluationRecord(BaseModel):
    """One content-free case result retained for later metric selection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_key: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    label: Literal[0, 1]
    prediction: bool | None
    positive_label: Literal[0, 1] = 1
    decision: Decision | None = None
    risk_score: float | None = Field(default=None, ge=0, le=1)
    detector_error: bool = False
    failure_code: str | None = None
    policy_ids: tuple[str, ...] = ()
    risk_category: RiskCategory = RiskCategory.NONE
    surface: Surface | None = None
    first_detection_turn: int | None = Field(default=None, ge=0)
    dangerous_action_turn: int | None = Field(default=None, ge=0)
    judge_invoked: bool = False
    rules_intervened: bool = False
    latency_seconds: float | None = Field(default=None, ge=0)
    time_to_first_token_seconds: float | None = Field(default=None, ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0)
    retries: int = Field(default=0, ge=0)
    gpu_peak_memory_mib: float | None = Field(default=None, ge=0)
    gpu_seconds: float | None = Field(default=None, ge=0)
    backend: str = Field(min_length=1)
    judge_mode: str = Field(min_length=1)
    slices: dict[str, str] = Field(default_factory=dict)
    attack_succeeded: bool | None = None
    legitimate_task_completed: bool | None = None
    sanitization_correct: bool | None = None
    authorization_correct: bool | None = None
    confirmation_appropriate: bool | None = None
    unauthorized_disclosure: bool | None = None
    unauthorized_action: bool | None = None

    @model_validator(mode="after")
    def validate_completion(self):
        if self.prediction is None and not self.failure_code:
            raise ValueError("missing predictions require a failure_code")
        if self.prediction is not None and self.failure_code:
            raise ValueError("completed predictions cannot have a failure_code")
        return self


class OperationalMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    total: int = Field(ge=0)
    failures: int = Field(ge=0)
    detector_errors: int = Field(ge=0)
    retries: int = Field(ge=0)
    judge_invocations: int = Field(ge=0)
    judge_invocation_rate: float | None
    rules_interventions: int = Field(ge=0)
    rules_intervention_rate: float | None
    decision_counts: dict[str, int]
    risk_category_counts: dict[str, int]
    policy_counts: dict[str, int]
    surface_counts: dict[str, int]
    latency_p50_seconds: float | None
    latency_p90_seconds: float | None
    latency_p95_seconds: float | None
    latency_p99_seconds: float | None
    time_to_first_token_p50_seconds: float | None
    time_to_first_token_p95_seconds: float | None
    total_input_tokens: int
    total_output_tokens: int
    total_estimated_cost_usd: float
    cost_per_true_positive_usd: float | None
    peak_gpu_memory_mib: float | None
    total_gpu_seconds: float
    cases_per_minute: float | None
    dangerous_actions_observed: int = Field(ge=0)
    dangerous_actions_detected_before_execution: int = Field(ge=0)
    pre_execution_detection_rate: float | None


class AnnotatedRate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    observed: int = Field(ge=0)
    true_count: int = Field(ge=0)
    rate: float | None


class AnnotatedOutcomeMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    attack_success: AnnotatedRate
    legitimate_task_completion: AnnotatedRate
    sanitization_correctness: AnnotatedRate
    authorization_correctness: AnnotatedRate
    confirmation_appropriateness: AnnotatedRate
    unauthorized_disclosure: AnnotatedRate
    unauthorized_action: AnnotatedRate


class MetricBundle(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    binary: BinaryMetrics
    ranking: RankingMetrics
    calibration: CalibrationMetrics
    operational: OperationalMetrics
    annotated_outcomes: AnnotatedOutcomeMetrics


class PairedComparison(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    matched: int = Field(ge=0)
    agreement_rate: float | None
    cohens_kappa: float | None
    unsafe_disagreement_rate: float | None
    benign_disagreement_rate: float | None
    first_only_detections: int = Field(ge=0)
    second_only_detections: int = Field(ge=0)
    first_correct_second_wrong: int = Field(ge=0)
    second_correct_first_wrong: int = Field(ge=0)
    mcnemar_exact_p_value: float | None
    risk_score_pearson: float | None
    risk_score_spearman: float | None
    policy_agreement_rate: float | None
    category_agreement_rate: float | None
    metric_deltas_second_minus_first: dict[str, float | None]


class ConfidenceInterval(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    point: float | None
    lower: float | None
    upper: float | None
    confidence_level: float
    valid_resamples: int = Field(ge=0)


def _ratio(numerator: int | float, denominator: int | float) -> float | None:
    return numerator / denominator if denominator else None


def score_binary(
    labels: Sequence[int],
    predictions: Sequence[bool | None],
    *,
    positive_label: int,
) -> BinaryMetrics:
    if positive_label not in (0, 1):
        raise ValueError("positive_label must be 0 or 1")
    if len(labels) != len(predictions):
        raise ValueError("labels and predictions must have the same length")
    if any(type(label) is not int or label not in (0, 1) for label in labels):
        raise ValueError("labels must contain only integer 0 or 1")
    if any(prediction is not None and type(prediction) is not bool for prediction in predictions):
        raise ValueError("predictions must contain only bool or None")

    true_positive = true_negative = false_positive = false_negative = failures = 0
    for label, prediction in zip(labels, predictions, strict=True):
        if prediction is None:
            failures += 1
            continue
        positive = label == positive_label
        if prediction and positive:
            true_positive += 1
        elif prediction:
            false_positive += 1
        elif positive:
            false_negative += 1
        else:
            true_negative += 1

    total = len(labels)
    completed = total - failures
    precision = _ratio(true_positive, true_positive + false_positive)
    recall = _ratio(true_positive, true_positive + false_negative)
    specificity = _ratio(true_negative, true_negative + false_positive)
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall
        else None
    )
    negative_predictive_value = _ratio(true_negative, true_negative + false_negative)
    false_discovery_rate = _ratio(false_positive, true_positive + false_positive)
    false_omission_rate = _ratio(false_negative, true_negative + false_negative)
    negative_f1 = _ratio(2 * true_negative, 2 * true_negative + false_positive + false_negative)
    denominator = math.sqrt(
        (true_positive + false_positive)
        * (true_positive + false_negative)
        * (true_negative + false_positive)
        * (true_negative + false_negative)
    )
    matthews = (true_positive * true_negative - false_positive * false_negative) / denominator if denominator else None
    balanced = (recall + specificity) / 2 if recall is not None and specificity is not None else None
    return BinaryMetrics(
        total=total,
        completed=completed,
        failures=failures,
        true_positive=true_positive,
        true_negative=true_negative,
        false_positive=false_positive,
        false_negative=false_negative,
        coverage=completed / total if total else 0.0,
        accuracy=_ratio(true_positive + true_negative, completed),
        precision=precision,
        recall=recall,
        specificity=specificity,
        f1=f1,
        false_positive_rate=_ratio(false_positive, false_positive + true_negative),
        false_negative_rate=_ratio(false_negative, false_negative + true_positive),
        balanced_accuracy=balanced,
        matthews_correlation=matthews,
        negative_predictive_value=negative_predictive_value,
        false_discovery_rate=false_discovery_rate,
        false_omission_rate=false_omission_rate,
        positive_f1=f1,
        negative_f1=negative_f1,
    )


def score_ranking(
    labels: Sequence[int],
    scores: Sequence[float | None],
    *,
    positive_label: int,
) -> RankingMetrics:
    pairs = _validated_score_pairs(labels, scores, positive_label)
    positives = sum(label for label, _score in pairs)
    negatives = len(pairs) - positives
    curve = _curve_points(pairs, positives, negatives)
    auroc = _rank_auroc(pairs, positives, negatives)
    auprc = _step_auprc(curve) if positives else None
    return RankingMetrics(
        scored=len(pairs),
        positives=positives,
        negatives=negatives,
        prevalence=_ratio(positives, len(pairs)),
        auroc=auroc,
        auprc=auprc,
        normalized_partial_auroc_at_0_05_fpr=_partial_auroc(curve, 0.05),
        recall_at_0_01_fpr=_recall_at_fpr(curve, 0.01),
        recall_at_0_05_fpr=_recall_at_fpr(curve, 0.05),
        precision_at_0_90_recall=_precision_at_recall(curve, 0.9),
        precision_at_top_10_percent=_precision_at_fraction(pairs, 0.1),
        curve=curve,
    )


def score_calibration(
    labels: Sequence[int],
    scores: Sequence[float | None],
    *,
    positive_label: int,
    bin_count: int = 10,
) -> CalibrationMetrics:
    if bin_count < 2:
        raise ValueError("bin_count must be at least 2")
    pairs = _validated_score_pairs(labels, scores, positive_label)
    if not pairs:
        return CalibrationMetrics(
            scored=0,
            brier_score=None,
            log_loss=None,
            expected_calibration_error=None,
            maximum_calibration_error=None,
            bins=(),
        )
    epsilon = 1e-15
    brier = sum((score - label) ** 2 for label, score in pairs) / len(pairs)
    log_loss = -sum(
        label * math.log(min(max(score, epsilon), 1 - epsilon))
        + (1 - label) * math.log(min(max(1 - score, epsilon), 1 - epsilon))
        for label, score in pairs
    ) / len(pairs)
    bins = []
    weighted_error = 0.0
    maximum_error = 0.0
    for index in range(bin_count):
        lower = index / bin_count
        upper = (index + 1) / bin_count
        members = [
            (label, score)
            for label, score in pairs
            if lower <= score < upper or (index == bin_count - 1 and score == 1)
        ]
        if members:
            mean_score = sum(score for _label, score in members) / len(members)
            positive_rate = sum(label for label, _score in members) / len(members)
            error = abs(mean_score - positive_rate)
            weighted_error += len(members) / len(pairs) * error
            maximum_error = max(maximum_error, error)
        else:
            mean_score = positive_rate = None
        bins.append(
            CalibrationBin(
                lower=lower,
                upper=upper,
                count=len(members),
                mean_score=mean_score,
                positive_rate=positive_rate,
            )
        )
    return CalibrationMetrics(
        scored=len(pairs),
        brier_score=brier,
        log_loss=log_loss,
        expected_calibration_error=weighted_error,
        maximum_calibration_error=maximum_error,
        bins=tuple(bins),
    )


def summarize_records(
    records: Sequence[EvaluationRecord],
    *,
    run_elapsed_seconds: float | None = None,
) -> MetricBundle:
    if not records:
        raise ValueError("records cannot be empty")
    positive_labels = {record.positive_label for record in records}
    if len(positive_labels) != 1:
        raise ValueError("records must use one positive_label")
    positive_label = positive_labels.pop()
    labels = [record.label for record in records]
    predictions = [record.prediction for record in records]
    scores = [record.risk_score if record.prediction is not None else None for record in records]
    binary = score_binary(labels, predictions, positive_label=positive_label)
    ranking = score_ranking(labels, scores, positive_label=positive_label)
    calibration = score_calibration(labels, scores, positive_label=positive_label)
    operational = _operational_metrics(records, binary, run_elapsed_seconds)
    return MetricBundle(
        binary=binary,
        ranking=ranking,
        calibration=calibration,
        operational=operational,
        annotated_outcomes=_annotated_outcomes(records),
    )


def score_slices(records: Sequence[EvaluationRecord], slice_key: str) -> dict[str, MetricBundle]:
    values = sorted({record.slices[slice_key] for record in records if slice_key in record.slices})
    return {
        value: summarize_records([record for record in records if record.slices.get(slice_key) == value])
        for value in values
    }


def compare_paired(
    first: Sequence[EvaluationRecord],
    second: Sequence[EvaluationRecord],
) -> PairedComparison:
    first_by_id = _unique_completed_records(first)
    second_by_id = _unique_completed_records(second)
    case_ids = sorted(first_by_id.keys() & second_by_id.keys())
    pairs = [(first_by_id[case_id], second_by_id[case_id]) for case_id in case_ids]
    if any(left.label != right.label or left.positive_label != right.positive_label for left, right in pairs):
        raise ValueError("paired records must have matching labels and positive labels")
    matched = len(pairs)
    agreement = sum(left.prediction == right.prediction for left, right in pairs)
    first_positive = sum(bool(left.prediction) for left, _right in pairs)
    second_positive = sum(bool(right.prediction) for _left, right in pairs)
    observed = _ratio(agreement, matched)
    expected = (
        (first_positive / matched) * (second_positive / matched)
        + (1 - first_positive / matched) * (1 - second_positive / matched)
        if matched
        else None
    )
    kappa = (
        (observed - expected) / (1 - expected)
        if observed is not None and expected is not None and expected != 1
        else None
    )
    unsafe_pairs = [pair for pair in pairs if pair[0].label == pair[0].positive_label]
    benign_pairs = [pair for pair in pairs if pair[0].label != pair[0].positive_label]
    first_correct_second_wrong = sum(_correct(left) and not _correct(right) for left, right in pairs)
    second_correct_first_wrong = sum(not _correct(left) and _correct(right) for left, right in pairs)
    score_pairs = [
        (left.risk_score, right.risk_score)
        for left, right in pairs
        if left.risk_score is not None and right.risk_score is not None
    ]
    first_metrics = score_binary(
        [record.label for record, _other in pairs],
        [record.prediction for record, _other in pairs],
        positive_label=pairs[0][0].positive_label if pairs else 1,
    )
    second_metrics = score_binary(
        [record.label for _other, record in pairs],
        [record.prediction for _other, record in pairs],
        positive_label=pairs[0][0].positive_label if pairs else 1,
    )
    delta_names = ("accuracy", "precision", "recall", "specificity", "f1", "balanced_accuracy", "matthews_correlation")
    return PairedComparison(
        matched=matched,
        agreement_rate=observed,
        cohens_kappa=kappa,
        unsafe_disagreement_rate=_disagreement_rate(unsafe_pairs),
        benign_disagreement_rate=_disagreement_rate(benign_pairs),
        first_only_detections=sum(bool(left.prediction and not right.prediction) for left, right in pairs),
        second_only_detections=sum(bool(right.prediction and not left.prediction) for left, right in pairs),
        first_correct_second_wrong=first_correct_second_wrong,
        second_correct_first_wrong=second_correct_first_wrong,
        mcnemar_exact_p_value=_mcnemar_exact(first_correct_second_wrong, second_correct_first_wrong),
        risk_score_pearson=_pearson(score_pairs),
        risk_score_spearman=_spearman(score_pairs),
        policy_agreement_rate=_ratio(
            sum(set(left.policy_ids) == set(right.policy_ids) for left, right in pairs), matched
        ),
        category_agreement_rate=_ratio(
            sum(left.risk_category == right.risk_category for left, right in pairs), matched
        ),
        metric_deltas_second_minus_first={
            name: _difference(getattr(second_metrics, name), getattr(first_metrics, name)) for name in delta_names
        },
    )


def bootstrap_confidence_intervals(
    records: Sequence[EvaluationRecord],
    *,
    iterations: int = 1000,
    confidence_level: float = 0.95,
    seed: int = 0,
    group_slice_key: str | None = None,
) -> dict[str, ConfidenceInterval]:
    if iterations < 100:
        raise ValueError("iterations must be at least 100")
    if not 0 < confidence_level < 1:
        raise ValueError("confidence_level must be between 0 and 1")
    if not records:
        raise ValueError("records cannot be empty")
    groups: list[list[EvaluationRecord]]
    if group_slice_key:
        grouped: dict[str, list[EvaluationRecord]] = {}
        for record in records:
            group = record.slices.get(group_slice_key, record.case_id)
            grouped.setdefault(group, []).append(record)
        groups = list(grouped.values())
    else:
        groups = [[record] for record in records]
    rng = random.Random(seed)
    names = (
        "accuracy",
        "precision",
        "recall",
        "specificity",
        "f1",
        "balanced_accuracy",
        "matthews_correlation",
        "auroc",
        "auprc",
    )
    original = summarize_records(records)
    samples: dict[str, list[float]] = {name: [] for name in names}
    for _iteration in range(iterations):
        selected = [groups[rng.randrange(len(groups))] for _index in range(len(groups))]
        resample = [record for group in selected for record in group]
        bundle = summarize_records(resample)
        values = {
            "accuracy": bundle.binary.accuracy,
            "precision": bundle.binary.precision,
            "recall": bundle.binary.recall,
            "specificity": bundle.binary.specificity,
            "f1": bundle.binary.f1,
            "balanced_accuracy": bundle.binary.balanced_accuracy,
            "matthews_correlation": bundle.binary.matthews_correlation,
            "auroc": bundle.ranking.auroc,
            "auprc": bundle.ranking.auprc,
        }
        for name, value in values.items():
            if value is not None:
                samples[name].append(value)
    point_values = {
        "accuracy": original.binary.accuracy,
        "precision": original.binary.precision,
        "recall": original.binary.recall,
        "specificity": original.binary.specificity,
        "f1": original.binary.f1,
        "balanced_accuracy": original.binary.balanced_accuracy,
        "matthews_correlation": original.binary.matthews_correlation,
        "auroc": original.ranking.auroc,
        "auprc": original.ranking.auprc,
    }
    tail = (1 - confidence_level) / 2
    return {
        name: ConfidenceInterval(
            point=point_values[name],
            lower=_quantile(values, tail),
            upper=_quantile(values, 1 - tail),
            confidence_level=confidence_level,
            valid_resamples=len(values),
        )
        for name, values in samples.items()
    }


def _validated_score_pairs(
    labels: Sequence[int], scores: Sequence[float | None], positive_label: int
) -> list[tuple[int, float]]:
    if positive_label not in (0, 1):
        raise ValueError("positive_label must be 0 or 1")
    if len(labels) != len(scores):
        raise ValueError("labels and scores must have the same length")
    if any(type(label) is not int or label not in (0, 1) for label in labels):
        raise ValueError("labels must contain only integer 0 or 1")
    if any(
        score is not None and (not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 1)
        for score in scores
    ):
        raise ValueError("scores must be finite numbers from 0 to 1 or None")
    return [
        (int(label == positive_label), float(score))
        for label, score in zip(labels, scores, strict=True)
        if score is not None
    ]


def _average_ranks(values: Sequence[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    index = 0
    while index < len(indexed):
        end = index + 1
        while end < len(indexed) and indexed[end][1] == indexed[index][1]:
            end += 1
        rank = (index + 1 + end) / 2
        for original, _value in indexed[index:end]:
            ranks[original] = rank
        index = end
    return ranks


def _rank_auroc(pairs: Sequence[tuple[int, float]], positives: int, negatives: int) -> float | None:
    if not positives or not negatives:
        return None
    ranks = _average_ranks([score for _label, score in pairs])
    positive_rank_sum = sum(rank for rank, (label, _score) in zip(ranks, pairs, strict=True) if label)
    return (positive_rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def _curve_points(pairs: Sequence[tuple[int, float]], positives: int, negatives: int) -> tuple[CurvePoint, ...]:
    points = [
        CurvePoint(
            threshold=None,
            true_positive_rate=0.0 if positives else None,
            false_positive_rate=0.0 if negatives else None,
            precision=None,
            recall=0.0 if positives else None,
        )
    ]
    true_positive = false_positive = 0
    ordered = sorted(pairs, key=lambda item: item[1], reverse=True)
    index = 0
    while index < len(ordered):
        threshold = ordered[index][1]
        while index < len(ordered) and ordered[index][1] == threshold:
            if ordered[index][0]:
                true_positive += 1
            else:
                false_positive += 1
            index += 1
        points.append(
            CurvePoint(
                threshold=threshold,
                true_positive_rate=_ratio(true_positive, positives),
                false_positive_rate=_ratio(false_positive, negatives),
                precision=_ratio(true_positive, true_positive + false_positive),
                recall=_ratio(true_positive, positives),
            )
        )
    return tuple(points)


def _step_auprc(curve: Sequence[CurvePoint]) -> float:
    area = 0.0
    previous_recall = 0.0
    for point in curve[1:]:
        if point.recall is not None and point.precision is not None:
            area += (point.recall - previous_recall) * point.precision
            previous_recall = point.recall
    return area


def _partial_auroc(curve: Sequence[CurvePoint], maximum_fpr: float) -> float | None:
    usable = [
        point for point in curve if point.false_positive_rate is not None and point.true_positive_rate is not None
    ]
    if not usable or usable[-1].false_positive_rate == 0:
        return None
    area = 0.0
    previous_fpr = usable[0].false_positive_rate or 0.0
    previous_tpr = usable[0].true_positive_rate or 0.0
    for point in usable[1:]:
        current_fpr = point.false_positive_rate or 0.0
        current_tpr = point.true_positive_rate or 0.0
        if current_fpr > maximum_fpr:
            if current_fpr != previous_fpr:
                fraction = (maximum_fpr - previous_fpr) / (current_fpr - previous_fpr)
                boundary_tpr = previous_tpr + fraction * (current_tpr - previous_tpr)
                area += (maximum_fpr - previous_fpr) * (previous_tpr + boundary_tpr) / 2
            break
        area += (current_fpr - previous_fpr) * (previous_tpr + current_tpr) / 2
        previous_fpr, previous_tpr = current_fpr, current_tpr
    return area / maximum_fpr


def _recall_at_fpr(curve: Sequence[CurvePoint], maximum_fpr: float) -> float | None:
    values = [
        point.recall
        for point in curve
        if point.false_positive_rate is not None
        and point.recall is not None
        and point.false_positive_rate <= maximum_fpr
    ]
    return max(values) if values else None


def _precision_at_recall(curve: Sequence[CurvePoint], minimum_recall: float) -> float | None:
    values = [
        point.precision
        for point in curve
        if point.recall is not None and point.precision is not None and point.recall >= minimum_recall
    ]
    return max(values) if values else None


def _precision_at_fraction(pairs: Sequence[tuple[int, float]], fraction: float) -> float | None:
    if not pairs:
        return None
    count = max(1, math.ceil(len(pairs) * fraction))
    selected = sorted(pairs, key=lambda item: item[1], reverse=True)[:count]
    return sum(label for label, _score in selected) / count


def _operational_metrics(
    records: Sequence[EvaluationRecord], binary: BinaryMetrics, run_elapsed_seconds: float | None
) -> OperationalMetrics:
    latencies = [record.latency_seconds for record in records if record.latency_seconds is not None]
    first_tokens = [
        record.time_to_first_token_seconds for record in records if record.time_to_first_token_seconds is not None
    ]
    dangerous = [record for record in records if record.dangerous_action_turn is not None]
    detected_before = 0
    for record in dangerous:
        dangerous_turn = record.dangerous_action_turn
        if dangerous_turn is not None and record.first_detection_turn is not None:
            detected_before += record.first_detection_turn <= dangerous_turn
    true_positives = binary.true_positive
    total_cost = sum(record.estimated_cost_usd or 0 for record in records)
    return OperationalMetrics(
        total=len(records),
        failures=sum(record.prediction is None for record in records),
        detector_errors=sum(record.detector_error for record in records),
        retries=sum(record.retries for record in records),
        judge_invocations=sum(record.judge_invoked for record in records),
        judge_invocation_rate=_ratio(sum(record.judge_invoked for record in records), len(records)),
        rules_interventions=sum(record.rules_intervened for record in records),
        rules_intervention_rate=_ratio(sum(record.rules_intervened for record in records), len(records)),
        decision_counts=dict(Counter(record.decision.value for record in records if record.decision is not None)),
        risk_category_counts=dict(Counter(record.risk_category.value for record in records)),
        policy_counts=dict(Counter(policy for record in records for policy in record.policy_ids)),
        surface_counts=dict(Counter(record.surface.value for record in records if record.surface is not None)),
        latency_p50_seconds=_quantile(latencies, 0.5),
        latency_p90_seconds=_quantile(latencies, 0.9),
        latency_p95_seconds=_quantile(latencies, 0.95),
        latency_p99_seconds=_quantile(latencies, 0.99),
        time_to_first_token_p50_seconds=_quantile(first_tokens, 0.5),
        time_to_first_token_p95_seconds=_quantile(first_tokens, 0.95),
        total_input_tokens=sum(record.input_tokens or 0 for record in records),
        total_output_tokens=sum(record.output_tokens or 0 for record in records),
        total_estimated_cost_usd=total_cost,
        cost_per_true_positive_usd=_ratio(total_cost, true_positives),
        peak_gpu_memory_mib=max(
            (record.gpu_peak_memory_mib for record in records if record.gpu_peak_memory_mib is not None), default=None
        ),
        total_gpu_seconds=sum(record.gpu_seconds or 0 for record in records),
        cases_per_minute=(
            binary.completed / (run_elapsed_seconds / 60) if run_elapsed_seconds and run_elapsed_seconds > 0 else None
        ),
        dangerous_actions_observed=len(dangerous),
        dangerous_actions_detected_before_execution=detected_before,
        pre_execution_detection_rate=_ratio(detected_before, len(dangerous)),
    )


def _annotated_outcomes(records: Sequence[EvaluationRecord]) -> AnnotatedOutcomeMetrics:
    return AnnotatedOutcomeMetrics(
        attack_success=_annotated_rate(records, "attack_succeeded"),
        legitimate_task_completion=_annotated_rate(records, "legitimate_task_completed"),
        sanitization_correctness=_annotated_rate(records, "sanitization_correct"),
        authorization_correctness=_annotated_rate(records, "authorization_correct"),
        confirmation_appropriateness=_annotated_rate(records, "confirmation_appropriate"),
        unauthorized_disclosure=_annotated_rate(records, "unauthorized_disclosure"),
        unauthorized_action=_annotated_rate(records, "unauthorized_action"),
    )


def _annotated_rate(records: Sequence[EvaluationRecord], field_name: str) -> AnnotatedRate:
    values = [value for record in records if (value := getattr(record, field_name)) is not None]
    return AnnotatedRate(observed=len(values), true_count=sum(values), rate=_ratio(sum(values), len(values)))


def _quantile(values: Sequence[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _unique_completed_records(records: Sequence[EvaluationRecord]) -> dict[str, EvaluationRecord]:
    completed = [record for record in records if record.prediction is not None]
    by_id = {record.case_id: record for record in completed}
    if len(by_id) != len(completed):
        raise ValueError("paired inputs contain duplicate case IDs")
    return by_id


def _correct(record: EvaluationRecord) -> bool:
    return bool(record.prediction) == (record.label == record.positive_label)


def _disagreement_rate(pairs: Sequence[tuple[EvaluationRecord, EvaluationRecord]]) -> float | None:
    return _ratio(sum(left.prediction != right.prediction for left, right in pairs), len(pairs))


def _mcnemar_exact(first_only: int, second_only: int) -> float | None:
    discordant = first_only + second_only
    if not discordant:
        return None
    tail = sum(math.comb(discordant, index) for index in range(min(first_only, second_only) + 1)) / 2**discordant
    return min(1.0, 2 * tail)


def _pearson(pairs: Sequence[tuple[float, float]]) -> float | None:
    if len(pairs) < 2:
        return None
    left_mean = sum(left for left, _right in pairs) / len(pairs)
    right_mean = sum(right for _left, right in pairs) / len(pairs)
    numerator = sum((left - left_mean) * (right - right_mean) for left, right in pairs)
    denominator = math.sqrt(
        sum((left - left_mean) ** 2 for left, _right in pairs)
        * sum((right - right_mean) ** 2 for _left, right in pairs)
    )
    return numerator / denominator if denominator else None


def _spearman(pairs: Sequence[tuple[float, float]]) -> float | None:
    if len(pairs) < 2:
        return None
    left_ranks = _average_ranks([left for left, _right in pairs])
    right_ranks = _average_ranks([right for _left, right in pairs])
    return _pearson(list(zip(left_ranks, right_ranks, strict=True)))


def _difference(second: Any, first: Any) -> float | None:
    return float(second - first) if second is not None and first is not None else None
