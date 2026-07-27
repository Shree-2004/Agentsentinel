"""Deterministic scorer: agent responsiveness against a configurable target.
score = min(1.0, target_ms / actual_ms); a case can override the target via
case.expected["latency_target_ms"], else falls back to the class default.
"""
from __future__ import annotations

from agentsentinel.core.models import AgentTrace, MetricScore, TestCase
from agentsentinel.scoring.registry import register


class LatencyScorer:
    name = "latency"
    default_target_ms = 5000.0

    def score(self, case: TestCase, trace: AgentTrace) -> MetricScore:
        target_ms = case.expected.get("latency_target_ms", self.default_target_ms)
        if trace.latency_ms <= 0:
            return MetricScore(metric_name=self.name, score=1.0, passed=True, rationale="no latency recorded")

        score = min(1.0, target_ms / trace.latency_ms)
        return MetricScore(
            metric_name=self.name,
            score=score,
            passed=trace.latency_ms <= target_ms,
            rationale=f"{trace.latency_ms:.0f}ms vs {target_ms:.0f}ms target",
        )


register(LatencyScorer())
