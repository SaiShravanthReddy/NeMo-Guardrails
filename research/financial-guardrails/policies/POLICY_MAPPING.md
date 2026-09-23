# Policy mapping

This configuration is an independent implementation based on the behavior described
in Lakera's public documentation. It does not reproduce Lakera's models, training
data, rules, thresholds, or performance.

Sources were reviewed on 2026-09-22:

- [Defenses](https://docs.lakera.ai/docs/defenses)
- [Prompt defense](https://docs.lakera.ai/docs/prompt-defense)
- [Data leakage prevention](https://docs.lakera.ai/docs/data-leakage-prevention)
- [Agent behavior defense](https://docs.lakera.ai/docs/agent-behavior-defense)

| ID | Source category | Local behavior | Surface | Action | Known gap |
| --- | --- | --- | --- | --- | --- |
| INJ-01 | Prompt defense | Detect direct attempts to override trusted instructions or reveal a hidden prompt | Input and untrusted tool results | Block | Rules cover explicit English and Chinese phrases; obfuscation and indirect attacks require a model detector |
| DLP-01 | Data leakage prevention | Detect Luhn-valid payment card numbers and email addresses | Input, tool results, output | Block cards; redact email addresses | This is not a general PII recognizer; authorization-aware PII policy remains application work |
| DLP-02 | Data leakage prevention | Detect private-key headers and configured protected values, including percent-encoded values | Input, tool results, output | Block | Paraphrases, fragments, and encryption are outside this rules-only version |
| URL-01 | Content moderation / agent behavior | Restrict output URLs to exact configured HTTPS hosts | Output and tool results | Block | An allowlist is not reputation or malware analysis; redirects must be checked by the fetcher |
| TOOL-01 | Agent behavior defense | Bind a read-only tool call to a trusted principal, permission, and account identifier | Tool boundary | Deny before execution | The host application must provide authenticated principal state |
| FIN-01 | Project extension | Detect explicit requests for laundering, AML/KYC evasion, or document forgery | Input and output | Block | Narrow rules are intentional and are not a complete financial-abuse classifier |
| LIMIT-01 | Implementation control | Reject empty or oversized messages before expensive processing | Input and output | Error for empty; block oversized | Character length is not a tokenizer or context-window estimate |

The default profile makes no model or provider calls. A check failure, skipped action,
invalid result, or disagreement between the custom classifier and NeMo rail outcome
raises `GuardUnavailable`; callers must withhold content and side effects.

## Deferred defenses

- Semantic injection and jailbreak models, calibrated on held-out multilingual data.
- Broad harmful-content moderation and application-specific financial suitability rules.
- Chinese PII recognition beyond the explicit rules above.
- URL reputation, redirect resolution, file scanning, and multimodal checks.
- Streaming checks. This version buffers a complete message before release.

These additions require representative fixtures and measurements. They should not be
enabled merely because a detector produces a score.
