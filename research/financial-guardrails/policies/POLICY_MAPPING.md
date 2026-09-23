# Open Lakera coverage and gaps

This is an independent implementation of behaviors described in Lakera's public
documentation. It does not reproduce Lakera's proprietary models, threat feeds,
training data, thresholds, or measured performance.

Sources reviewed: [Defenses](https://docs.lakera.ai/docs/defenses),
[Prompt Defense](https://docs.lakera.ai/docs/prompt-defense),
[Data Leakage Prevention](https://docs.lakera.ai/docs/data-leakage-prevention), and
[Agent Behavior Defense](https://docs.lakera.ai/docs/agent-behavior-defense).

| Public defense area | Open Lakera behavior | Status | Verification | Gap |
| --- | --- | --- | --- | --- |
| Prompt Defense: direct injection | Anchored English/Chinese rules plus optional pinned DeBERTa classifier | Approximated | `test_ne_mo_rail_outcomes`, `test_direct_engine_and_ne_mo_agree` | Rules are bypassable; optional model needs calibration |
| Prompt Defense: jailbreaks | Explicit role-change and safeguard-bypass rules; optional Qwen3Guard | Approximated | `test_explicit_harmful_requests_are_blocked` | No adaptive-red-team performance claim |
| Prompt Defense: indirect injection | Retrieved chunks and tool results are always untrusted and screened | Implemented for configured hooks | `test_indirect_injection_is_role_aware`, `test_indirect_injection_in_retrieval_is_blocked`, `test_malicious_tool_result_is_not_released` | Host application must use the retrieval/tool wrappers |
| Content Moderation | Explicit fraud, malware, violence, and self-harm assistance rules; optional Qwen3Guard categories | Approximated | `test_explicit_harmful_requests_are_blocked`, benign counterexamples in `test_defense_areas.py` | Rules do not provide broad semantic coverage |
| Data Leakage Prevention: PII | Email sanitization; optional future span model | Partial | `test_enforce_mode_sanitizes_email`, retrieval and tool-result tests | No general names, addresses, national IDs, or Chinese PII model yet |
| Data Leakage Prevention: credentials | Private-key headers, credential assignments, and configured protected values | Approximated | `test_output_leakage_is_blocked`, `test_detector_failure_never_allows_ordinary_event` | Encoded, fragmented, and paraphrased leakage can evade rules |
| Data Leakage Prevention: financial data | Luhn-valid cards and labeled account/routing numbers | Approximated | `test_luhn_valid_cards`, `test_output_leakage_is_blocked` | Authorization-aware field taxonomy is application-specific |
| System instruction leakage | Explicit system/developer-instruction disclosure markers and protected canaries | Approximated | `test_output_leakage_is_blocked` | Semantic paraphrases require a calibrated model |
| Malicious Links | URL extraction, IDNA normalization, exact HTTPS allowlist/denylist, credential/port/private-IP checks | Approximated | URL cases in `test_policy.py` and `test_defense_areas.py` | No proprietary reputation, redirect, DNS, or malware intelligence |
| Agent Behavior: tool allow/deny | Machine policy allowlist, denylist, permission and exact argument checks | Implemented at application boundary | `test_unauthorized_account_never_executes_tool`, `test_destructive_tool_is_denied_before_execution` | Every host tool must be registered through `GuardedTools` |
| Agent Behavior: data transfer | Export permission and trusted confirmation for configured external destinations | Implemented policy control | tool policy tests | Destination ownership and downstream effects remain host responsibilities |
| Agent Behavior: privilege/destructive action | Denied tool categories execute zero side effects | Implemented for configured names | `test_destructive_tool_is_denied_before_execution` | Policy must list every application tool |
| Agent Behavior: financial transaction | Permission, account scope, argument schema, and trusted confirmation | Implemented baseline | `test_legitimate_transfer_requires_then_accepts_trusted_confirmation` | Business limits, fraud scoring, and settlement state remain application controls |
| Detect mode | Returns `log_only`, preserves content, records metadata without raw text | Implemented | `test_detect_mode_records_without_raw_content` | Production sink, retention, and access controls are deployment work |
| Enforce mode | Deterministic block, sanitize, confirmation, and allow precedence | Implemented | `test_engine.py` | Threshold calibration is pending benchmark data |

## Unsupported claims

- Commercial Lakera equivalence, accuracy, latency, or attack-prevention rates.
- Proprietary URL reputation and threat intelligence.
- Multimodal, streaming-prefix, or file-content scanning.
- A semantic model deciding authorization. Authorization comes from authenticated
  application state; model or tool-result text cannot grant permission.
- CNFinBench or FinVault performance until the supplied datasets are integrated and run.
