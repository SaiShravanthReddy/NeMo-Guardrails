# NeMo integration points

This project pins NeMo Guardrails `0.24.1` from the surrounding editable fork.

| Surface | Hook used | Enforcement evidence |
| --- | --- | --- |
| Input | `LLMRails.check_async(..., rail_types=[RailType.INPUT])` and `financial check input` | Direct/NeMo equivalence tests |
| Output | `LLMRails.check_async(..., rail_types=[RailType.OUTPUT])` and `financial check output` | Sanitization/block tests |
| Retrieval | `rails.retrieval.flows: financial check retrieval` for the full LLMRails RAG lifecycle; `screen_retrieved_chunks` for an external retriever | Direct wrapper tests |
| Tool call | Native `rails.tool_output: tool call validation` for NeMo structural allowlist/schema validation; `GuardedTools.execute` for permissions, resource scope, confirmation, and policy checks before side effects | Tool tests prove denied tools do not execute |
| Tool result | Native `rails.tool_input: tool result validation` for call/result linkage; `GuardedTools.execute` screens returned content as untrusted before release | Injection and sanitization tests |

`check_async` exposes only input and output `RailType` values in this fork. Retrieval
rails run inside the full LLMRails generation/RAG lifecycle, so an application with
an external retriever must call `screen_retrieved_chunks`. Native tool rails validate
message structure and declared JSON schemas; they do not implement identity,
permission, confirmation, or semantic result policies. Those checks belong at the
actual tool boundary and are implemented by `GuardedTools`.

The offline demonstration exercises NeMo input rails and the application tool hook.
It does not claim that a static trace proves production attack prevention. Streaming
is unsupported because complete content is buffered before release.
