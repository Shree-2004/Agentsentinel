"""Generic shim for simple, function-based agents — the "no custom Python
needed" path described in docs/bring_your_own_agent.md. Unlike the other
three shims (which are bespoke, one per target, handling that target's
specific quirks), this ONE script handles any agent shaped like:

    result = some_function(input_text)

where the result is either a plain string, or a dict with the answer under
a named key. That covers a large fraction of real agents; anything more
exotic (async, multi-turn, tool-calling, needing pre-built dependencies
passed in) still needs a bespoke adapter — see adding_an_adapter.md for
that path. This file has zero dependency on the agentsentinel package
(same reason as every other shim: it runs under the TARGET's interpreter,
which never has agentsentinel installed).

Protocol (same sentinel-line convention as every other shim, but the input
payload carries an extra "config" key this shim actually needs, since it
has no built-in knowledge of the target the way the bespoke shims do):

{
  "input_text": "...",
  "config": {
    "repo_path": "/abs/path/to/target/repo",
    "module": "app.main",              # importable module path
    "function": "run",                  # function name within that module
    "output_style": "string" | "dict",
    "output_field": "answer",           # required only if output_style == "dict"
    "dotenv": true                       # whether to load repo_path/.env first
  }
}
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path


def main() -> None:
    payload = json.loads(sys.stdin.read())
    config = payload["config"]
    repo_path = Path(config["repo_path"])

    sys.path.insert(0, str(repo_path))

    if config.get("dotenv"):
        try:
            from dotenv import load_dotenv

            load_dotenv(dotenv_path=repo_path / ".env")
        except ImportError:
            pass  # target has no python-dotenv installed and no .env to load - fine

    try:
        module = importlib.import_module(config["module"])
        func = getattr(module, config["function"])
        result = func(payload["input_text"])

        output_style = config.get("output_style", "string")
        if output_style == "string":
            output_text = str(result)
        elif output_style == "dict":
            output_text = str(result[config["output_field"]])
        else:
            raise ValueError(f"Unknown output_style: {output_style!r} (expected 'string' or 'dict')")

    except Exception as exc:  # noqa: BLE001 - report to parent, don't crash silently
        _emit({"error": f"{type(exc).__name__}: {exc}"})
        return

    _emit({"output_text": output_text, "tool_calls": [], "sources": [], "raw_output": None})


def _emit(result: dict) -> None:
    print(f"AGENTSENTINEL_RESULT:{json.dumps(result)}")


if __name__ == "__main__":
    main()
