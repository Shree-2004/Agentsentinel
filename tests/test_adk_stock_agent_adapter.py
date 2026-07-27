"""Live integration test for the real ADK stock-analysis agent adapter.

Skipped by default: hits real Gemini calls (root + up to 3 sub-agents) and
real Yahoo Finance API calls, so it must never run in the fast per-PR CI
gate. Run explicitly with: AGENTSENTINEL_RUN_LIVE_TESTS=1 pytest -v -m live

Note: as of writing, a live run of this adapter fails with a real,
external "API key not valid" error from Google's API — confirmed
independent of this adapter (see docs/architecture.md) — because the
GOOGLE_API_KEY in finance-agent/.env is invalid. That's a credential to
replace in the target repo's own .env, not a bug in this test or the
adapter code, which correctly reports the error via AgentTrace.error
instead of crashing.
"""
from __future__ import annotations

import os

import pytest

import agentsentinel.scoring  # noqa: F401 - registers builtin scorers
from agentsentinel.adapters.adk_stock_agent import AdkStockAgentAdapter
from agentsentinel.runner.suite_runner import run_suite
from agentsentinel.scoring.registry import get_scorers
from agentsentinel.testcases.loader import load_seed_cases

pytestmark = pytest.mark.skipif(
    os.environ.get("AGENTSENTINEL_RUN_LIVE_TESTS") != "1",
    reason="live test — hits real Gemini + Yahoo Finance APIs; set AGENTSENTINEL_RUN_LIVE_TESTS=1 to run",
)


@pytest.mark.live
def test_adk_stock_agent_runs_end_to_end():
    agent = AdkStockAgentAdapter()
    cases = load_seed_cases(agent_target="stock-analysis-adk")
    assert len(cases) == 2

    scorers = get_scorers(["keyword_match", "tool_call_correctness", "latency"])
    scorecard, traces = run_suite(agent, cases, scorers)

    assert len(traces) == 2
    for trace in traces:
        assert trace.error is None, f"adapter raised: {trace.error}"
