"""Shared LLM-judge client. Deliberately independent of whichever model any
target agent uses — the LangGraph, RAG chatbot, and ADK agents in this
portfolio all use Gemini too, but via three separate .env files in three
separate repos/venvs. The judge is AgentSentinel's own dependency, running
in-process in the harness's own venv (unlike target agents, which run in
their own isolated subprocess — see adapters/subprocess_base.py), so it
needs its OWN .env with its own GOOGLE_API_KEY, set up via `pip install -e
".[judge]"` and a `.env` at the AgentSentinel repo root.

Default model is gemini-2.5-flash, not gemini-1.5-flash — the latter is the
retired model that broke two of the three target repos during Phase 1
(see docs/architecture.md); worth not repeating that mistake here.
"""
from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_MODEL = "gemini-2.5-flash"
_REPO_ROOT = Path(__file__).resolve().parents[2]  # agentsentinel/agentsentinel/scoring/ -> agentsentinel/


def _load_own_env() -> None:
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=_REPO_ROOT / ".env")


class JudgeLLM:
    def __init__(self, model: str | None = None, api_key: str | None = None):
        _load_own_env()
        from google import genai

        self.model = model or os.environ.get("AGENTSENTINEL_JUDGE_MODEL", _DEFAULT_MODEL)
        key = api_key or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError(
                "No GOOGLE_API_KEY found for the judge LLM. Set it in a .env file at the "
                "AgentSentinel repo root (separate from any target agent's own .env)."
            )
        self._client = genai.Client(api_key=key)

    def complete(self, prompt: str) -> str:
        response = self._client.models.generate_content(model=self.model, contents=prompt)
        return (response.text or "").strip()


_default_judge: JudgeLLM | None = None


def get_default_judge() -> JudgeLLM:
    """Lazily constructed singleton so importing scoring.faithfulness etc.
    doesn't require GOOGLE_API_KEY to be set unless a judge scorer actually
    runs (keeps `agentsentinel run --agent toy-agent` dependency-free)."""
    global _default_judge
    if _default_judge is None:
        _default_judge = JudgeLLM()
    return _default_judge
