"""Adapter for the RAG AI CHATBOT (LangChain, hybrid dense+BM25 retrieval,
confidence-gated generation). Runs via subprocess isolation (see
subprocess_base.py) in its own venv — its pinned langchain==0.3.7 conflicts
with the LangGraph research repo's langchain==0.2.16.

Unlike the LangGraph adapter, this target repo ships no venv of its own, so
setup() creates one on first use (agentsentinel/adapters/venv_utils.py) —
a one-time cost, idempotent on subsequent runs.

The actual call to ask() happens in shims/rag_chatbot_shim.py, executed
under the target repo's interpreter, against a small fixed fixture corpus
(testcases/fixtures/rag_corpus/) rather than a real uploaded PDF, so results
are reproducible.
"""
from __future__ import annotations

import os
from pathlib import Path

from agentsentinel.adapters.subprocess_base import SubprocessAgentAdapter
from agentsentinel.adapters.venv_utils import ensure_venv
from agentsentinel.core.models import RunContext

_DEFAULT_REPO_PATH = Path(__file__).resolve().parents[3] / "RAG AI CHATBOT"


class RagChatbotAdapter(SubprocessAgentAdapter):
    name = "rag-chatbot-langchain"
    version = "0.1.0"
    timeout_s = 120.0

    def __init__(self, repo_path: str | Path | None = None):
        self._repo_path = Path(repo_path or os.environ.get("AGENTSENTINEL_RAG_REPO_PATH", _DEFAULT_REPO_PATH))
        self.shim_path = Path(__file__).parent / "shims" / "rag_chatbot_shim.py"
        self.venv_python = None  # resolved in setup(), may need to bootstrap a venv first

    def setup(self, ctx: RunContext) -> None:
        self.venv_python = ensure_venv(self._repo_path)
