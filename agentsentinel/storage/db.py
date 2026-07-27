"""Engine/session management + persistence of a Scorecard into the schema.
Default DB path is ./agentsentinel.db (gitignored); tests override via
AGENTSENTINEL_DB_PATH or by passing an explicit path to get_engine().
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import asdict

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from agentsentinel.core.models import Scorecard
from agentsentinel.storage.schema import Base, RunRow, ScoreRow, TraceRow

_DEFAULT_DB_PATH = "agentsentinel.db"


def get_engine(db_path: str | None = None):
    path = db_path or os.environ.get("AGENTSENTINEL_DB_PATH", _DEFAULT_DB_PATH)
    engine = create_engine(f"sqlite:///{path}", future=True)
    Base.metadata.create_all(engine)
    return engine


@contextmanager
def session_scope(engine) -> Session:
    SessionLocal = sessionmaker(bind=engine, future=True)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def save_full_run(engine, scorecard: Scorecard, traces: list, git_sha: str | None = None) -> None:
    """Persist a scorecard together with its underlying AgentTrace/MetricScore
    objects. `traces` is a list[AgentTrace] in the same order as scorecard.results.
    """
    with session_scope(engine) as session:
        run_row = RunRow(
            id=scorecard.run_id,
            agent_name=scorecard.agent_name,
            started_at=scorecard.started_at,
            finished_at=scorecard.finished_at,
            git_sha=git_sha,
            pass_rate=scorecard.pass_rate,
            aggregate_json=scorecard.aggregate,
            baseline_run_id=scorecard.baseline_run_id,
            regressions_json=scorecard.regressions,
        )
        session.add(run_row)

        trace_by_id = {t.trace_id: t for t in traces}
        for result in scorecard.results:
            trace = trace_by_id[result.trace_id]
            trace_row = TraceRow(
                trace_id=trace.trace_id,
                run_id=scorecard.run_id,
                test_case_id=trace.test_case_id,
                agent_name=trace.agent_name,
                output_text=trace.output_text,
                tool_calls_json=[asdict(tc) for tc in trace.tool_calls],
                sources_json=[asdict(s) for s in trace.sources],
                latency_ms=trace.latency_ms,
                prompt_tokens=trace.prompt_tokens,
                completion_tokens=trace.completion_tokens,
                cost_usd_estimate=trace.cost_usd_estimate,
                error=trace.error,
                raw_output_json=_safe_json(trace.raw_output),
                created_at=trace.created_at,
            )
            session.add(trace_row)

            for score in result.scores:
                session.add(
                    ScoreRow(
                        trace_id=trace.trace_id,
                        metric_name=score.metric_name,
                        score=score.score,
                        passed=score.passed,
                        rationale=score.rationale,
                        raw_json=score.raw,
                    )
                )


def _safe_json(value):
    """raw_output is agent-specific and best-effort only (debugging escape
    hatch, never consumed by scorers) — if it isn't JSON-serializable, store
    its repr instead of failing the whole run."""
    import json

    try:
        json.dumps(value)
        return value
    except TypeError:
        return {"__repr__": repr(value)}
