# AgentSentinel

**An evaluation and red-teaming harness for LLM agents.**

Most agent portfolios stop at "it works in the demo." AgentSentinel is the other half: it wraps *any* agent (a LangGraph pipeline, a Google ADK multi-agent system, a plain RAG chain) behind one common interface, runs it against a versioned suite of normal, edge-case, and adversarial prompt-injection test cases, scores the results (faithfulness, tool-call correctness, injection resistance, latency), and gates CI on regressions.

> Status: **Phase 0 and two of three Phase 1 adapters complete.** Core harness works end-to-end against a dependency-free toy agent. Both the LangGraph research-pipeline adapter and the RAG chatbot adapter have run live against their real agents with a 100% pass rate. Along the way the harness caught three real, independent bugs: a crash in the research pipeline when the critic never approves within its iteration budget, a self-conflicting `requirements.txt` in the RAG chatbot repo, and a hard-coded reference to a since-retired Gemini model (`gemini-1.5-flash`) in the RAG chatbot's config — exactly the kind of thing this project exists to catch. The Google ADK stock-analysis adapter is next.

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
- [x] **Phase 1a/1b** — Real adapters for the LangGraph research pipeline and RAG chatbot, both live-verified (subprocess-isolated per target venv — see [docs/architecture.md](docs/architecture.md)).
- [ ] **Phase 1c** — Real adapter for the Google ADK stock-analysis agent (async, multi-turn, tool-calling — the hardest of the three).
- [ ] **Phase 2** — RAGAS-style faithfulness scorer (LLM-as-judge, calibrated against a hand-labeled set) + a curated prompt-injection corpus targeting the ADK agent's MCP tool-calling surface.
- [ ] **Phase 3** — Regression tracking against a baseline run + Streamlit dashboard (trace explorer, score history, a dedicated injection tab).
- [ ] **Phase 4** — GitHub Actions CI gate wired into a real target repo (fast deterministic checks per-PR, full LLM-judge run nightly).

## License

MIT
