"""Live integration test for the real RAG chatbot adapter.

Skipped by default: this hits a real Gemini API call and loads a local
HuggingFace embedding model (slow, non-trivial disk cache), so it must never
run in the fast per-PR CI gate.
Run explicitly with: AGENTSENTINEL_RUN_LIVE_TESTS=1 pytest -v -m live
"""
from __future__ import annotations

import os

import pytest

import agentsentinel.scoring  # noqa: F401 - registers builtin scorers
from agentsentinel.adapters.rag_chatbot import RagChatbotAdapter
from agentsentinel.runner.suite_runner import run_suite
from agentsentinel.scoring.registry import get_scorers
from agentsentinel.testcases.loader import load_seed_cases

pytestmark = pytest.mark.skipif(
    os.environ.get("AGENTSENTINEL_RUN_LIVE_TESTS") != "1",
    reason="live test — hits a real LLM API and loads a local embedding model; set AGENTSENTINEL_RUN_LIVE_TESTS=1 to run",
)


@pytest.mark.live
def test_rag_chatbot_runs_end_to_end():
    agent = RagChatbotAdapter()
    cases = load_seed_cases(agent_target="rag-chatbot-langchain")
    assert len(cases) == 3

    scorers = get_scorers(["keyword_match", "tool_call_correctness", "latency"])
    scorecard, traces = run_suite(agent, cases, scorers)

    assert len(traces) == 3
    for trace in traces:
        assert trace.error is None, f"adapter raised: {trace.error}"
