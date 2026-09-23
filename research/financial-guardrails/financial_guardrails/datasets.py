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

"""Dataset intake utilities; raw records are never committed or logged."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field


class BenchmarkCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    case_id: str
    messages: tuple[dict[str, Any], ...]
    metadata: dict[str, Any] = Field(default_factory=dict)


class DatasetAdapter(Protocol):
    name: str
    version: str

    def cases(self) -> Iterable[BenchmarkCase]: ...


class DatasetManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    filename: str
    sha256: str
    byte_size: int
    format: str
    record_count: int
    top_level_keys: tuple[str, ...]


def inspect_json_dataset(path: str | Path) -> DatasetManifest:
    source = Path(path)
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    records = list(_iter_records(source))
    keys = sorted({key for record in records if isinstance(record, dict) for key in record})
    return DatasetManifest(
        filename=source.name,
        sha256=digest.hexdigest(),
        byte_size=source.stat().st_size,
        format="jsonl" if source.suffix.lower() == ".jsonl" else "json",
        record_count=len(records),
        top_level_keys=tuple(keys),
    )


def _iter_records(path: Path) -> Iterator[Any]:
    if path.suffix.lower() == ".jsonl":
        with path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if line.strip():
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise ValueError(f"invalid JSONL at line {line_number}") from exc
        return
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("invalid JSON dataset") from exc
    if not isinstance(value, list):
        raise ValueError("JSON benchmark input must be a list of records")
    yield from value
