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

import json
from email.message import Message
from urllib.error import HTTPError

import pytest
from financial_guardrails import judge_backends
from financial_guardrails.judge_backends import (
    JudgeBackendSpec,
    OpenAICompatibleJudgeBackend,
    configured_judge_backend,
    load_judge_backend_registry,
)
from pydantic import SecretStr, ValidationError


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, _limit):
        return self.body


def test_shared_client_sends_bounded_chat_completion(monkeypatch):
    captured = {}
    metrics = []

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        body = {
            "choices": [{"message": {"content": '{"decision":"allow"}'}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20},
        }
        return FakeResponse(json.dumps(body).encode())

    monkeypatch.setattr(judge_backends, "urlopen", fake_urlopen)
    backend = OpenAICompatibleJudgeBackend(
        name="test",
        spec=JudgeBackendSpec(
            base_url="https://judge.example/v1",
            model="test-model",
            request_options={"max_tokens": 100},
            input_cost_per_million_usd=0.06,
            output_cost_per_million_usd=0.15,
        ),
        api_key=SecretStr("secret-value"),
        request_timeout_seconds=7,
        metrics_sink=metrics.append,
    )

    result = backend.complete("policy prompt")

    payload = json.loads(captured["request"].data)
    assert result == '{"decision":"allow"}'
    assert captured["request"].full_url == "https://judge.example/v1/chat/completions"
    assert captured["request"].headers["Authorization"] == "Bearer secret-value"
    assert payload == {
        "model": "test-model",
        "messages": [{"role": "user", "content": "policy prompt"}],
        "max_tokens": 100,
    }
    assert captured["timeout"] == 7
    assert len(metrics) == 1
    assert metrics[0].input_tokens == 100
    assert metrics[0].output_tokens == 20
    assert metrics[0].estimated_cost_usd == pytest.approx(0.000009)
    assert metrics[0].failure_code is None


@pytest.mark.parametrize("url", ["http://remote.example/v1", "file:///tmp/model", "not-a-url"])
def test_backend_rejects_unsafe_urls(url):
    with pytest.raises(ValidationError):
        JudgeBackendSpec(base_url=url, model="model")


def test_backend_options_cannot_replace_prompt_or_model():
    with pytest.raises(ValidationError, match="cannot replace"):
        JudgeBackendSpec(
            base_url="https://judge.example/v1",
            model="model",
            request_options={"messages": []},
        )


def test_local_loopback_does_not_require_a_key(monkeypatch):
    monkeypatch.delenv("NAVIGATOR_TOOLKIT_API_KEY", raising=False)

    backend = configured_judge_backend("hipergator")

    assert backend.spec.base_url == "http://127.0.0.1:8000/v1"
    assert backend.spec.revision == "4da05a8edb55c6046cce958586c33b61da07bb79"


def test_navigator_requires_credential(monkeypatch):
    monkeypatch.delenv("NAVIGATOR_TOOLKIT_API_KEY", raising=False)

    with pytest.raises(ValueError, match="NAVIGATOR_TOOLKIT_API_KEY"):
        configured_judge_backend("navigator")


def test_provider_error_does_not_expose_response_body(monkeypatch):
    metrics = []

    def fail(*_args, **_kwargs):
        raise HTTPError(
            "https://judge.example/v1/chat/completions",
            400,
            "request included sensitive-record-value",
            Message(),
            None,
        )

    monkeypatch.setattr(judge_backends, "urlopen", fail)
    backend = OpenAICompatibleJudgeBackend(
        name="test",
        spec=JudgeBackendSpec(base_url="https://judge.example/v1", model="test-model"),
        api_key=None,
        metrics_sink=metrics.append,
    )

    with pytest.raises(RuntimeError, match="judge backend request failed") as error:
        backend.complete("private benchmark content")
    assert "sensitive-record-value" not in str(error.value)
    assert metrics[0].failure_code == "request_failed"
    assert metrics[0].input_tokens is None


def test_backend_retries_transient_provider_failure(monkeypatch):
    metrics = []
    calls = 0

    def flaky_urlopen(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise HTTPError("https://judge.example/v1/chat/completions", 503, "unavailable", Message(), None)
        return FakeResponse(
            json.dumps(
                {
                    "choices": [{"message": {"content": '{"decision":"allow"}'}}],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 20},
                }
            ).encode()
        )

    monkeypatch.setattr(judge_backends, "urlopen", flaky_urlopen)
    monkeypatch.setattr(judge_backends.time, "sleep", lambda _seconds: None)
    backend = OpenAICompatibleJudgeBackend(
        name="test",
        spec=JudgeBackendSpec(base_url="https://judge.example/v1", model="test-model"),
        api_key=None,
        metrics_sink=metrics.append,
    )

    assert backend.complete("policy prompt") == '{"decision":"allow"}'
    assert calls == 2
    assert [metric.failure_code for metric in metrics] == ["request_failed", None]


def test_registry_rejects_unknown_fields(tmp_path):
    path = tmp_path / "backends.yml"
    path.write_text(
        "schema_version: '1.0'\nbackends:\n  test:\n    base_url: https://example.com/v1\n"
        "    model: model\n    unsupported: true\n"
    )

    with pytest.raises(ValidationError):
        load_judge_backend_registry(path)
