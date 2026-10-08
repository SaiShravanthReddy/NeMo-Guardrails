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

from financial_guardrails.evaluation import MetricBundle


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


def _format_seconds(value: float | None) -> str:
    return "unavailable" if value is None else f"{value:.3f}"
