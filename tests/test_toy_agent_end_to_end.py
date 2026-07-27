"""Proves the full pipeline works with zero external dependencies:
interfaces -> toy adapter -> scorers -> suite_runner -> SQLite storage.
This is the test that keeps CI green from Phase 0 onward, before any real
portfolio-repo adapter exists.
"""
from __future__ import annotations

import agentsentinel.scoring  # noqa: F401 - registers builtin scorers
from agentsentinel.adapters.toy_agent import ToyAgentAdapter
from agentsentinel.runner.suite_runner import run_suite
from agentsentinel.scoring.registry import get_scorers
from agentsentinel.storage.db import get_engine, save_full_run
from agentsentinel.testcases.loader import load_seed_cases


def test_toy_agent_answers_known_facts_correctly():
    agent = ToyAgentAdapter()
    cases = load_seed_cases(agent_target="toy-agent")
    assert len(cases) == 3

    scorers = get_scorers(["keyword_match", "latency"])
    scorecard, traces = run_suite(agent, cases, scorers)

    assert scorecard.pass_rate == 1.0
    assert len(traces) == 3
    assert all(trace.error is None for trace in traces)


def test_toy_agent_declines_unknown_queries():
    agent = ToyAgentAdapter()
    cases = [c for c in load_seed_cases(agent_target="toy-agent") if c.id == "toy-003-unknown"]

    scorers = get_scorers(["keyword_match"])
    scorecard, traces = run_suite(agent, cases, scorers)

    assert scorecard.pass_rate == 1.0
    assert "don't know" in traces[0].output_text.lower()
    assert traces[0].sources == []


def test_scorecard_persists_to_sqlite(tmp_path):
    db_path = str(tmp_path / "test.db")
    agent = ToyAgentAdapter()
    cases = load_seed_cases(agent_target="toy-agent")
    scorers = get_scorers(["keyword_match", "latency"])

    scorecard, traces = run_suite(agent, cases, scorers)
    engine = get_engine(db_path)
    save_full_run(engine, scorecard, traces)

    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from agentsentinel.storage.schema import RunRow, ScoreRow, TraceRow

    with Session(engine) as session:
        run_row = session.get(RunRow, scorecard.run_id)
        assert run_row is not None
        assert run_row.agent_name == "toy-agent"

        trace_rows = session.scalars(select(TraceRow).where(TraceRow.run_id == scorecard.run_id)).all()
        assert len(trace_rows) == 3

        score_rows = session.scalars(
            select(ScoreRow).where(ScoreRow.trace_id == trace_rows[0].trace_id)
        ).all()
        assert len(score_rows) == 2  # keyword_match + latency
