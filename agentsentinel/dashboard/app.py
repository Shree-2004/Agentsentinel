"""Streamlit dashboard: `streamlit run agentsentinel/dashboard/app.py`.

Reads directly off the SQLite database `agentsentinel run`/`gate` already
write to — no separate ingestion step, no second source of truth. Built
after the CLI (not before) deliberately: the eval engine, adapters, and
injection corpus are what make this project technically substantive: the
dashboard is a viewer on top of data that already exists, not the other
way around.
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from agentsentinel.dashboard import data
from agentsentinel.dashboard.views import history_chart, injection_tab, overview, trace_explorer
from agentsentinel.storage.db import get_engine

# agentsentinel/agentsentinel/dashboard/app.py -> agentsentinel/ (repo root)
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEMO_DB = _REPO_ROOT / "demo_data.db"

st.set_page_config(page_title="AgentSentinel", layout="wide")
st.title("AgentSentinel")
st.caption("Evaluation and red-teaming results for the wrapped agents.")

# Defaults to the committed showcase dataset (demo_data.db) so this renders
# something real immediately on a fresh deploy (e.g. Streamlit Community
# Cloud) with no setup step. Override in the sidebar to point at your own
# agentsentinel.db from a local `run`/`gate`.
default_db = str(_DEMO_DB) if _DEMO_DB.exists() else "agentsentinel.db"
db_path = st.sidebar.text_input("Database", value=default_db)
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
