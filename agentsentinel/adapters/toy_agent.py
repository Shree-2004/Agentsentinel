"""A trivial, dependency-free agent used only to prove the harness itself
(interfaces -> runner -> scoring -> storage) end-to-end without needing any
of the three real portfolio repos wired up. Real adapters (langgraph_research,
rag_chatbot, adk_stock_agent) follow the same shape once the harness is
trusted — see docs/adding_an_adapter.md.

Behavior is intentionally simple and deterministic: a tiny fixed keyword ->
answer knowledge base, so tests never depend on network calls or an LLM.
"""
from __future__ import annotations

from agentsentinel.adapters.base import BaseAgentAdapter
from agentsentinel.core.models import AgentTrace, RunContext, SourceRef, TestCase, ToolCall

_KNOWLEDGE_BASE = {
    "capital of france": ("Paris is the capital of France.", "geo-facts.md"),
    "speed of light": ("The speed of light in a vacuum is about 299,792 km/s.", "physics-facts.md"),
}


class ToyAgentAdapter(BaseAgentAdapter):
    name = "toy-agent"
    version = "0.1.0"

    def _invoke(self, case: TestCase, ctx: RunContext) -> AgentTrace:
        query = case.input_text.strip().lower()

        match_key = next((k for k in _KNOWLEDGE_BASE if k in query), None)
        tool_calls = [
            ToolCall(name="keyword_search", args={"query": query}, result_summary=match_key or "no match")
        ]

        if match_key is None:
            return AgentTrace(
                test_case_id=case.id,
                agent_name=self.name,
                output_text="I don't know.",
                tool_calls=tool_calls,
                sources=[],
            )

        answer, doc = _KNOWLEDGE_BASE[match_key]
        return AgentTrace(
            test_case_id=case.id,
            agent_name=self.name,
            output_text=answer,
            tool_calls=tool_calls,
            sources=[SourceRef(content=answer, source=doc, label=match_key)],
        )
