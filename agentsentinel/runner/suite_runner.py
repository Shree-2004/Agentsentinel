"""Orchestrates one full suite run: adapter.setup -> run each case -> score
each trace -> aggregate into a Scorecard. This is the one place that knows
about both AgentUnderTest and Scorer — everything else only needs to know
about one side of that boundary.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from agentsentinel.core.interfaces import AgentUnderTest
from agentsentinel.core.models import (
    AgentTrace,
    EvalResult,
    RunContext,
    Scorecard,
    TestCase,
)
from agentsentinel.scoring.registry import Scorer


def run_suite(
    agent: AgentUnderTest,
    cases: list[TestCase],
    scorers: list[Scorer],
    config: dict | None = None,
) -> tuple[Scorecard, list[AgentTrace]]:
    """Runs `agent` against every case in `cases`, scores each resulting
    trace with every scorer in `scorers`, and returns the aggregated
    Scorecard plus the raw traces (callers that want to persist full traces,
    e.g. storage.save_full_run, need both)."""

    run_id = str(uuid.uuid4())
    ctx = RunContext(run_id=run_id, config=config or {})
    started_at = datetime.now(timezone.utc)

    agent.setup(ctx)
    traces: list[AgentTrace] = []
    results: list[EvalResult] = []

    try:
        for case in cases:
            trace = agent.run(case, ctx)
            traces.append(trace)

            scores = [scorer.score(case, trace) for scorer in scorers]
            results.append(
                EvalResult(
                    trace_id=trace.trace_id,
                    test_case_id=case.id,
                    agent_name=trace.agent_name,
                    scores=scores,
                )
            )
    finally:
        agent.teardown(ctx)

    finished_at = datetime.now(timezone.utc)
    aggregate = _aggregate_scores(results)
    pass_rate = _pass_rate(results)

    scorecard = Scorecard(
        run_id=run_id,
        agent_name=agent.name,
        started_at=started_at,
        finished_at=finished_at,
        results=results,
        aggregate=aggregate,
        pass_rate=pass_rate,
    )
    return scorecard, traces


def _aggregate_scores(results: list[EvalResult]) -> dict[str, float]:
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for result in results:
        for score in result.scores:
            sums[score.metric_name] = sums.get(score.metric_name, 0.0) + score.score
            counts[score.metric_name] = counts.get(score.metric_name, 0) + 1
    return {name: sums[name] / counts[name] for name in sums}


def _pass_rate(results: list[EvalResult]) -> float:
    if not results:
        return 0.0
    passed = 0
    for result in results:
        # a case "passes" only if every scorer that reported a pass/fail
        # verdict passed; scorers with passed=None (no verdict) don't block.
        verdicts = [s.passed for s in result.scores if s.passed is not None]
        if all(verdicts) if verdicts else True:
            passed += 1
    return passed / len(results)
