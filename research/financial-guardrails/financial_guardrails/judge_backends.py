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

"""OpenAI-compatible policy-judge backends with bounded, secret-safe I/O."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

DEFAULT_BACKEND_CONFIG_PATH = Path(__file__).resolve().parents[1] / "models" / "judge_backends.yml"
MAX_RESPONSE_BYTES = 1024 * 1024


class JudgeBackendSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    base_url: str
    model: str = Field(min_length=1)
    revision: str | None = None
    api_key_env: str | None = None
    request_options: dict[str, Any] = Field(default_factory=dict)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        parsed = urlparse(value)
        local_hosts = {"127.0.0.1", "localhost", "::1"}
        if parsed.scheme == "https" and parsed.hostname:
            return value.rstrip("/")
        if parsed.scheme == "http" and parsed.hostname in local_hosts:
            return value.rstrip("/")
        raise ValueError("base_url must use HTTPS or local loopback HTTP")

    @field_validator("request_options")
    @classmethod
    def reject_reserved_request_options(cls, value: dict[str, Any]) -> dict[str, Any]:
        reserved = {"model", "messages"}.intersection(value)
        if reserved:
            raise ValueError("request_options cannot replace model or messages")
        return value


class JudgeBackendRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str
    backends: dict[str, JudgeBackendSpec]


class OpenAICompatibleJudgeBackend:
    """Minimal chat-completions client shared by Navigator and local vLLM."""

    def __init__(
        self,
        *,
        name: str,
        spec: JudgeBackendSpec,
        api_key: SecretStr | None,
        request_timeout_seconds: float = 120,
    ):
        self.name = name
        self.spec = spec
        self._api_key = api_key
        self.request_timeout_seconds = request_timeout_seconds

    def complete(self, prompt: str) -> str:
        payload = {
            "model": self.spec.model,
            "messages": [{"role": "user", "content": prompt}],
            **self.spec.request_options,
        }
        headers = {"Content-Type": "application/json"}
        if self._api_key is not None:
            headers["Authorization"] = f"Bearer {self._api_key.get_secret_value()}"
        request = Request(
            f"{self.spec.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.request_timeout_seconds) as response:  # noqa: S310
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise RuntimeError("judge backend request failed") from exc
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ValueError("judge backend response exceeded the size limit")
        try:
            body = json.loads(raw)
            content = body["choices"][0]["message"]["content"]
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise ValueError("judge backend returned an invalid chat-completions response") from exc
        if not isinstance(content, str) or not content.strip():
            raise ValueError("judge backend returned empty content")
        return content


def load_judge_backend_registry(
    path: str | Path = DEFAULT_BACKEND_CONFIG_PATH,
) -> JudgeBackendRegistry:
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError("judge backend configuration could not be loaded") from exc
    return JudgeBackendRegistry.model_validate(raw)


def configured_judge_backend(
    backend_name: str,
    *,
    path: str | Path = DEFAULT_BACKEND_CONFIG_PATH,
    request_timeout_seconds: float = 120,
) -> OpenAICompatibleJudgeBackend:
    registry = load_judge_backend_registry(path)
    try:
        spec = registry.backends[backend_name]
    except KeyError as exc:
        raise ValueError(f"unknown judge backend: {backend_name}") from exc
    api_key = None
    if spec.api_key_env:
        value = os.environ.get(spec.api_key_env)
        if not value:
            raise ValueError(f"required credential environment variable is missing: {spec.api_key_env}")
        api_key = SecretStr(value)
    return OpenAICompatibleJudgeBackend(
        name=f"{backend_name}:{spec.model}",
        spec=spec,
        api_key=api_key,
        request_timeout_seconds=request_timeout_seconds,
    )
