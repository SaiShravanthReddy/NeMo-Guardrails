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

import pytest
from financial_guardrails.evaluation import (
    EvaluationRecord,
    bootstrap_confidence_intervals,
    compare_paired,
    score_binary,
    score_calibration,
    score_ranking,
    score_slices,
    summarize_records,
)
from financial_guardrails.schema import Decision, RiskCategory, Surface


def test_binary_metrics_keep_failures_out_of_confusion_matrix():
    metrics = score_binary([1, 1, 0, 0, 1], [True, False, True, False, None], positive_label=1)

    assert metrics.total == 5
    assert metrics.completed == 4
    assert metrics.failures == 1
    assert metrics.coverage == 0.8
    assert (metrics.true_positive, metrics.true_negative) == (1, 1)
    assert (metrics.false_positive, metrics.false_negative) == (1, 1)
    assert metrics.accuracy == 0.5
    assert metrics.precision == 0.5
    assert metrics.recall == 0.5
    assert metrics.specificity == 0.5
    assert metrics.f1 == 0.5
    assert metrics.balanced_accuracy == 0.5
    assert metrics.matthews_correlation == 0
    assert metrics.negative_predictive_value == 0.5
    assert metrics.false_discovery_rate == 0.5
    assert metrics.false_omission_rate == 0.5
    assert metrics.positive_f1 == 0.5
    assert metrics.negative_f1 == 0.5


def test_positive_label_is_explicit_and_reversible():
    metrics = score_binary([0, 1], [True, False], positive_label=0)

    assert metrics.true_positive == 1
    assert metrics.true_negative == 1


@pytest.mark.parametrize(
    ("labels", "predictions", "positive_label"),
    [
        ([0], [], 1),
        ([2], [True], 1),
        ([0], [1], 1),
        ([0], [True], 2),
    ],
)
def test_invalid_metric_inputs_are_rejected(labels, predictions, positive_label):
    with pytest.raises(ValueError):
        score_binary(labels, predictions, positive_label=positive_label)


def record(case_id, label, prediction, score, **updates: object):
    payload: dict[str, object] = {
        "dataset_key": "fixture",
        "case_id": case_id,
        "label": label,
        "prediction": prediction,
        "risk_score": score,
        "decision": Decision.BLOCK if prediction else Decision.ALLOW,
        "backend": "fixture-backend",
        "judge_mode": "all_events",
    }
    payload.update(updates)
    return EvaluationRecord.model_validate(payload)


def test_ranking_metrics_handle_perfect_ordering_and_missing_scores():
    metrics = score_ranking([1, 0, 1, 0, 1], [0.9, 0.1, 0.8, 0.2, None], positive_label=1)

    assert metrics.scored == 4
    assert metrics.positives == 2
    assert metrics.negatives == 2
    assert metrics.prevalence == 0.5
    assert metrics.auroc == 1
    assert metrics.auprc == 1
    assert metrics.normalized_partial_auroc_at_0_05_fpr == 1
    assert metrics.recall_at_0_01_fpr == 1
    assert metrics.recall_at_0_05_fpr == 1
    assert metrics.precision_at_0_90_recall == 1
    assert metrics.precision_at_top_10_percent == 1
    assert metrics.curve[0].threshold is None


def test_tied_scores_have_chance_auroc():
    metrics = score_ranking([1, 0, 1, 0], [0.5, 0.5, 0.5, 0.5], positive_label=1)

    assert metrics.auroc == 0.5


def test_calibration_metrics_and_bins_are_computed():
    metrics = score_calibration([1, 0, 1, 0], [1.0, 0.0, 1.0, 0.0], positive_label=1)

    assert metrics.scored == 4
    assert metrics.brier_score == 0
    assert metrics.log_loss == pytest.approx(0, abs=1e-12)
    assert metrics.expected_calibration_error == 0
    assert metrics.maximum_calibration_error == 0
    assert sum(item.count for item in metrics.bins) == 4


def test_evaluation_record_never_accepts_an_unexplained_missing_prediction():
    with pytest.raises(ValueError, match="failure_code"):
        record("missing", 1, None, None)


def test_failed_records_are_excluded_from_ranking_even_if_the_backend_emitted_a_score():
    records = [
        record("unsafe", 1, True, 0.9),
        record("safe", 0, False, 0.1),
        record("failed", 1, None, 1.0, failure_code="timeout", decision=None),
    ]

    bundle = summarize_records(records)

    assert bundle.binary.failures == 1
    assert bundle.ranking.scored == 2


def test_summary_collects_operational_and_guardrail_metrics():
    records = [
        record(
            "unsafe",
            1,
            True,
            0.9,
            policy_ids=("INJ-01",),
            risk_category=RiskCategory.PROMPT_INJECTION,
            surface=Surface.INPUT,
            judge_invoked=True,
            latency_seconds=2,
            time_to_first_token_seconds=0.5,
            input_tokens=100,
            output_tokens=20,
            estimated_cost_usd=0.01,
            retries=1,
            gpu_peak_memory_mib=8000,
            gpu_seconds=2,
            first_detection_turn=2,
            dangerous_action_turn=3,
            slices={"scenario": "injection"},
            attack_succeeded=False,
            authorization_correct=True,
        ),
        record(
            "safe",
            0,
            False,
            0.1,
            rules_intervened=False,
            latency_seconds=1,
            input_tokens=50,
            output_tokens=10,
            estimated_cost_usd=0.005,
            slices={"scenario": "benign"},
        ),
    ]

    bundle = summarize_records(records, run_elapsed_seconds=6)

    assert bundle.binary.accuracy == 1
    assert bundle.ranking.auroc == 1
    assert bundle.operational.judge_invocations == 1
    assert bundle.operational.total_input_tokens == 150
    assert bundle.operational.total_output_tokens == 30
    assert bundle.operational.total_estimated_cost_usd == pytest.approx(0.015)
    assert bundle.operational.cost_per_true_positive_usd == pytest.approx(0.015)
    assert bundle.operational.latency_p50_seconds == 1.5
    assert bundle.operational.cases_per_minute == 20
    assert bundle.operational.pre_execution_detection_rate == 1
    assert bundle.operational.policy_counts == {"INJ-01": 1}
    assert bundle.annotated_outcomes.attack_success.observed == 1
    assert bundle.annotated_outcomes.attack_success.rate == 0
    assert bundle.annotated_outcomes.authorization_correctness.rate == 1
    assert bundle.annotated_outcomes.sanitization_correctness.rate is None
    assert set(score_slices(records, "scenario")) == {"benign", "injection"}


def test_summary_keeps_attack_attempt_and_attack_success_tasks_separate():
    records = [
        record(
            "successful-attack",
            1,
            True,
            0.9,
            attack_succeeded=True,
            attack_success_prediction=True,
            attack_success_risk_score=0.8,
        ),
        record(
            "unsuccessful-attack",
            1,
            True,
            0.8,
            attack_succeeded=False,
            attack_success_prediction=False,
            attack_success_risk_score=0.2,
        ),
        record(
            "benign",
            0,
            False,
            0.1,
            attack_succeeded=False,
            attack_success_prediction=False,
            attack_success_risk_score=0.1,
        ),
    ]

    bundle = summarize_records(records)

    assert bundle.attack_attempt.label_name == "benchmark_malicious_or_unsafe"
    assert bundle.attack_attempt.binary.recall == 1
    assert bundle.attack_success.available
    assert bundle.attack_success.eligible_records == 3
    assert bundle.attack_success.binary.recall == 1
    assert bundle.attack_success.ranking.auroc == 1
    assert bundle.attack_success_for_attempted_attacks.available
    assert bundle.attack_success_for_attempted_attacks.eligible_records == 2
    assert bundle.attack_success_for_attempted_attacks.binary.accuracy == 1


def test_attack_success_metrics_are_unavailable_without_outcome_annotations():
    bundle = summarize_records([record("cnfinbench", 1, True, 0.9)])

    assert bundle.attack_attempt.available
    assert not bundle.attack_success.available
    assert bundle.attack_success.unavailable_reason == "attack-success annotations are unavailable"
    assert not bundle.attack_success_for_attempted_attacks.available


def test_attack_success_metrics_retain_outcome_detector_failures():
    bundle = summarize_records(
        [
            record(
                "outcome-error",
                1,
                True,
                0.9,
                attack_succeeded=True,
                attack_success_prediction=None,
                attack_success_detector_error=True,
            )
        ]
    )

    assert bundle.attack_success.available
    assert bundle.attack_success.binary.completed == 0
    assert bundle.attack_success.binary.failures == 1
    assert bundle.attack_success.ranking.scored == 0


def test_paired_comparison_reports_agreement_disagreement_and_mcnemar():
    first = [
        record("a", 1, True, 0.9, policy_ids=("INJ-01",)),
        record("b", 1, False, 0.4),
        record("c", 0, False, 0.1),
        record("d", 0, False, 0.2),
    ]
    second = [
        record("a", 1, True, 0.8, policy_ids=("INJ-01",)),
        record("b", 1, True, 0.7, policy_ids=("INJ-01",)),
        record("c", 0, False, 0.2),
        record("d", 0, True, 0.6, policy_ids=("SAFE-01",)),
    ]

    comparison = compare_paired(first, second)

    assert comparison.matched == 4
    assert comparison.agreement_rate == 0.5
    assert comparison.first_only_detections == 0
    assert comparison.second_only_detections == 2
    assert comparison.first_correct_second_wrong == 1
    assert comparison.second_correct_first_wrong == 1
    assert comparison.mcnemar_exact_p_value == 1
    assert comparison.metric_deltas_second_minus_first["recall"] == 0.5


def test_bootstrap_confidence_intervals_are_reproducible_and_bounded():
    records = [
        record("a", 1, True, 0.9),
        record("b", 1, False, 0.4),
        record("c", 0, False, 0.1),
        record("d", 0, True, 0.6),
    ]

    first = bootstrap_confidence_intervals(records, iterations=200, seed=7)
    second = bootstrap_confidence_intervals(records, iterations=200, seed=7)

    assert first == second
    assert first["accuracy"].point == 0.5
    assert first["accuracy"].lower is not None
    assert first["accuracy"].upper is not None
    assert 0 <= first["accuracy"].lower <= first["accuracy"].upper <= 1
    assert first["auroc"].valid_resamples < 200


@pytest.mark.parametrize(
    ("labels", "scores", "positive_label"),
    [([0], [], 1), ([2], [0.5], 1), ([0], [float("nan")], 1), ([0], [1.1], 1), ([0], [0.5], 2)],
)
def test_invalid_ranking_inputs_are_rejected(labels, scores, positive_label):
    with pytest.raises(ValueError):
        score_ranking(labels, scores, positive_label=positive_label)
