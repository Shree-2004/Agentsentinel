"""Live integration test for the real LangGraph research-assistant adapter.

Skipped by default: this hits real Gemini + Tavily/ArXiv APIs, costs quota,
and takes 30-60s+ per case, so it must never run in the fast per-PR CI gate.
Run explicitly with: AGENTSENTINEL_RUN_LIVE_TESTS=1 pytest -v -m live
"""
from __future__ import annotations

import os

import pytest

import agentsentinel.scoring  # noqa: F401 - registers builtin scorers
from agentsentinel.adapters.langgraph_research import LangGraphResearchAdapter
from agentsentinel.runner.suite_runner import run_suite
from agentsentinel.scoring.registry import get_scorers
from agentsentinel.testcases.loader import load_seed_cases

pytestmark = pytest.mark.skipif(
    os.environ.get("AGENTSENTINEL_RUN_LIVE_TESTS") != "1",
    reason="live test — hits real LLM/search APIs; set AGENTSENTINEL_RUN_LIVE_TESTS=1 to run",
)


@pytest.mark.live
def test_langgraph_research_pipeline_runs_end_to_end():
    agent = LangGraphResearchAdapter()
    cases = load_seed_cases(agent_target="research-pipeline-langgraph")
    assert len(cases) == 2

    scorers = get_scorers(["keyword_match", "tool_call_correctness", "latency"])
    scorecard, traces = run_suite(agent, cases, scorers)

    assert len(traces) == 2
    for trace in traces:
        assert trace.error is None, f"adapter raised: {trace.error}"
        assert trace.output_text, "pipeline returned an empty report"
