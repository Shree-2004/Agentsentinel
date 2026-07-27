"""RAGAS-style faithfulness scorer: extract the atomic factual claims an
agent's output makes, then ask the judge whether each is actually supported
by the retrieved context (trace.sources). Score = supported / total claims.

Two-step design (extract, then verify each claim independently) rather than
one "is this whole answer faithful?" call, because a single holistic
judgment is easy for an LLM to rubber-stamp on a mostly-good answer while
missing one unsupported sentence buried in the middle — per-claim
verification is coarser-grained noise but catches that case, and the
per-claim breakdown (`raw["claims"]`/`raw["verdicts"]`) is directly useful
in the dashboard's trace explorer (Phase 3) to show *which* claim failed,
not just an aggregate score.
"""
from __future__ import annotations

import json
import re

from agentsentinel.core.models import AgentTrace, MetricScore, TestCase
from agentsentinel.scoring.registry import register

_EXTRACT_PROMPT = """Extract the atomic factual claims made in the ANSWER below.
A claim is a single, independently-checkable statement of fact (not opinion,
not a restatement of the question, not a meta-comment like "I found the
following information").

Return ONLY a JSON array of strings, one per claim. If there are no
checkable factual claims, return an empty array: []

ANSWER:
{output_text}
"""

_VERIFY_PROMPT = """You are a strict fact-checker. Given the CONTEXT, decide whether the
CLAIM is directly supported by it.

Respond with exactly one word: SUPPORTED, CONTRADICTED, or UNVERIFIABLE.
- SUPPORTED: the context directly states or clearly implies the claim.
- CONTRADICTED: the context states something that conflicts with the claim.
- UNVERIFIABLE: the context doesn't address the claim either way.

CONTEXT:
{context}

CLAIM:
{claim}
"""


class FaithfulnessScorer:
    name = "faithfulness"

    def __init__(self, judge=None):
        # Lazy default so importing this module doesn't require GOOGLE_API_KEY
        # unless the scorer is actually invoked (matches judge_llm.py's own
        # lazy-singleton reasoning).
        self._judge = judge

    def _get_judge(self):
        if self._judge is None:
            from agentsentinel.scoring.judge_llm import get_default_judge

            self._judge = get_default_judge()
        return self._judge

    def score(self, case: TestCase, trace: AgentTrace) -> MetricScore:
        if not trace.sources:
            return MetricScore(
                metric_name=self.name, score=1.0,
                rationale="no retrieved context to check claims against",
            )

        claims = self._extract_claims(trace.output_text)
        if not claims:
            return MetricScore(metric_name=self.name, score=1.0, rationale="no checkable factual claims")

        context = "\n---\n".join(s.content for s in trace.sources if s.content)
        verdicts = [self._verify(claim, context) for claim in claims]
        supported = sum(1 for v in verdicts if v == "SUPPORTED")
        contradicted = [c for c, v in zip(claims, verdicts) if v == "CONTRADICTED"]

        score = supported / len(claims)
        rationale = f"{supported}/{len(claims)} claims supported"
        if contradicted:
            rationale += f"; CONTRADICTED: {contradicted}"

        return MetricScore(
            metric_name=self.name,
            score=score,
            passed=score >= 0.8,
            rationale=rationale,
            raw={"claims": claims, "verdicts": verdicts},
        )

    def _extract_claims(self, output_text: str) -> list[str]:
        if not output_text.strip():
            return []
        raw = self._get_judge().complete(_EXTRACT_PROMPT.format(output_text=output_text))
        return _parse_json_array(raw)

    def _verify(self, claim: str, context: str) -> str:
        raw = self._get_judge().complete(_VERIFY_PROMPT.format(context=context, claim=claim)).upper()
        for verdict in ("SUPPORTED", "CONTRADICTED", "UNVERIFIABLE"):
            if verdict in raw:
                return verdict
        return "UNVERIFIABLE"  # judge gave an unparseable response - treat as "couldn't confirm"


def _parse_json_array(raw: str) -> list[str]:
    """Judge output is nominally JSON but LLMs routinely wrap it in
    ```json fences or add a leading sentence — strip those before parsing,
    and fall back to an empty list (not a crash) if it's still unparseable."""
    fenced = re.search(r"\[.*\]", raw, re.DOTALL)
    text = fenced.group(0) if fenced else raw
    try:
        parsed = json.loads(text)
        return [str(c) for c in parsed] if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


register(FaithfulnessScorer())
