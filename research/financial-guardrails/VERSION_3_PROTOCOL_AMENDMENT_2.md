# Version 3 Protocol Amendment 2

## Status

**Clarification before static Version 3 evaluation.** On 2026-10-29, the
project team clarified that FinVault and CNFinBench are hypothetical benchmark
traces and that the guardrail must not receive dataset labels. This amendment
does not alter the frozen Version 1 results.

## Static benchmark contract

For static FinVault and CNFinBench replay, Version 3 receives only the ordered,
cleaned conversation trace. It does not receive `attack_success`, `outcome`,
`final_status`, case labels, review annotations, or application authorization
and execution facts.

The Version 3 judge may use prior conversation turns as untrusted context for
task relevance and threat assessment. No trace event, including a tool result
or recorded tool call, can grant application authorization or prove execution.

Dataset annotations remain evaluator-only:

- attack-attempt labels score intervention and threat assessment after
  inference;
- attack-success labels score the independent outcome monitor after inference.

Consequently, static outcome results are trace-based predictions of observed
harm, not verified application execution claims.

## Production integration remains optional

The trusted authorization and execution interfaces remain available only when
a real application supplies independent application-side facts. They are not
required, generated, or substituted with FinVault/CNFinBench labels for static
benchmark replay.

## Evaluation sequence

Validate the conversation-only static path locally, run a small representative
HPG gate, then run grouped cross-validation using the existing reviewed-group
exclusion. Report this as non-final development evidence under Amendment 1
unless a new independent holdout is registered before inference.
