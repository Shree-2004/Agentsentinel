# Adding a new agent to AgentSentinel

This walks through wiring up a *fourth* (or fifth, or tenth) agent — any
repo, any framework — so AgentSentinel can evaluate it the same way it
already evaluates the three in this portfolio. Concrete, copy-adjustable
steps, using the real `langgraph_research.py` adapter as the reference
example throughout.

## Step 0: decide if you need subprocess isolation

Almost always: **yes**. The reason AgentSentinel exists as a subprocess
harness at all is that real agent repos pin conflicting dependency versions
(see `docs/architecture.md`'s "Why real adapters run their target in a
subprocess" section — the LangGraph repo and RAG chatbot repo can't share
one Python environment). Unless your new agent has *zero* third-party
dependencies (like the built-in `toy_agent.py`), assume you need isolation.

## Step 1: figure out the target's real entrypoint

Read the target repo's actual code — not just its README — to find how it's
really invoked. This matters because READMEs lie (see the MCP-bypass finding
in `docs/architecture.md`: finance-agent's README describes an MCP server
its real code never calls). Concretely, answer:

- Is it a plain function (`run_pipeline(topic) -> dict`, like LangGraph)?
  A class with pre-built dependencies passed in (like the RAG chatbot's
  `ask(question, vector_store, llm, chat_history)`)? An async multi-turn
  runner (like ADK's `Runner.run_async(...)`)?
- Does it need a `.env` loaded, and does the *order* of its own imports
  matter? (The LangGraph repo has a real bug here — see
  `shims/langgraph_research_shim.py`'s docstring — where `.env` needs
  loading before a specific import or a tool's API key check fails.)
- Does it hard-code a model name that might be stale? Check for this
  explicitly — it's bitten two of the three existing adapters
  (`gemini-1.5-flash` retired in both the RAG chatbot and finance-agent
  repos).

## Step 2: does the target have its own venv?

Check for one. If it does (like the LangGraph and finance-agent repos),
your adapter just points at it (`venv_utils.venv_python_path`). If it
doesn't (like the RAG chatbot repo originally didn't), your adapter can
auto-create one on first use via `venv_utils.ensure_venv` — see
`adapters/rag_chatbot.py`'s `setup()` for the pattern.

**Real gotcha to expect**: a target repo's own `requirements.txt` may be
internally self-conflicting or just wrong (this happened with the RAG
chatbot repo — see its commit history). If a plain `pip install -r
requirements.txt` fails with a resolver conflict, try installing with loose
version ranges or `--no-deps` plus the handful of real direct dependencies,
rather than fighting the exact pins.

## Step 3: write the shim

The shim is a **standalone script with zero import dependency on the
`agentsentinel` package** — it runs under the *target's* interpreter, which
never has `agentsentinel` installed. It follows one protocol:

- Reads one JSON object from stdin: `{"input_text": ..., "multi_turn": ...,
  "case_id": ..., "tags": [...]}`
- Does whatever importing/calling the target needs
- Prints **exactly one line**, prefixed `AGENTSENTINEL_RESULT:`, containing
  JSON: `{"output_text": ..., "tool_calls": [...], "sources": [...],
  "raw_output": ...}` on success, or `{"error": "..."}` on failure
- That line must be the **last** line of stdout — the target's own prints
  (progress bars, debug logs — all three existing targets print freely) are
  ignored by the parent, which only looks at the last `AGENTSENTINEL_RESULT:`
  line

Minimal skeleton (adapt from `shims/langgraph_research_shim.py`, the
simplest of the three real ones):

```python
from __future__ import annotations
import json, sys
from pathlib import Path

REPO_PATH = Path(__file__).resolve().parents[4] / "Your Target Repo Name"

def main() -> None:
    payload = json.loads(sys.stdin.read())
    sys.path.insert(0, str(REPO_PATH))

    from dotenv import load_dotenv
    load_dotenv(dotenv_path=REPO_PATH / ".env")  # load BEFORE importing the target's own modules

    from your_target_module import run_your_agent  # the real entrypoint from Step 1

    try:
        result = run_your_agent(payload["input_text"])
    except Exception as exc:
        print(f"AGENTSENTINEL_RESULT:{json.dumps({'error': f'{type(exc).__name__}: {exc}'})}")
        return

    print(f"AGENTSENTINEL_RESULT:{json.dumps({
        'output_text': result.get('answer', ''),
        'tool_calls': [],   # populate if the target exposes tool/function calls
        'sources': [],      # populate if the target does retrieval
        'raw_output': None, # debugging escape hatch, kept untyped on purpose
    })}")

if __name__ == "__main__":
    main()
```

**Test the shim standalone before wiring the adapter class** — this is the
cheapest place to catch import errors, and it's how every real adapter in
this repo got debugged:
```bash
cd "path/to/your/target/repo"
echo '{"input_text": "a real test query", "multi_turn": false}' | venv/Scripts/python.exe "path/to/agentsentinel/agentsentinel/adapters/shims/your_shim.py"
```
You should see the target's own progress output, then one line starting
`AGENTSENTINEL_RESULT:{...}`.

## Step 4: write the adapter class

Thin — it just tells `SubprocessAgentAdapter` where the venv and shim are:

```python
from __future__ import annotations
import os
from pathlib import Path
from agentsentinel.adapters.subprocess_base import SubprocessAgentAdapter
from agentsentinel.adapters.venv_utils import venv_python_path
from agentsentinel.core.models import RunContext

_DEFAULT_REPO_PATH = Path(__file__).resolve().parents[3] / "Your Target Repo Name"

class YourAgentAdapter(SubprocessAgentAdapter):
    name = "your-agent-name"       # this is the --agent value on the CLI
    version = "0.1.0"
    timeout_s = 120.0               # generous - real agents take longer than you expect

    def __init__(self, repo_path: str | Path | None = None):
        self._repo_path = Path(repo_path or os.environ.get("AGENTSENTINEL_YOURAGENT_REPO_PATH", _DEFAULT_REPO_PATH))
        self.venv_python = venv_python_path(self._repo_path)
        self.shim_path = Path(__file__).parent / "shims" / "your_agent_shim.py"

    def setup(self, ctx: RunContext) -> None:
        if not self.venv_python.exists():
            raise FileNotFoundError(f"No venv found at {self.venv_python}.")
```

## Step 5: register it

One line in `agentsentinel/adapters/__init__.py` — follow the existing
pattern (lazy import inside a factory function, so importing this module
doesn't require the new target's dependencies to be installed unless
someone actually selects `--agent your-agent-name`):

```python
def _register_your_agent():
    from agentsentinel.adapters.your_agent import YourAgentAdapter
    return YourAgentAdapter()

_ADAPTER_FACTORIES["your-agent-name"] = _register_your_agent
```

## Step 6: write seed test cases

`agentsentinel/testcases/seed/your_agent.yaml` — see any existing seed file
for the schema. Start with 1-2 `normal` cases and 1 `edge_case`; add
`adversarial_injection` cases once the normal ones pass reliably (don't try
to test resistance to an attack you haven't confirmed the agent can even
answer normally first — see how `adk-003-injection` needed two attempts
just to reach the point where an attack was even possible to deliver).

## Step 7: run it

```bash
python -m agentsentinel.cli run --agent your-agent-name
```
Read `AgentTrace.error` on any failures (the CLI surfaces this directly in
the scorecard output) before assuming a scorer is wrong — most early
failures are import/environment issues, not scoring bugs.

## Common pitfalls (all real, all hit while building the first three)

- **Windows console encoding**: if the target prints emoji/unicode and you're
  testing the shim standalone (not through the CLI), you'll get a
  `UnicodeEncodeError` that has nothing to do with your adapter logic. The
  CLI already forces UTF-8; a one-off debugging script needs
  `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")` too.
- **`numpy.float32` (or similar) isn't JSON-serializable** — if the target
  returns similarity scores, tensor values, etc., cast to native Python
  types (`float(x)`) before building the result dict. This broke the RAG
  chatbot shim once already.
- **Retired/renamed models** — check every hard-coded model string in the
  target repo before your first live run, not after a confusing API error.
- **Don't assume a "full" query reaches every sub-agent** — for multi-agent
  systems with LLM-driven delegation (like ADK's `transfer_to_agent`), the
  root agent may not reliably complete its own documented pipeline for a
  given phrasing. Verify with a real trace before trusting a test case that
  depends on a specific agent being reached.
