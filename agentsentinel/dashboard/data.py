"""Read-only data access for the dashboard. Deliberately thin wrappers over
plain SQL via pandas.read_sql — the dashboard is a viewer, not a second
place business logic (aggregation, regression detection) should live. All
of that already happened at run/gate time and is stored on the RunRow; the
dashboard just displays it, so what it shows can never drift from what the
CLI gate decided.
"""
from __future__ import annotations

import json

import pandas as pd
from sqlalchemy import Engine


def list_agents(engine: Engine) -> list[str]:
    df = pd.read_sql("SELECT DISTINCT agent_name FROM runs ORDER BY agent_name", engine)
    return df["agent_name"].tolist()


def list_runs(engine: Engine, agent_name: str) -> pd.DataFrame:
    return pd.read_sql(
        "SELECT id, started_at, finished_at, pass_rate, baseline_run_id, regressions_json, aggregate_json "
        "FROM runs WHERE agent_name = ? ORDER BY started_at DESC",
        engine,
        params=(agent_name,),
    )


def get_run(engine: Engine, run_id: str) -> pd.Series | None:
    df = pd.read_sql("SELECT * FROM runs WHERE id = ?", engine, params=(run_id,))
    return df.iloc[0] if not df.empty else None


def get_traces(engine: Engine, run_id: str) -> pd.DataFrame:
    return pd.read_sql(
        "SELECT * FROM traces WHERE run_id = ? ORDER BY created_at", engine, params=(run_id,)
    )


def get_scores_for_trace(engine: Engine, trace_id: str) -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM scores WHERE trace_id = ?", engine, params=(trace_id,))


def get_score_history(engine: Engine, agent_name: str, metric_name: str) -> pd.DataFrame:
    """One row per run, with that run's mean score for `metric_name` — the
    series the history chart plots. Reads straight from each run's
    precomputed aggregate_json rather than re-joining traces/scores, for
    the same reason as the module docstring: don't recompute what run/gate
    already computed."""
    runs = list_runs(engine, agent_name)
    rows = []
    for _, run in runs.iterrows():
        aggregate = json.loads(run["aggregate_json"]) if isinstance(run["aggregate_json"], str) else run["aggregate_json"]
        if metric_name in aggregate:
            rows.append({"run_id": run["id"], "started_at": run["started_at"], "score": aggregate[metric_name]})
    return pd.DataFrame(rows).sort_values("started_at") if rows else pd.DataFrame(columns=["run_id", "started_at", "score"])


def get_injection_cases(engine: Engine) -> pd.DataFrame:
    """Every trace ever scored by injection_resistance, across all agents
    and runs — the data behind the dedicated injection tab."""
    return pd.read_sql(
        """
        SELECT t.run_id, t.test_case_id, t.agent_name, t.output_text, t.created_at,
               s.score, s.passed, s.rationale
        FROM scores s
        JOIN traces t ON t.trace_id = s.trace_id
        WHERE s.metric_name = 'injection_resistance'
        ORDER BY t.created_at DESC
        """,
        engine,
    )
