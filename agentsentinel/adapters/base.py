"""Shared boilerplate for AgentUnderTest implementations: timing and
exception-to-error-trace conversion, so a single misbehaving adapter can't
crash the suite. Subclasses implement _invoke(); run() wraps it uniformly.
"""
from __future__ import annotations

import time
import traceback

from agentsentinel.core.models import AgentTrace, RunContext, TestCase


class BaseAgentAdapter:
    name: str = "unnamed-agent"
    version: str = "0.0.0"

    def setup(self, ctx: RunContext) -> None:
        pass

    def teardown(self, ctx: RunContext) -> None:
        pass

    def _invoke(self, case: TestCase, ctx: RunContext) -> AgentTrace:
        raise NotImplementedError

    def run(self, case: TestCase, ctx: RunContext) -> AgentTrace:
        start = time.perf_counter()
        try:
            trace = self._invoke(case, ctx)
            trace.latency_ms = (time.perf_counter() - start) * 1000
            return trace
        except Exception as exc:  # noqa: BLE001 - intentional: isolate one bad case
            return AgentTrace(
                test_case_id=case.id,
                agent_name=self.name,
                output_text="",
                latency_ms=(time.perf_counter() - start) * 1000,
                error=f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}",
            )
