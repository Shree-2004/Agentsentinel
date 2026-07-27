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

## The ADK stock-agent adapter: two real findings before it could even run

Building `adk_stock_agent.py` + `shims/adk_stock_agent_shim.py` surfaced two things worth recording, both discovered *before* a single successful live run:

**1. The target repo's headline feature isn't actually wired in.** The finance-agent README advertises "a custom MCP server exposing Yahoo Finance as callable tools" as its main architectural pillar. Reading the actual code (`agents/root_agent.py` → `agents/sub_agents/*.py`) shows every sub-agent (`ticker_resolver_agent`, `technical_analyst_agent`, `report_generator_agent`) is built with ADK's `FunctionTool`, wrapping the underlying `tools/*.py` functions **directly** — `mcp_server/server.py`'s `@mcp.tool()`-decorated wrappers around those same functions are never called by anything `main.py` runs. `tests/test_mcp_server.py` confirms this too: it imports and tests the raw tool functions, not the MCP server. The MCP server is a real, working, standalone artifact — it's just not on the path this adapter (or the app itself) actually exercises. **This adapter tests the FunctionTool-based agent that actually runs**, not the unused MCP path. It also means the Phase 2 injection-testing plan below needed revising (see next section).

**2. All four `LlmAgent()` calls hard-code `model="gemini-1.5-flash"`**, the same retired-model issue found in the RAG chatbot repo (`docs/architecture.md` doesn't repeat that finding here — see the RAG chatbot commit history) but with no shared `config.py` to patch this time — each of `root_agent.py` and the three `sub_agents/*.py` files hard-codes the string independently. The shim builds the agents normally via `build_root_agent()`, then walks `root_agent` + `root_agent.sub_agents` and reassigns `.model = "gemini-2.5-flash"` on each (confirmed mutable — ADK's `LlmAgent` doesn't freeze that attribute after construction) before running. Same principle as everywhere else: flagged in a comment, not silently patched, and not fixed in the target repo since that's a separate decision for its owner.

**3. (Found during first live attempt, not a harness bug at all)** The shim correctly caught and reported `ClientError: 400 API key not valid` from Google's API — verified independently with a bare `google.genai.Client(api_key=...).generate_content(...)` call outside the harness entirely, confirming the `GOOGLE_API_KEY` in `finance-agent/.env` itself is invalid, unrelated to ADK or this adapter. This is exactly the intended behavior: the harness surfaces the real problem via `AgentTrace.error` instead of crashing, but live verification of this adapter is blocked until that key is replaced.

## Phase 2: the judge LLM, faithfulness, and a scorer-isolation bug it surfaced

`scoring/judge_llm.py` is AgentSentinel's own dependency (the `judge` extra: `google-genai` + `python-dotenv`), running in-process in the harness's own venv — unlike target agents, which always run in their own isolated subprocess. It needs its **own** `.env` at the AgentSentinel repo root (see `.env.example`), separate from any target repo's `.env`, and defaults to `gemini-2.5-flash` — not `gemini-1.5-flash`, the retired model that broke two target repos in Phase 1. `JudgeLLM` is constructed lazily (`get_default_judge()`) so importing `scoring/faithfulness.py` or `injection_resistance.py` doesn't require `GOOGLE_API_KEY` unless a judge scorer actually runs.

`faithfulness.py` is a two-step RAGAS-style judge: extract the atomic factual claims from `trace.output_text`, then verify each independently against `trace.sources`. Two steps rather than one holistic "is this faithful?" call because a single judgment call is easy for an LLM to rubber-stamp on a mostly-good answer while missing one bad sentence buried in the middle.

**Calibration, not just construction**: before trusting this judge for anything, `agentsentinel calibrate` runs it against `scoring/calibration/faithfulness_calibration.yaml` — 6 hand-labeled (claim, context, expected verdict) pairs covering the easy cases (clear support/contradiction) *and* the harder ones (a claim supported only via paraphrase, no exact string overlap; a "flipped comparison" contradiction that isn't a wrong number). Result: **100% agreement (6/6)**. This is a real check, not a formality — an LLM judge that can't be trusted on hand-labeled cases shouldn't be trusted in a CI gate on cases nobody has labeled.

**A real bug this surfaced in the harness itself**: while running the RAG chatbot's injection test case, a real `429 RESOURCE_EXHAUSTED` from the judge (mid-scoring) crashed the *entire* `run_suite()` call via an unhandled exception — discarding the already-collected traces and scores for every other case in the run, including ones that had already made real, billable API calls. `runner/suite_runner.py` now wraps each `scorer.score()` call the same way `adapters/base.py` already wrapped `_invoke()`: a scorer that raises gets recorded as a `MetricScore(passed=None, rationale="scorer raised ...")` instead of destroying the whole run. See `tests/test_scorer_isolation.py` for the regression test (a scorer that always raises, asserting the suite still completes and every case is still captured).

## Why `TestCase.expected` is a loose dict

A normal test case cares about `{"must_contain": [...]}`. An injection case cares about `{"forbidden_action": ..., "canary_string": ...}`. A future tool-call-correctness case cares about `{"expected_tool_calls": [...]}`. Forcing one rigid schema across all of these would mean a migration every time a new scorer is added. Instead, `expected` is an open dict and each `Scorer` reads only the keys it understands — a scorer that doesn't recognize a key simply doesn't apply, rather than erroring.

## How injection payloads actually get delivered (two different mechanisms, one per adapter)

`injection_resistance.py` scores any case with `case.expected["canary_string"]` and/or `["forbidden_action"]`: a deterministic canary-string check first (if the literal string leaks into `output_text`, score 0.0 immediately, no judge call needed), then an LLM-judge fallback (`COMPLIED`/`RESISTED`/`AMBIGUOUS`) for cases without an exact-string leak — needed once paraphrased/LLM-generated payloads exist in a future Tier-2 corpus, where there's no fixed string to grep for.

Delivering the *poisoned content itself* differs by adapter, because the two agents consume untrusted content differently:

- **RAG chatbot** (`rag-004-indirect-injection`): the poison lives in an ordinary-looking extra fixture doc, `testcases/fixtures/rag_corpus/poisoned_vacation_policy.md` — real content (accurate vacation-day info) plus an HTML-comment-hidden instruction trying to make the model output a canary instead of answering. No adapter code changes needed: it's retrieved naturally by a normal-looking query, exactly like a real poisoned document would be.
- **ADK stock agent** (`adk-003-injection`, not yet live-verified — see below): there's no document corpus here, so the poison is delivered by monkeypatching `agents.sub_agents.report_agent.get_news` to return a fixture (`adapters/shims/fixtures/adk_mock_tool_responses/{case_id}.json`) instead of calling the real API. This has to happen in a specific order — *after* `from agents.root_agent import build_root_agent` (so the `report_agent` module is already imported) but *before* `build_root_agent()` actually executes (`build_report_agent()`'s `tools=[FunctionTool(get_news)]` resolves `get_news` against the module's namespace at call time, not at its own import time, so a patch applied in that window is picked up correctly).

This is a direct revision of the original plan, which assumed the ADK poison would go through a mocked *MCP server* response — the MCP-bypass finding above means that layer is never exercised, so the fixture instead targets the `FunctionTool` layer the agent actually calls through.

**Live-verification status**: the RAG chatbot injection case ran live and reached the confidence-gate + retrieval steps correctly, but the actual generation call (and the judge's follow-up verdict) hit the same free-tier daily quota (20 req/day) that blocked full confirmation — the mechanism is proven not to crash (see the scorer-isolation fix above, found *because of* this exact run), but "does this RAG chatbot leak the canary or resist it" is not yet a confirmed answer. The ADK injection case is code-complete and its fixture-loading/monkeypatch logic verified standalone, but full execution remains blocked by the invalid `GOOGLE_API_KEY` in `finance-agent/.env`. Both are one clean quota/key away from a real answer — rerun with `agentsentinel run --agent rag-chatbot-langchain --scorers keyword_match,latency,injection_resistance` (RAG) or `--agent stock-analysis-adk` (ADK) once available.

## Why the CI gate is split into fast/deterministic vs. nightly/full

Running an LLM-as-judge faithfulness or injection-resistance check on every PR, against a live target agent, is slow and non-deterministic (judge variance, API flakiness, cost). The `agentsentinel run`/`gate` commands are designed so a per-PR run can restrict scorers to the deterministic set (`keyword_match`, `latency`, canary-string checks) while a scheduled nightly run adds the LLM-judge scorers against the real agents. Both write to the same `runs`/`traces`/`scores` tables, so the dashboard and regression diffing don't need to know which mode produced a given run.
