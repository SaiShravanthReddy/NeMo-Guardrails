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

"""Markdown reporting helpers for content-free evaluation artifacts."""

from __future__ import annotations

from collections.abc import Sequence

from financial_guardrails.evaluation import EvaluationTaskMetrics, MetricBundle


def render_evaluation_report(runs: Sequence[tuple[str, MetricBundle]]) -> str:
    """Render the protocol-defined, content-free tables for saved artifacts."""

    return "\n\n".join(
        (
            "# Open Lakera evaluation summary",
            _render_task_table("Attack-attempt detection", runs, "attack_attempt"),
            _render_task_table("Attack-success detection", runs, "attack_success"),
            _render_task_table(
                "Attack-success detection among attempted attacks",
                runs,
                "attack_success_for_attempted_attacks",
            ),
            _render_decision_action_table(runs),
            _render_operational_table(runs),
            "## Per-conversation latency\n\n" + render_latency_table(runs),
        )
    )


def render_latency_table(runs: Sequence[tuple[str, MetricBundle]]) -> str:
    """Render per-conversation latency percentiles for one or more runs."""

    lines = [
        "| Run | Conversations | p50 latency (s) | p95 latency (s) |",
        "| --- | ---: | ---: | ---: |",
    ]
    for name, metrics in runs:
        operational = metrics.operational
        lines.append(
            "| "
            f"{name} | {operational.total} | {_format_seconds(operational.latency_p50_seconds)} | "
            f"{_format_seconds(operational.latency_p95_seconds)} |"
        )
    return "\n".join(lines)


def _render_task_table(title: str, runs: Sequence[tuple[str, MetricBundle]], task_name: str) -> str:
    lines = [
        f"## {title}",
        "",
        "| Run | Eligible | Completed | Coverage | Precision | Recall | F1 | Balanced accuracy | FPR | Score coverage | AUROC | AUPRC |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, metrics in runs:
        task = getattr(metrics, task_name)
        lines.append(_task_row(name, task))
    return "\n".join(lines)


def _task_row(name: str, task: EvaluationTaskMetrics) -> str:
    if not task.available:
        return f"| {name} | {task.eligible_records} | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable |"
    binary = task.binary
    ranking = task.ranking
    assert binary is not None
    assert ranking is not None
    return (
        "| "
        + " | ".join(
            (
                name,
                str(task.eligible_records),
                str(binary.completed),
                _format_percent(binary.coverage),
                _format_percent(binary.precision),
                _format_percent(binary.recall),
                _format_percent(binary.f1),
                _format_percent(binary.balanced_accuracy),
                _format_percent(binary.false_positive_rate),
                _format_percent(task.risk_score_coverage.coverage),
                _format_percent(ranking.auroc),
                _format_percent(ranking.auprc),
            )
        )
        + " |"
    )


def _render_operational_table(runs: Sequence[tuple[str, MetricBundle]]) -> str:
    lines = [
        "## Operational reliability",
        "",
        "| Run | Detector errors | Judge conversations | Logical judge attempts | Observed backend calls | Judge repairs | Exact attempt/call match | Estimated cost (USD) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |",
    ]
    for name, metrics in runs:
        operational = metrics.operational
        lines.append(
            "| "
            f"{name} | {operational.detector_errors} | {operational.judge_invocations} | "
            f"{operational.judge_attempts} | {operational.judge_backend_calls} | "
            f"{operational.judge_repair_attempts} | {operational.judge_backend_call_telemetry_matches} | "
            f"{operational.total_estimated_cost_usd:.6f} |"
        )
    return "\n".join(lines)


def _render_decision_action_table(runs: Sequence[tuple[str, MetricBundle]]) -> str:
    """Show confirmation burden separately from automatic intervention."""
    lines = [
        "## Decision actions and confirmation burden",
        "",
        "| Run | Allow | Block | Sanitize | Automatic intervention | Require confirmation | Log only |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, metrics in runs:
        counts = metrics.operational.decision_counts
        total = metrics.operational.total
        automatic = counts.get("block", 0) + counts.get("sanitize", 0)
        lines.append(
            "| "
            f"{name} | {_format_count_rate(counts.get('allow', 0), total)} | "
            f"{_format_count_rate(counts.get('block', 0), total)} | "
            f"{_format_count_rate(counts.get('sanitize', 0), total)} | "
            f"{_format_count_rate(automatic, total)} | "
            f"{_format_count_rate(counts.get('require_confirmation', 0), total)} | "
            f"{_format_count_rate(counts.get('log_only', 0), total)} |"
        )
    return "\n".join(lines)


def _format_seconds(value: float | None) -> str:
    return "unavailable" if value is None else f"{value:.3f}"


def _format_percent(value: float | None) -> str:
    return "unavailable" if value is None else f"{value * 100:.1f}%"


def _format_count_rate(count: int, total: int) -> str:
    return f"{count} ({count / total * 100:.1f}%)" if total else "0 (unavailable)"
