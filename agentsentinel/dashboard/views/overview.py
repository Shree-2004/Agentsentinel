"""Run picker + scorecard summary + regression callouts for the selected run."""
from __future__ import annotations

import json

import streamlit as st

from agentsentinel.dashboard import data


def render(engine, agent_name: str) -> str | None:
    """Renders the run picker + summary. Returns the selected run_id (or
    None if the agent has no runs yet) so other tabs can reuse the same
    selection."""
    runs = data.list_runs(engine, agent_name)
    if runs.empty:
        st.info(f"No runs yet for '{agent_name}'. Run `agentsentinel run --agent {agent_name}` first.")
        return None

    labels = [f"{row.started_at} — pass rate {row.pass_rate:.0%} — {row.id[:8]}" for row in runs.itertuples()]
    selected_idx = st.selectbox("Run", options=range(len(runs)), format_func=lambda i: labels[i])
    run = runs.iloc[selected_idx]

    col1, col2, col3 = st.columns(3)
    col1.metric("Pass rate", f"{run.pass_rate:.0%}")
    aggregate = json.loads(run.aggregate_json) if isinstance(run.aggregate_json, str) else run.aggregate_json
    col2.metric("Metrics scored", len(aggregate))
    regressions = json.loads(run.regressions_json) if isinstance(run.regressions_json, str) else run.regressions_json
    col3.metric("Regressions", len(regressions), delta=None if not regressions else f"-{len(regressions)}")

    st.subheader("Aggregate scores")
    st.table({metric: f"{score:.2f}" for metric, score in aggregate.items()})

    if run.baseline_run_id:
        st.caption(f"Compared against baseline run `{run.baseline_run_id[:8]}`")
        if regressions:
            st.error(f"{len(regressions)} regression(s) found")
            st.table(
                [
                    {
                        "case": r["test_case_id"],
                        "metric": r["metric_name"],
                        "baseline": f"{r['baseline_score']:.2f}",
                        "current": f"{r['current_score']:.2f}",
                        "delta": f"{r['delta']:+.2f}",
                    }
                    for r in regressions
                ]
            )
        else:
            st.success("No regressions vs. baseline.")
    else:
        st.caption("No baseline recorded for this run (first run for this agent, or run via `run` not `gate`).")

    return run.id
