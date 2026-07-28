"""Streamlit dashboard: `streamlit run agentsentinel/dashboard/app.py`.

Reads directly off the SQLite database `agentsentinel run`/`gate` already
write to — no separate ingestion step, no second source of truth. Built
after the CLI (not before) deliberately: the eval engine, adapters, and
injection corpus are what make this project technically substantive: the
dashboard is a viewer on top of data that already exists, not the other
way around.
"""
from __future__ import annotations

import streamlit as st

from agentsentinel.dashboard import data
from agentsentinel.dashboard.views import history_chart, injection_tab, overview, trace_explorer
from agentsentinel.storage.db import get_engine

st.set_page_config(page_title="AgentSentinel", layout="wide")
st.title("AgentSentinel")
st.caption("Evaluation and red-teaming results for the wrapped agents.")

db_path = st.sidebar.text_input("Database", value="agentsentinel.db")
engine = get_engine(db_path)

agents = data.list_agents(engine)
if not agents:
    st.warning(
        f"No runs found in `{db_path}`. Run `agentsentinel run --agent <name>` "
        f"(or `gate`) first, then refresh this page."
    )
    st.stop()

agent_name = st.sidebar.selectbox("Agent", options=agents)

tab_overview, tab_traces, tab_history, tab_injection = st.tabs(
    ["Overview", "Trace Explorer", "Score History", "🛡️ Injection"]
)

with tab_overview:
    selected_run_id = overview.render(engine, agent_name)

with tab_traces:
    if selected_run_id:
        trace_explorer.render(engine, selected_run_id)
    else:
        st.info("Select a run in the Overview tab first.")

with tab_history:
    history_chart.render(engine, agent_name)

with tab_injection:
    injection_tab.render(engine)
