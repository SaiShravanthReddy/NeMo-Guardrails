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

import time

from financial_guardrails.local_models import LocalClassification, LocalModelDetector
from financial_guardrails.schema import Decision, SecurityEvent, SourceRole, Surface, TrustLevel


def event():
    return SecurityEvent(
        event_id="model-test",
        surface=Surface.INPUT,
        source_role=SourceRole.USER,
        trust=TrustLevel.USER_INTENT,
        content="test",
    )


class FakeBackend:
    name = "fake"

    def __init__(self, result):
        self.result = result

    def classify(self, event):
        return self.result


def test_local_model_maps_unsafe_to_block():
    detector = LocalModelDetector(FakeBackend(LocalClassification("unsafe", ("violent",))))

    assert detector.detect(event()).decision is Decision.BLOCK


def test_local_model_maps_controversial_to_confirmation():
    detector = LocalModelDetector(FakeBackend(LocalClassification("controversial")))

    assert detector.detect(event()).decision is Decision.REQUIRE_CONFIRMATION


def test_local_model_rejects_malformed_output():
    detector = LocalModelDetector(FakeBackend({"label": "safe"}))

    try:
        detector.detect(event())
    except ValueError as exc:
        assert "malformed" in str(exc)
    else:
        raise AssertionError("malformed model output was accepted")


class SlowBackend:
    name = "slow"

    def classify(self, event):
        time.sleep(0.05)
        return LocalClassification("safe")


def test_local_model_timeout_is_explicit():
    detector = LocalModelDetector(SlowBackend(), timeout_seconds=0.001)

    try:
        detector.detect(event())
    except TimeoutError as exc:
        assert "timed out" in str(exc)
    else:
        raise AssertionError("model timeout was accepted")
