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

"""Evaluation primitives that keep failures separate from classification errors."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field


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


def _ratio(numerator: int, denominator: int) -> float | None:
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
    )
