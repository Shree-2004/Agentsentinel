"""Adapter for the finance-agent (Google ADK multi-agent stock analysis
system). Runs via subprocess isolation (see subprocess_base.py) using the
target repo's own existing venv.

This is the hardest of the three real adapters: the target is async,
multi-turn, and tool-calling, owned by ADK's own `Runner`/session
machinery - there's no single function to call the way there is for the
LangGraph pipeline. The actual event-stream draining and tool-call capture
happens in shims/adk_stock_agent_shim.py, executed under the target's
interpreter.

Documented finding (see the shim's docstring and docs/architecture.md for
detail): the target repo's README advertises a custom MCP server as its
headline feature, but the live agent path never actually calls it - each
sub-agent uses ADK's FunctionTool directly against local Python functions.
This adapter tests what actually runs.
"""
from __future__ import annotations

import os
from pathlib import Path

from agentsentinel.adapters.subprocess_base import SubprocessAgentAdapter
from agentsentinel.adapters.venv_utils import venv_python_path
from agentsentinel.core.models import RunContext

_DEFAULT_REPO_PATH = Path(__file__).resolve().parents[3] / "finance-agent"


class AdkStockAgentAdapter(SubprocessAgentAdapter):
    name = "stock-analysis-adk"
    version = "0.1.0"
    timeout_s = 180.0

    def __init__(self, repo_path: str | Path | None = None):
        self._repo_path = Path(repo_path or os.environ.get("AGENTSENTINEL_FINANCE_REPO_PATH", _DEFAULT_REPO_PATH))
        self.venv_python = venv_python_path(self._repo_path)
        self.shim_path = Path(__file__).parent / "shims" / "adk_stock_agent_shim.py"

    def setup(self, ctx: RunContext) -> None:
        if not self.venv_python.exists():
            raise FileNotFoundError(
                f"No venv found at {self.venv_python}. This adapter expects the target repo to "
                f"already have one set up (`python -m venv venv` + `pip install -r requirements.txt` "
                f"inside {self._repo_path})."
            )
