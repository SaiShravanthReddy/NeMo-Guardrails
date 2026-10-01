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
from financial_guardrails.evaluation import score_binary


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
