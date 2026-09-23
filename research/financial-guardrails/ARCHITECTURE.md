# Open Lakera architecture

The versioned policy is `policies/open_lakera_v1.yml`. `SecurityEvent` identifies
the interaction surface, source role, trust level, actor, permissions, resource
scope, tool data, and trusted confirmation identifiers. Retrieved content and tool
results are structurally required to be untrusted.

`PolicyEngine` invokes every configured detector and aggregates results with this
precedence:

```text
block > require_confirmation > sanitize > log_only > allow
```

In enforce mode the aggregate action is applied. In detect mode a finding becomes
`log_only`, the original content is preserved, and the recommended enforcement
decision remains in the verdict. Audit records omit content, arguments, matched
text, and secrets.

Each verdict contains the policy and schema versions, mode, applied and recommended
decisions, policy IDs, risk category, redacted evidence, explanation, per-detector
status, explicit detector-error flag, and resulting content. A detector exception,
timeout, malformed output, or unknown label is converted into a detector failure.
The machine policy maps failures to `block` for tool calls and
`require_confirmation` for ordinary surfaces.

The same engine is called directly by retrieval/tool wrappers and by the NeMo
custom action. Authentication and confirmation identifiers must be supplied by
trusted host code. They are never inferred from user text, retrieved text, model
output, or tool results.

The optional model layer is disabled by default. It lazily loads pinned local files,
refuses hosted inference, applies a bounded timeout, and rejects malformed labels.
The rules-only profile remains the reproducible CPU baseline.
