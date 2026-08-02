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

with st.expander("What am I looking at?", expanded=True):
    st.markdown(
        """
AgentSentinel is a test harness for LLM agents: it runs each agent against a
suite of normal, edge-case, and **adversarial prompt-injection** test cases,
then scores every response. This dashboard is the read-only viewer over
those results — nothing here re-computes a score, it just displays what the
CLI (`agentsentinel run` / `gate`) already decided.

**Start with the agent picker in the sidebar**, then use the tabs below:

- **Overview** — pick a run, see its pass rate and whether it regressed
  against the previous ("baseline") run.
- **Trace Explorer** — drill into one run: every test case's raw output,
  tool calls, and *why* each scorer gave the score it did.
- **Score History** — a metric's score over time, across runs, as a trend
  line — so a regression shows up as a dip, not just a red table row.
- **🛡️ Injection** — the headline tab: every case where an agent was
  attacked with a prompt injection, across *all* agents and runs, with any
  case where the agent fell for it (🔴 "complied") called out first.
        """
    )

with st.sidebar.expander("Advanced: data source", expanded=False):
    st.caption(
        "Defaults to the committed showcase dataset. Point this at your own "
        "`agentsentinel.db` (produced by a local `run`/`gate`) to see your own results."
    )
    default_db = str(_DEMO_DB) if _DEMO_DB.exists() else "agentsentinel.db"
    db_path = st.text_input("Database path", value=default_db)

engine = get_engine(db_path)

agents = data.list_agents(engine)
if not agents:
    st.warning(
        f"No runs found in `{db_path}`. Run `agentsentinel run --agent <name>` "
        f"(or `gate`) first, then refresh this page."
    )
    st.stop()

agent_name = st.sidebar.selectbox("Agent", options=agents, help="Each agent was evaluated independently — pick one to see its results.")

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
