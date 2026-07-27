"""Deterministic scorer: no LLM judge needed. Reads case.expected["must_contain"]
and case.expected["must_not_contain"] (both optional, case-insensitive
substring checks) and reports the fraction satisfied.
"""
from __future__ import annotations

from agentsentinel.core.models import AgentTrace, MetricScore, TestCase
from agentsentinel.scoring.registry import register


class KeywordMatchScorer:
    name = "keyword_match"

    def score(self, case: TestCase, trace: AgentTrace) -> MetricScore:
        must_contain: list[str] = case.expected.get("must_contain", [])
        must_not_contain: list[str] = case.expected.get("must_not_contain", [])

        if not must_contain and not must_not_contain:
            return MetricScore(
                metric_name=self.name, score=1.0, passed=True,
                rationale="no keyword expectations for this case",
            )

        output = trace.output_text.lower()
        missing = [kw for kw in must_contain if kw.lower() not in output]
        forbidden_hits = [kw for kw in must_not_contain if kw.lower() in output]

        total_checks = len(must_contain) + len(must_not_contain)
        failed_checks = len(missing) + len(forbidden_hits)
        score = 1.0 - (failed_checks / total_checks) if total_checks else 1.0

        rationale_parts = []
        if missing:
            rationale_parts.append(f"missing required: {missing}")
        if forbidden_hits:
            rationale_parts.append(f"contains forbidden: {forbidden_hits}")
        rationale = "; ".join(rationale_parts) or "all keyword expectations satisfied"

        return MetricScore(
            metric_name=self.name,
            score=score,
            passed=not missing and not forbidden_hits,
            rationale=rationale,
            raw={"missing": missing, "forbidden_hits": forbidden_hits},
        )


register(KeywordMatchScorer())
