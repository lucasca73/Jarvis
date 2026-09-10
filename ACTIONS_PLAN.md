# Local actions and LLM tool calling plan

Planning draft updated 2026-09-10. No action executor or cloud provider is
implemented by this document. The current Jarvis runtime remains local Ollama
plus the existing voice pipeline.

## Goal

Allow Jarvis to complete useful computer tasks while keeping the model behind a
small, reviewable capability boundary. The model proposes a named tool and typed
arguments; Jarvis validates the proposal, applies a permission policy, executes
approved code locally, and returns a structured result. The model never receives
direct shell, filesystem, or GUI access.

```text
STT → model → tool call → policy gate → local executor → result → model → TTS
```

## First local tools

Start with a short allowlist and explicit contracts rather than a general shell
bridge.

| Tool | Initial behavior | Risk policy |
| --- | --- | --- |
| `open_application(name)` | Open a fixed set of installed macOS apps | Confirmation initially; allowlist required |
| `set_volume(level)` | Set system volume with `level` bounded to 0–100 | Confirmation initially; reversible |
| `find_files(root, pattern)` | Read-only search under approved roots with result limits | Auto-execute for approved roots |
| `get_system_status()` | Read-only, bounded status such as battery or current time | Auto-execute |

Shell commands, file writes/deletes, browser automation, messages, purchases,
and network requests stay out of the first tool set. Destructive or externally
visible effects must require confirmation immediately before execution.

## Contracts and policy

Introduce provider-independent types for `ToolDefinition`, `ToolCall`,
`ToolResult`, `ActionPolicy`, and `ActionExecutor`. Tool arguments use strict
JSON schemas; unknown tools and invalid arguments are rejected before execution.
Executors enforce approved paths, timeouts, cancellation, bounded output, and
deterministic error categories. Prompts, arguments, and results remain in memory
and must not be written to logs or telemetry.

The policy has three levels: safe read-only operations may run automatically;
reversible local changes require confirmation until explicitly enabled; and
destructive, irreversible, or externally visible operations always require
confirmation. The UI should expose a `Working` state while an approved action
runs and a content-free confirmation dialog for higher-risk actions. A tool
failure returns a structured error and must not crash the voice loop or silently
retry a side effect.

## Provider boundary

Keep `LanguageModel` independent of any provider. Add a separate tool-capable
contract or an optional `respond_with_tools` method so the current Ollama
adapter continues to work without tools. Ollama remains the default local
provider; its existing history and privacy behavior stay unchanged.

An optional OpenAI adapter can use the [Responses API text interface](https://developers.openai.com/api/docs/guides/text)
and [function calling](https://developers.openai.com/api/docs/guides/function-calling).
The [GPT-6 Astra model page](https://developers.openai.com/api/docs/models/gpt-6-astra)
lists function calling and computer-use tools as supported capabilities. This
would be an explicit provider choice, never an automatic fallback. The API key
must come from the user's environment or Keychain and must never be bundled in
`Jarvis.app`.

Cloud inference changes the current local-only boundary: prompts, tool calls,
and possibly tool results leave the computer. Use `store=false` for an OpenAI
Responses request, but review the [OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data)
because this does not mean zero retention. The user must explicitly opt in.

Computer-use models that consume screenshots and return mouse/keyboard actions
are a later, higher-risk capability. Begin with narrow local tools and add visual
control only after a separate privacy and safety review.

## Implementation order

- [ ] ACTION.1 Define tool-call/result schemas and the provider-independent model contract.
- [ ] ACTION.2 Implement the four local executors with path, argument, timeout, and output bounds.
- [ ] ACTION.3 Add policy evaluation, confirmation, cancellation, and content-free `Working`/failure events.
- [ ] ACTION.4 Add a mocked tool-calling provider and, only after local tests, an explicitly configured OpenAI adapter.
- [ ] ACTION.5 Test unknown tools, invalid schemas, policy rejection, timeout/cancellation, failures, repeated calls, and log privacy.
- [ ] ACTION.6 Perform a manual privacy review before enabling any cloud provider or computer-use capability.

Completion requires an approved local tool call to return a bounded structured
result, recover from failure, and leave the normal voice loop usable. No
implementation milestone is complete yet.
