"""Runs under the finance-agent's OWN venv interpreter — stdlib + target
repo imports only (see subprocess_base.py for why: no dependency on the
agentsentinel package in that venv).

Important, documented finding: despite the target repo's README describing
a "custom MCP server exposing Yahoo Finance as callable tools" as its
headline feature, the actual live agent path (root_agent.py -> sub_agents)
does NOT go through that MCP server at all. Each sub-agent wraps the
underlying tools/*.py functions directly with ADK's `FunctionTool` -
`mcp_server/server.py` and its `@mcp.tool()` wrappers exist in the repo but
are never invoked by anything `main.py` calls. This adapter tests what
actually runs (the FunctionTool-based agent), not the unused MCP path. See
docs/architecture.md for how this changes the injection-testing plan for
Phase 2.

Protocol: reads {"input_text": ...} from stdin, prints exactly one line
prefixed AGENTSENTINEL_RESULT: with the JSON result (or {"error": ...}) as
the LAST line of stdout - same convention as the other two shims.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# agentsentinel/agentsentinel/adapters/shims/ -> GITHUB proj/
REPO_PATH = Path(__file__).resolve().parents[4] / "finance-agent"

# The four LlmAgent() calls (root + 3 sub-agents) all hard-code
# model="gemini-1.5-flash", which Google has since retired (same issue
# found in the RAG chatbot repo). There's no shared config module here to
# patch, so instead: build the agents normally, then walk the tree and
# reassign the .model attribute on each before running - flagged here
# rather than silently masked, and not fixed in the target repo since
# that's a separate decision for the repo owner.
WORKING_MODEL = "gemini-2.5-flash"


def main() -> None:
    payload = json.loads(sys.stdin.read())

    sys.path.insert(0, str(REPO_PATH))
    sys.path.insert(0, str(REPO_PATH / "mcp_server"))  # matches root_agent.py's own sys.path pattern
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=REPO_PATH / ".env")

    from agents.root_agent import build_root_agent

    try:
        root_agent = build_root_agent()
        root_agent.model = WORKING_MODEL
        for sub_agent in root_agent.sub_agents:
            sub_agent.model = WORKING_MODEL

        result = asyncio.run(_run_agent(root_agent, payload["input_text"]))
    except Exception as exc:  # noqa: BLE001 - report to parent, don't crash silently
        _emit({"error": f"{type(exc).__name__}: {exc}"})
        return

    _emit(result)


async def _run_agent(root_agent, input_text: str) -> dict:
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai.types import Content, Part

    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name="agentsentinel", user_id="agentsentinel")
    runner = Runner(agent=root_agent, app_name="agentsentinel", session_service=session_service)

    message = Content(parts=[Part(text=input_text)])

    tool_calls: list[dict] = []
    output_text = ""

    async for event in runner.run_async(user_id="agentsentinel", session_id=session.id, new_message=message):
        if not event.content:
            continue
        for part in event.content.parts:
            if getattr(part, "function_call", None):
                tool_calls.append({"name": part.function_call.name, "args": dict(part.function_call.args or {})})
            if getattr(part, "function_response", None) and tool_calls:
                # pair the response with the most recent matching call by name
                for call in reversed(tool_calls):
                    if call["name"] == part.function_response.name and call.get("result_summary") is None:
                        call["result_summary"] = str(part.function_response.response)[:2000]
                        break
        if event.is_final_response() and event.content:
            for part in event.content.parts:
                if getattr(part, "text", None):
                    output_text += part.text

    return {
        "output_text": output_text,
        "tool_calls": tool_calls,
        "sources": [],  # this agent has no retrieval/citation concept - tool_calls carry the provenance instead
        "raw_output": {"tool_call_count": len(tool_calls)},
    }


def _emit(result: dict) -> None:
    print(f"AGENTSENTINEL_RESULT:{json.dumps(result)}")


if __name__ == "__main__":
    main()
