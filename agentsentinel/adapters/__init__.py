"""Registry of adapters the CLI can run by name. Real adapters
(langgraph_research, rag_chatbot, adk_stock_agent) get added here as they're
built in Phase 1 — each requires its target repo installed as a dependency,
so importing them eagerly here would break `agentsentinel run --agent toy`
in an environment that doesn't have those repos. Import lazily instead.
"""
from __future__ import annotations

from typing import Callable

from agentsentinel.core.interfaces import AgentUnderTest

_ADAPTER_FACTORIES: dict[str, Callable[[], AgentUnderTest]] = {}


def _register_toy_agent():
    from agentsentinel.adapters.toy_agent import ToyAgentAdapter

    return ToyAgentAdapter()


def _register_langgraph_research():
    from agentsentinel.adapters.langgraph_research import LangGraphResearchAdapter

    return LangGraphResearchAdapter()


def _register_rag_chatbot():
    from agentsentinel.adapters.rag_chatbot import RagChatbotAdapter

    return RagChatbotAdapter()


def _register_adk_stock_agent():
    from agentsentinel.adapters.adk_stock_agent import AdkStockAgentAdapter

    return AdkStockAgentAdapter()


_ADAPTER_FACTORIES["toy-agent"] = _register_toy_agent
_ADAPTER_FACTORIES["research-pipeline-langgraph"] = _register_langgraph_research
_ADAPTER_FACTORIES["rag-chatbot-langchain"] = _register_rag_chatbot
_ADAPTER_FACTORIES["stock-analysis-adk"] = _register_adk_stock_agent


def build_adapter(name: str) -> AgentUnderTest:
    if name not in _ADAPTER_FACTORIES:
        available = ", ".join(sorted(_ADAPTER_FACTORIES))
        raise KeyError(f"Unknown adapter '{name}'. Available: {available}")
    return _ADAPTER_FACTORIES[name]()


def available_adapters() -> list[str]:
    return sorted(_ADAPTER_FACTORIES)
