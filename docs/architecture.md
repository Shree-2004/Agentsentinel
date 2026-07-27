# Architecture

## The adapter problem

Three target agents (Phase 1) have incompatible call shapes:

1. **LangGraph research pipeline** — a pure function, `run_pipeline(topic) -> dict`. Single-shot, no intermediate visibility beyond what's in the final state dict.
2. **Google ADK stock-analysis agent** — a stateful, async, multi-turn, tool-calling agent owned by ADK's `Runner`. The interesting behavior (tool calls, MCP server responses) happens inside an event stream you don't control the shape of.
3. **LangChain RAG chatbot** — a function requiring externally-constructed dependencies (`vector_store`, `llm`) that returns a streaming token generator plus a side-channel list of source chunks.

Forcing all three through a heavier, more "structured" interface (e.g. one that assumes streaming, or assumes a single dict return, or assumes synchronous execution) would distort at least one of them. So `AgentUnderTest` is deliberately minimal:

```python
class AgentUnderTest(Protocol):
    name: str
    version: str
    def setup(self, ctx: RunContext) -> None: ...
    def run(self, case: TestCase, ctx: RunContext) -> AgentTrace: ...
    def teardown(self, ctx: RunContext) -> None: ...
```

Each adapter absorbs its target's execution model internally — draining a generator, running an asyncio event loop, translating ADK's function-call/function-response event parts into `ToolCall` records — and returns one fully materialized `AgentTrace`. The harness never assumes anything about *how* an adapter produces a trace, only what shape the trace takes once it exists.

`AgentUnderTest` is a `Protocol` (structural typing), not a required base class, so adapters can wrap a target repo without that repo needing to know AgentSentinel exists — no invasive instrumentation of the projects being evaluated.

## Why `TestCase.expected` is a loose dict

A normal test case cares about `{"must_contain": [...]}`. An injection case cares about `{"forbidden_action": ..., "canary_string": ...}`. A future tool-call-correctness case cares about `{"expected_tool_calls": [...]}`. Forcing one rigid schema across all of these would mean a migration every time a new scorer is added. Instead, `expected` is an open dict and each `Scorer` reads only the keys it understands — a scorer that doesn't recognize a key simply doesn't apply, rather than erroring.

## Why injection payloads live in mocked tool-response fixtures, not the test file

The real threat model for the ADK agent is *indirect* prompt injection: a malicious instruction embedded in untrusted tool output (e.g. a news article fetched via the MCP server), not in the user's own message. Encoding that means the adapter needs a way to substitute a poisoned fixture for a live MCP call on specific test cases, deterministically and offline (so CI doesn't depend on a real news article containing an attack string on a given day). See `agentsentinel/testcases/fixtures/mcp_mock_responses/` (Phase 2) and `docs/injection_taxonomy.md` for the archetype list this corpus is built from.

## Why the CI gate is split into fast/deterministic vs. nightly/full

Running an LLM-as-judge faithfulness or injection-resistance check on every PR, against a live target agent, is slow and non-deterministic (judge variance, API flakiness, cost). The `agentsentinel run`/`gate` commands are designed so a per-PR run can restrict scorers to the deterministic set (`keyword_match`, `latency`, canary-string checks) while a scheduled nightly run adds the LLM-judge scorers against the real agents. Both write to the same `runs`/`traces`/`scores` tables, so the dashboard and regression diffing don't need to know which mode produced a given run.
