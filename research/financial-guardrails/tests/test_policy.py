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
from financial_guardrails.configuration import LinkConfig, load_policy
from financial_guardrails.detectors import is_payment_card, unsafe_urls
from pydantic import ValidationError


@pytest.mark.parametrize("value", ["4111 1111 1111 1111", "5555555555554444"])
def test_luhn_valid_cards(value):
    assert is_payment_card(value)


@pytest.mark.parametrize("value", ["4111 1111 1111 1112", "1111111111111111", "1234"])
def test_non_cards_do_not_match(value):
    assert not is_payment_card(value)


@pytest.mark.parametrize(
    "url",
    [
        "http://sec.gov",
        "https://user@sec.gov",
        "https://sec.gov:444/report",
        "javascript:alert(1)",
        "//sec.gov/report",
    ],
)
def test_unsafe_url_forms_are_restricted(url):
    assert unsafe_urls(url, ["sec.gov"], [])


def test_exact_https_host_is_allowed():
    assert not unsafe_urls("https://sec.gov/report", ["sec.gov"], [])


def test_missing_policy_file_is_explicit_failure(tmp_path):
    with pytest.raises(ValueError, match="could not be loaded"):
        load_policy(tmp_path / "missing.yml")


def test_unknown_link_configuration_field_is_rejected():
    with pytest.raises(ValidationError):
        LinkConfig.model_validate({"allowed_hosts": [], "denied_hosts": [], "wildcard": "*"})
