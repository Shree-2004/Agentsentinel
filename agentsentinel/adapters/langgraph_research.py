"""Adapter for the Multi-Agent Research Assistant (LangGraph, 4-agent
reflection pipeline). Runs via subprocess isolation (see subprocess_base.py)
using the target repo's own existing venv — its pinned langchain==0.2.16
conflicts with the RAG chatbot repo's langchain==0.3.7, so importing both
in-process is not viable.

The actual call to run_pipeline() happens in shims/langgraph_research_shim.py,
executed under the target repo's interpreter.
"""
from __future__ import annotations

import os
from pathlib import Path

from agentsentinel.adapters.subprocess_base import SubprocessAgentAdapter
from agentsentinel.adapters.venv_utils import venv_python_path
from agentsentinel.core.models import RunContext

# Sibling repo, two levels up from this file (agentsentinel/agentsentinel/adapters/ -> GITHUB proj/)
_DEFAULT_REPO_PATH = Path(__file__).resolve().parents[3] / "Multi-Agent Research Assistant"


class LangGraphResearchAdapter(SubprocessAgentAdapter):
    name = "research-pipeline-langgraph"
    version = "0.1.0"
    timeout_s = 240.0  # observed real runs: ~3-4 min with 2 reflection iterations

    def __init__(self, repo_path: str | Path | None = None):
        self._repo_path = Path(repo_path or os.environ.get("AGENTSENTINEL_RESEARCH_REPO_PATH", _DEFAULT_REPO_PATH))
        self.venv_python = venv_python_path(self._repo_path)
        self.shim_path = Path(__file__).parent / "shims" / "langgraph_research_shim.py"

    def setup(self, ctx: RunContext) -> None:
        if not self.venv_python.exists():
            raise FileNotFoundError(
                f"No venv found at {self.venv_python}. This adapter expects the target repo to "
                f"already have one set up (`python -m venv venv` + `pip install -r requirements.txt` "
                f"inside {self._repo_path})."
            )
