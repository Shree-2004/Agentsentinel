"""Base class for adapters whose target agent runs in a separate, isolated
Python process instead of being imported in-process.

Why: target repos in this portfolio pin genuinely conflicting dependency
versions (e.g. the LangGraph research assistant pins langchain==0.2.16,
the RAG chatbot pins langchain==0.3.7 — a real major-version conflict, not
something resolvable by picking compatible pins). Importing both into one
shared interpreter is not viable and would silently break one adapter every
time another is installed. Each target instead keeps (or gets) its own venv,
and the harness talks to it as a subprocess over a small JSON protocol —
the harness's own dependencies (click, SQLAlchemy, rich, ...) never need to
coexist with any target's dependencies at all.

Protocol: the adapter writes {"input_text": ..., "multi_turn": ...} as JSON
to the shim's stdin. The shim (living in agentsentinel/adapters/shims/, run
under the TARGET's interpreter) does whatever importing/calling it needs
and prints exactly one line prefixed with "AGENTSENTINEL_RESULT:" containing
either {"output_text", "tool_calls", "sources", "raw_output"} on success or
{"error": "..."} on failure. Wrapped agents often print their own progress
lines (all three target repos in this portfolio do) — only the sentinel-
prefixed line is parsed as the result, so agent chatter on stdout is safely
ignored rather than corrupting the protocol.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from agentsentinel.adapters.base import BaseAgentAdapter
from agentsentinel.core.models import AgentTrace, RunContext, SourceRef, TestCase, ToolCall

RESULT_PREFIX = "AGENTSENTINEL_RESULT:"


class SubprocessAgentAdapter(BaseAgentAdapter):
    venv_python: Path
    shim_path: Path
    timeout_s: float = 300.0

    def _invoke(self, case: TestCase, ctx: RunContext) -> AgentTrace:
        if not self.venv_python.exists():
            return AgentTrace(
                test_case_id=case.id, agent_name=self.name, output_text="",
                error=(
                    f"No interpreter found at {self.venv_python}. "
                    f"Run this adapter's setup()/venv bootstrap first."
                ),
            )

        payload = json.dumps({"input_text": case.input_text, "multi_turn": case.multi_turn})
        # Wrapped agents print emoji/unicode progress lines (all three in
        # this portfolio do). Piped stdout on Windows defaults to the
        # console codepage rather than UTF-8, which crashes those prints
        # inside the child — force UTF-8 I/O for the child process itself.
        child_env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        try:
            proc = subprocess.run(
                [str(self.venv_python), str(self.shim_path)],
                input=payload,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_s,
                env=child_env,
            )
        except subprocess.TimeoutExpired as exc:
            return AgentTrace(
                test_case_id=case.id, agent_name=self.name, output_text="",
                error=f"Shim timed out after {self.timeout_s}s: {exc}",
            )

        result_line = self._extract_result_line(proc.stdout)
        if result_line is None:
            return AgentTrace(
                test_case_id=case.id, agent_name=self.name, output_text="",
                error=(
                    f"Shim produced no {RESULT_PREFIX} line (exit={proc.returncode}).\n"
                    f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
                ),
            )

        data = json.loads(result_line)
        if "error" in data:
            return AgentTrace(test_case_id=case.id, agent_name=self.name, output_text="", error=data["error"])

        return AgentTrace(
            test_case_id=case.id,
            agent_name=self.name,
            output_text=data.get("output_text", ""),
            tool_calls=[ToolCall(**tc) for tc in data.get("tool_calls", [])],
            sources=[SourceRef(**s) for s in data.get("sources", [])],
            raw_output=data.get("raw_output"),
        )

    @staticmethod
    def _extract_result_line(stdout: str) -> str | None:
        for line in reversed(stdout.splitlines()):
            if line.startswith(RESULT_PREFIX):
                return line[len(RESULT_PREFIX):]
        return None
