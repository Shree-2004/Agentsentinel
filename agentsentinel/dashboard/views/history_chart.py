"""Score history across runs for one agent — the view that makes a
regression visible as a trend line, not just a single red table row.
"""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from agentsentinel.dashboard import data


def render(engine, agent_name: str) -> None:
    runs = data.list_runs(engine, agent_name)
    if len(runs) < 2:
        st.info("Need at least 2 runs for this agent to show a history trend.")
        return

    all_metrics: set[str] = set()
    for aggregate_json in runs["aggregate_json"]:
        aggregate = json.loads(aggregate_json) if isinstance(aggregate_json, str) else aggregate_json
        all_metrics.update(aggregate.keys())

    if not all_metrics:
        st.info("No scored metrics recorded yet.")
        return

    metric = st.selectbox("Metric", options=sorted(all_metrics))
    history = data.get_score_history(engine, agent_name, metric)
    if history.empty:
        st.info(f"No history for '{metric}'.")
        return

    chart_df = history.set_index("started_at")[["score"]].rename(columns={"score": metric})
    st.line_chart(chart_df)
    st.caption(f"{len(history)} run(s) with '{metric}' scored, oldest to newest.")
