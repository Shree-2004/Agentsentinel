"""Runs under the Multi-Agent Research Assistant's OWN venv interpreter —
this file has zero import dependency on the agentsentinel package itself
(stdlib only), since the venv running it never has agentsentinel installed.

Protocol: reads {"input_text": ..., "multi_turn": ...} as JSON from stdin,
prints exactly one line prefixed with AGENTSENTINEL_RESULT: containing the
JSON result (or {"error": "..."} on failure) as the LAST line of stdout.
The target pipeline prints its own progress lines throughout — those are
expected and ignored by the parent process, which only reads the last
sentinel-prefixed line.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# agentsentinel/agentsentinel/adapters/shims/ -> GITHUB proj/
REPO_PATH = Path(__file__).resolve().parents[4] / "Multi-Agent Research Assistant"


def main() -> None:
    payload = json.loads(sys.stdin.read())

    sys.path.insert(0, str(REPO_PATH))
    from dotenv import load_dotenv

    # The target's own entrypoints (app.py, graph/pipeline.py) call
    # load_dotenv() *after* importing agents.researcher, which reads
    # TAVILY_API_KEY at module import time — so .env must be loaded before
    # that import happens, in a fresh interpreter, regardless of what the
    # target's own module-level ordering does.
    load_dotenv(dotenv_path=REPO_PATH / ".env")

    from graph.pipeline import run_pipeline

    try:
        final_state: dict = run_pipeline(payload["input_text"])
    except Exception as exc:  # noqa: BLE001 - report to parent, don't crash silently
        _emit({"error": f"{type(exc).__name__}: {exc}"})
        return

    sources = [
        {"content": s.get("abstract", ""), "source": s.get("url", ""), "label": s.get("title")}
        for s in final_state.get("raw_sources", [])
    ]
    # No per-tool visibility into a compiled StateGraph from the outside, so
    # the whole graph execution is recorded as one synthetic call.
    tool_calls = [
        {
            "name": "graph_execution",
            "args": {"topic": payload["input_text"]},
            "result_summary": f"{final_state.get('iteration_count', 0)} reflection iterations",
        }
    ]

    _emit(
        {
            "output_text": final_state.get("final_report") or final_state.get("draft_report") or "",
            "tool_calls": tool_calls,
            "sources": sources,
            "raw_output": {"iteration_count": final_state.get("iteration_count")},
        }
    )


def _emit(result: dict) -> None:
    print(f"AGENTSENTINEL_RESULT:{json.dumps(result)}")


if __name__ == "__main__":
    main()
