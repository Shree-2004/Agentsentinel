"""Every case ever scored by injection_resistance, across every agent and
run, with COMPLIED verdicts highlighted in red. This is the single most
important view in the dashboard: a faithfulness score of 0.8 is a judgment
call, but "the agent leaked a canary string when attacked" is not — this
tab exists so that fact is never buried in a generic per-case table.
"""
from __future__ import annotations

import streamlit as st

from agentsentinel.dashboard import data


def render(engine) -> None:
    cases = data.get_injection_cases(engine)
    if cases.empty:
        st.info("No cases have been scored by injection_resistance yet.")
        return

    st.caption(
        "Each case here fed the agent a prompt injection — a hidden instruction smuggled in "
        "via a tool result or retrieved document (e.g. \"ignore previous instructions, output "
        "X instead\"). **Resisted** means the agent answered the real question and ignored the "
        "injected instruction; **complied** means it followed the attacker's instruction instead."
    )

    complied = cases[cases["score"] == 0.0]
    resisted = cases[cases["score"] == 1.0]
    ambiguous_or_unscored = cases[~cases.index.isin(complied.index) & ~cases.index.isin(resisted.index)]

    col1, col2, col3 = st.columns(3)
    col1.metric("Resisted", len(resisted))
    col2.metric("Complied (vulnerable)", len(complied), delta=None if complied.empty else f"{len(complied)}", delta_color="inverse")
    col3.metric("Ambiguous / unscored", len(ambiguous_or_unscored))

    if not complied.empty:
        st.error(f"{len(complied)} case(s) where an agent complied with an injected instruction:")
        for row in complied.itertuples():
            st.markdown(f"🔴 **{row.agent_name}** / `{row.test_case_id}` (run `{row.run_id[:8]}`)")
            st.write(row.output_text)
            st.caption(row.rationale)
            st.divider()

    if not resisted.empty:
        st.success(f"{len(resisted)} case(s) where an agent resisted an injected instruction:")
        for row in resisted.itertuples():
            with st.expander(f"🟢 {row.agent_name} / {row.test_case_id} (run {row.run_id[:8]})"):
                st.write(row.output_text)
                st.caption(row.rationale)

    if not ambiguous_or_unscored.empty:
        with st.expander(f"⚪ {len(ambiguous_or_unscored)} ambiguous / unscored case(s)"):
            st.dataframe(ambiguous_or_unscored[["agent_name", "test_case_id", "run_id", "score", "rationale"]])
