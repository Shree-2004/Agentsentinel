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


_ADAPTER_FACTORIES["toy-agent"] = _register_toy_agent


def build_adapter(name: str) -> AgentUnderTest:
    if name not in _ADAPTER_FACTORIES:
        available = ", ".join(sorted(_ADAPTER_FACTORIES))
        raise KeyError(f"Unknown adapter '{name}'. Available: {available}")
    return _ADAPTER_FACTORIES[name]()


def available_adapters() -> list[str]:
    return sorted(_ADAPTER_FACTORIES)
