# AgentSentinel

**An evaluation and red-teaming harness for LLM agents.**

Most agent portfolios stop at "it works in the demo." AgentSentinel is the other half: it wraps *any* agent (a LangGraph pipeline, a Google ADK multi-agent system, a plain RAG chain) behind one common interface, runs it against a versioned suite of normal, edge-case, and adversarial prompt-injection test cases, scores the results (faithfulness, tool-call correctness, injection resistance, latency), and gates CI on regressions.

> Status: **Phase 0 and Phase 1 (all three real adapters) complete.** Core harness works end-to-end against a dependency-free toy agent, and every real target agent in the portfolio now has a working `AgentUnderTest` adapter. The LangGraph research pipeline and the RAG chatbot have both run live with a 100% pass rate. The ADK stock-analysis adapter is code-complete and its harness-level integration is verified (correct CLI output, correct error handling) — a live full run is currently blocked by an invalid `GOOGLE_API_KEY` in that target repo's own `.env`, confirmed independent of this project with a bare `google.genai.Client` call.
>
> Along the way the harness caught **four real, independent issues** in the wrapped agents — exactly the kind of thing this project exists to catch: a crash in the research pipeline when the critic never approves within its iteration budget; a self-conflicting `requirements.txt` in the RAG chatbot repo; a hard-coded reference to a since-retired Gemini model (`gemini-1.5-flash`) in *two separate repos*; and a README claiming an MCP server as a headline feature that the live agent path never actually calls (see [docs/architecture.md](docs/architecture.md) for all four in detail).

## Why this exists

Building an agent is table stakes now. Making one *trustworthy* — provably resistant to prompt injection via untrusted tool output, provably not hallucinating beyond its retrieved context, provably not regressing when a prompt changes — is the part most portfolios skip. AgentSentinel exists to fill that gap, using itself as the harness that evaluates three of my other agent projects.

## Architecture

The core problem: agent implementations have wildly incompatible call shapes — a pure function returning a final state dict, a stateful async multi-turn tool-calling agent owned by a framework runner, a function requiring externally-constructed dependencies that returns a streaming generator. `AgentUnderTest` is deliberately thin (`setup` / `run` / `teardown`) so each adapter absorbs its target's quirks internally and the harness only ever sees one normalized `AgentTrace`.

```
TestCase ──► AgentUnderTest.run() ──► AgentTrace ──► Scorer(s) ──► MetricScore ──► Scorecard
                                                                                       │
                                                                                       ▼
                                                                          SQLite (runs/traces/scores)
                                                                                       │
                                                                                       ▼
                                                                     regression check vs. baseline run
                                                                                       │
                                                                                       ▼
                                                                        CI gate (pass/fail exit code)
```

See [docs/architecture.md](docs/architecture.md) for the full design rationale (why `Protocol` over an ABC, why `TestCase.expected` is a loose dict, why injection payloads live in mocked tool-response fixtures rather than the test file itself).

## Quick start

```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -e ".[dev]"

pytest -v                              # runs the toy-agent end-to-end suite
python -m agentsentinel.cli run --agent toy-agent   # prints a live scorecard
```

## Project structure

```
agentsentinel/
  core/         # AgentUnderTest interface + TestCase/AgentTrace/Scorecard data model
  adapters/     # toy_agent (in-process) + real adapters (subprocess-isolated, own venv per target)
    shims/      # small scripts executed under each TARGET repo's own interpreter
  scoring/      # pluggable, self-registering metrics (keyword_match, latency,
                # tool_call_correctness now; faithfulness + injection_resistance in Phase 2)
  testcases/    # versioned YAML test cases (seed/ = trusted, CI-gating)
  runner/       # suite_runner: setup -> run -> score -> aggregate
  storage/      # SQLAlchemy schema + SQLite persistence, regression diffing
  cli/          # `agentsentinel run` / `gate` / `generate` / `report`
  dashboard/    # Streamlit scorecard + trace explorer (Phase 3)
tests/
docs/
```

## Roadmap

- [x] **Phase 0** — Core interfaces, toy adapter, deterministic scorers, SQLite storage, CI.
- [x] **Phase 1** — Real adapters for all three target agents (LangGraph research pipeline, RAG chatbot, Google ADK stock-analysis agent), each subprocess-isolated in its own venv — see [docs/architecture.md](docs/architecture.md). LangGraph and RAG chatbot are live-verified end-to-end; the ADK adapter is code-complete and harness-verified, pending a valid API key in its target repo.
- [ ] **Phase 2** — RAGAS-style faithfulness scorer (LLM-as-judge, calibrated against a hand-labeled set) + a curated prompt-injection corpus. Originally scoped around the ADK agent's MCP server; revised to target the `FunctionTool` layer it actually calls through (see docs/architecture.md's MCP-bypass finding).
- [ ] **Phase 3** — Regression tracking against a baseline run + Streamlit dashboard (trace explorer, score history, a dedicated injection tab).
- [ ] **Phase 4** — GitHub Actions CI gate wired into a real target repo (fast deterministic checks per-PR, full LLM-judge run nightly).

## License

MIT
