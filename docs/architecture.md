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

## Why real adapters run their target in a subprocess, not in-process

The original Phase 1 plan was `sys.path` injection into AgentSentinel's own interpreter — simple, and fine in principle. It broke on contact with real dependencies: the LangGraph research repo pins `langchain==0.2.16`; the RAG chatbot repo pins `langchain==0.3.7`. That's a real major-version conflict, not a pinning oversight — installing both into one shared venv silently upgrades/downgrades one of them and breaks whichever adapter isn't currently being tested. A harness that can only evaluate agents whose dependencies happen to be mutually compatible isn't actually general-purpose.

So each real adapter (`langgraph_research.py`, `rag_chatbot.py`) subclasses `SubprocessAgentAdapter` instead of importing its target directly:

- The target keeps (or gets, via `adapters/venv_utils.py::ensure_venv`) its **own venv**, completely isolated from AgentSentinel's own dependencies and from every other adapter's target.
- A small shim script per adapter (`adapters/shims/*.py`) is executed **under the target's interpreter**. Shims have zero import dependency on the `agentsentinel` package itself — that venv never has it installed — only stdlib plus whatever the target repo provides.
- Protocol: the parent process writes `{"input_text": ..., "multi_turn": ...}` as JSON to the shim's stdin; the shim prints exactly one line prefixed `AGENTSENTINEL_RESULT:` containing the trace JSON (or `{"error": ...}`) as the *last* line of stdout. Wrapped agents print their own progress freely (all three target repos in this portfolio do, with emoji/unicode arrows) — only the sentinel-prefixed line is parsed, so agent chatter never corrupts the protocol.
- Windows detail: piped stdout defaults to the console codepage (cp1252), not UTF-8, and multiple target repos crash on their own `print("→ ...")` debug lines under that codepage. Both the CLI's own stdout (`cli/__main__.py`) and the subprocess child env (`PYTHONIOENCODING=utf-8` in `subprocess_base.py`) force UTF-8 explicitly — this is a real, generalizable failure mode wrapping *anyone's* third-party agent on Windows, not a one-off.

Known limitation: a subprocess is spawned fresh per test case, so **multi-turn conversation memory isn't threaded through** for adapters that would need it (the RAG chatbot's `chat_history` param is always empty here). Supporting it would mean a long-lived shim process communicating over a persistent pipe rather than one process per call — left for a future phase since the current seed corpus is single-turn only.

## Why `TestCase.expected` is a loose dict

A normal test case cares about `{"must_contain": [...]}`. An injection case cares about `{"forbidden_action": ..., "canary_string": ...}`. A future tool-call-correctness case cares about `{"expected_tool_calls": [...]}`. Forcing one rigid schema across all of these would mean a migration every time a new scorer is added. Instead, `expected` is an open dict and each `Scorer` reads only the keys it understands — a scorer that doesn't recognize a key simply doesn't apply, rather than erroring.

## Why injection payloads live in mocked tool-response fixtures, not the test file

The real threat model for the ADK agent is *indirect* prompt injection: a malicious instruction embedded in untrusted tool output (e.g. a news article fetched via the MCP server), not in the user's own message. Encoding that means the adapter needs a way to substitute a poisoned fixture for a live MCP call on specific test cases, deterministically and offline (so CI doesn't depend on a real news article containing an attack string on a given day). See `agentsentinel/testcases/fixtures/mcp_mock_responses/` (Phase 2) and `docs/injection_taxonomy.md` for the archetype list this corpus is built from.

## Why the CI gate is split into fast/deterministic vs. nightly/full

Running an LLM-as-judge faithfulness or injection-resistance check on every PR, against a live target agent, is slow and non-deterministic (judge variance, API flakiness, cost). The `agentsentinel run`/`gate` commands are designed so a per-PR run can restrict scorers to the deterministic set (`keyword_match`, `latency`, canary-string checks) while a scheduled nightly run adds the LLM-judge scorers against the real agents. Both write to the same `runs`/`traces`/`scores` tables, so the dashboard and regression diffing don't need to know which mode produced a given run.
