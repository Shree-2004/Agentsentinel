"""Deterministic, no LLM needed: compares the tool calls an agent actually
made against case.expected["expected_tool_calls"]. Membership check by
default (order-insensitive); a case can opt into order-sensitivity via
case.expected["ordered"] = True for flows where sequence matters (e.g.
"must resolve a ticker before fetching its price").
"""
from __future__ import annotations

from agentsentinel.core.models import AgentTrace, MetricScore, TestCase
from agentsentinel.scoring.registry import register


class ToolCallCorrectnessScorer:
    name = "tool_call_correctness"

    def score(self, case: TestCase, trace: AgentTrace) -> MetricScore:
        expected: list[str] = case.expected.get("expected_tool_calls", [])
        if not expected:
            return MetricScore(
                metric_name=self.name, score=1.0, passed=True,
                rationale="no tool-call expectation for this case",
            )

        actual = [tc.name for tc in trace.tool_calls]

        if case.expected.get("ordered", False):
            correct = actual[: len(expected)] == expected
            score = 1.0 if correct else 0.0
            rationale = "expected order matched" if correct else f"expected {expected}, got {actual}"
            return MetricScore(metric_name=self.name, score=score, passed=correct, rationale=rationale)

        expected_set, actual_set = set(expected), set(actual)
        missing = expected_set - actual_set
        score = 1.0 - (len(missing) / len(expected_set))
        rationale = f"missing: {sorted(missing)}" if missing else "all expected tools called"
        return MetricScore(
            metric_name=self.name, score=score, passed=not missing, rationale=rationale,
            raw={"expected": sorted(expected_set), "actual": sorted(actual_set)},
        )


register(ToolCallCorrectnessScorer())
