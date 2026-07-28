"""End-to-end test for the config-only "bring your own agent" path: no
custom adapter, no shim written for this specific target — just
examples/simple_agent/agentsentinel.yaml pointing GenericAgentAdapter at an
ordinary function it's never seen before. Uses the real ensure_venv() path
(creates examples/simple_agent/venv/ on first run if missing), but that
target has zero third-party dependencies, so this stays fast and needs no
network/API key - safe for the regular (non-live) CI suite.
"""
from __future__ import annotations

from pathlib import Path

import agentsentinel.scoring  # noqa: F401 - registers builtin scorers
from agentsentinel.runner.suite_runner import run_suite
from agentsentinel.scoring.registry import get_scorers
from agentsentinel.testcases.external_config import load_external_config

_CONFIG_PATH = Path(__file__).resolve().parents[1] / "examples" / "simple_agent" / "agentsentinel.yaml"


def test_generic_adapter_runs_an_unmodified_external_function():
    agent, cases = load_external_config(_CONFIG_PATH)
    assert agent.name == "simple-faq-bot"
    assert len(cases) == 3

    scorers = get_scorers(["keyword_match", "latency", "tool_call_correctness"])
    scorecard, traces = run_suite(agent, cases, scorers)

    assert scorecard.pass_rate == 1.0
    assert all(t.error is None for t in traces)
