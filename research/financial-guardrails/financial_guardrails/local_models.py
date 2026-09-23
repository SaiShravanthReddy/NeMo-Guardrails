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

"""Optional local-only classifier adapters. Imports are lazy and never call hosted inference."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from importlib import import_module
from typing import Protocol

from financial_guardrails.schema import Decision, DetectorResult, Evidence, RiskCategory, SecurityEvent


@dataclass(frozen=True)
class LocalClassification:
    label: str
    categories: tuple[str, ...] = ()
    score: float | None = None


class LocalBackend(Protocol):
    name: str

    def classify(self, event: SecurityEvent) -> LocalClassification: ...


class LocalModelDetector:
    def __init__(self, backend: LocalBackend, timeout_seconds: float = 30):
        self.backend = backend
        self.name = backend.name
        self.timeout_seconds = timeout_seconds
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"{self.name}-worker")

    def detect(self, event: SecurityEvent) -> DetectorResult:
        future = self._executor.submit(self.backend.classify, event)
        try:
            classification = future.result(timeout=self.timeout_seconds)
        except FutureTimeout as exc:
            future.cancel()
            raise TimeoutError(f"{self.name} timed out") from exc
        if not isinstance(classification, LocalClassification):
            raise ValueError("local classifier returned malformed output")
        label = classification.label.lower()
        if label in {"safe", "benign", "no_injection"}:
            return DetectorResult(detector=self.name)
        if label == "controversial":
            decision = Decision.REQUIRE_CONFIRMATION
        elif label in {"unsafe", "injection"}:
            decision = Decision.BLOCK
        else:
            raise ValueError("local classifier returned an unknown label")
        category = (
            RiskCategory.PROMPT_INJECTION
            if "injection" in classification.categories or label == "injection"
            else RiskCategory.HARMFUL_CONTENT
        )
        return DetectorResult(
            detector=self.name,
            decision=decision,
            policy_ids=("MODEL-LOCAL",),
            risk_category=category,
            evidence=(
                Evidence(
                    detector=self.name,
                    rule_id="MODEL-LOCAL",
                    summary=f"local model label={label}; categories={','.join(classification.categories) or 'none'}",
                ),
            ),
            explanation="An optional local classifier identified a security risk.",
        )


class DebertaInjectionBackend:
    name = "deberta_prompt_injection"

    def __init__(self, model_id: str, revision: str, device: int = -1):
        try:
            transformers = import_module("transformers")
        except ImportError as exc:
            raise RuntimeError("install the local-models extra to use this backend") from exc
        tokenizer = transformers.AutoTokenizer.from_pretrained(model_id, revision=revision, local_files_only=True)
        model = transformers.AutoModelForSequenceClassification.from_pretrained(
            model_id, revision=revision, local_files_only=True
        )
        self.pipeline = transformers.pipeline(
            "text-classification",
            model=model,
            tokenizer=tokenizer,
            device=device,
        )

    def classify(self, event: SecurityEvent) -> LocalClassification:
        output = self.pipeline(event.content, truncation=True)[0]
        label = str(output.get("label", "")).lower()
        mapped = (
            "injection"
            if label in {"1", "label_1", "injection"}
            else "safe"
            if label in {"0", "label_0", "safe"}
            else label
        )
        return LocalClassification(mapped, ("injection",) if mapped == "injection" else (), float(output["score"]))


class QwenGuardBackend:
    name = "qwen3guard_content_safety"
    LABEL = re.compile(r"Safety:\s*(Safe|Unsafe|Controversial)", re.IGNORECASE)
    CATEGORY = re.compile(
        r"Violent|Non-violent Illegal Acts|Sexual Content or Sexual Acts|PII|Suicide & Self-Harm|"
        r"Unethical Acts|Politically Sensitive Topics|Copyright Violation|Jailbreak",
        re.IGNORECASE,
    )

    def __init__(self, model_id: str, revision: str, device: str = "auto"):
        try:
            transformers = import_module("transformers")
            AutoModelForCausalLM = transformers.AutoModelForCausalLM
            AutoTokenizer = transformers.AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("install the local-models extra to use this backend") from exc
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision, local_files_only=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id,
            revision=revision,
            device_map=device,
            local_files_only=True,
        ).eval()

    def classify(self, event: SecurityEvent) -> LocalClassification:
        role = "assistant" if event.surface.value == "output" else "user"
        prompt = self.tokenizer.apply_chat_template([{"role": role, "content": event.content}], tokenize=False)
        inputs = self.tokenizer([prompt], return_tensors="pt").to(self.model.device)
        output = self.model.generate(**inputs, max_new_tokens=96, do_sample=False)
        generated = self.tokenizer.decode(output[0][inputs["input_ids"].shape[-1] :], skip_special_tokens=True)
        match = self.LABEL.search(generated)
        if not match:
            raise ValueError("Qwen3Guard output did not contain a safety label")
        categories = tuple(dict.fromkeys(item.lower() for item in self.CATEGORY.findall(generated)))
        return LocalClassification(match.group(1).lower(), categories)
