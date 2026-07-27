"""The AgentUnderTest contract.

Deliberately thin and imperative: one run() call that always returns a fully
materialized AgentTrace. Adapters own all the messiness of their target
agent internally (draining generators, running async event loops, capturing
tool-call events) — the harness never assumes a shared execution model
underneath, only a shared *output* model. This is what lets a single-shot
LangGraph function, a stateful async multi-turn ADK agent, and a RAG chain
needing externally-built dependencies all satisfy the same interface without
distorting any of them.

A Protocol (structural typing), not a required base class: adapters live in
agentsentinel/adapters/, import the target repo as a dependency, and wrap it
without requiring any change to the target repo's source.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from agentsentinel.core.models import AgentTrace, RunContext, TestCase


@runtime_checkable
class AgentUnderTest(Protocol):
    name: str
    version: str

    def setup(self, ctx: RunContext) -> None:
        """Called once per suite run. Build expensive shared deps here
        (vector stores, LLM clients, ADK Runner/session service). Must be
        safe to call exactly once per RunContext."""
        ...

    def run(self, case: TestCase, ctx: RunContext) -> AgentTrace:
        """Execute the agent against one test case. MUST NOT raise on
        agent-side failure — catch and encode as AgentTrace(error=...) so
        one bad case doesn't kill the whole suite."""
        ...

    def teardown(self, ctx: RunContext) -> None:
        """Release resources (subprocess handles, DB connections, etc.)."""
        ...
