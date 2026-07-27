"""A scorer raising (rate limit, malformed judge output, etc.) must not
crash the whole suite and lose every other case's already-collected
results — this is exactly what happened with a real 429 from the judge
during the RAG chatbot injection run. Regression test for that.
"""
from __future__ import annotations

from agentsentinel.adapters.toy_agent import ToyAgentAdapter
from agentsentinel.core.models import AgentTrace, MetricScore, TestCase
from agentsentinel.runner.suite_runner import run_suite
from agentsentinel.testcases.loader import load_seed_cases


class _RaisingScorer:
    name = "raising_scorer"

    def score(self, case: TestCase, trace: AgentTrace) -> MetricScore:
        raise RuntimeError("simulated transient failure (e.g. a 429 from an LLM judge)")


def test_a_raising_scorer_does_not_crash_the_suite():
    agent = ToyAgentAdapter()
    cases = load_seed_cases(agent_target="toy-agent")

    scorecard, traces = run_suite(agent, cases, [_RaisingScorer()])

    assert len(traces) == len(cases)  # every case still ran and was captured
    for result in scorecard.results:
        assert len(result.scores) == 1
        score = result.scores[0]
        assert score.passed is None  # no verdict, not counted as a failure
        assert "RuntimeError" in score.rationale
