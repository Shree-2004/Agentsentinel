"""Per-trace detail: output, tool calls, sources, and each scorer's
rationale — the view that proves an LLM judge isn't a black box. Every
score shown elsewhere in the dashboard traces back to a rationale visible
here.
"""
from __future__ import annotations

import json

import streamlit as st

from agentsentinel.dashboard import data


def render(engine, run_id: str) -> None:
    traces = data.get_traces(engine, run_id)
    if traces.empty:
        st.info("No traces for this run.")
        return

    st.caption(
        "One expander per test case in this run. 🟢 means the agent ran without error "
        "(scores below still tell you if it passed); 🔴 means the agent itself errored out. "
        "Expand a case to see its raw output, tool calls, and each scorer's rationale."
    )

    for trace in traces.itertuples():
        icon = "🔴" if trace.error else "🟢"
        with st.expander(f"{icon} {trace.test_case_id} — {trace.latency_ms:.0f}ms"):
            if trace.error:
                st.error(trace.error)
                continue

            st.markdown("**Output**")
            st.write(trace.output_text or "*(empty)*")

            tool_calls = json.loads(trace.tool_calls_json) if isinstance(trace.tool_calls_json, str) else trace.tool_calls_json
            if tool_calls:
                st.markdown("**Tool calls**")
                st.table(
                    [{"name": tc.get("name"), "args": tc.get("args"), "result": tc.get("result_summary")} for tc in tool_calls]
                )

            sources = json.loads(trace.sources_json) if isinstance(trace.sources_json, str) else trace.sources_json
            if sources:
                st.markdown("**Sources**")
                st.table(
                    [{"source": s.get("source"), "score": s.get("score"), "content": (s.get("content") or "")[:200]} for s in sources]
                )

            scores = data.get_scores_for_trace(engine, trace.trace_id)
            if not scores.empty:
                st.markdown("**Scores**")
                for score in scores.itertuples():
                    passed_str = "—" if score.passed is None else ("✅" if score.passed else "❌")
                    st.write(f"{passed_str} **{score.metric_name}**: {score.score:.2f} — {score.rationale}")
