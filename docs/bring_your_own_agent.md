# Bring your own agent (no code required)

The three adapters that ship with this repo (`langgraph_research.py`,
`rag_chatbot.py`, `adk_stock_agent.py`) are each hand-written for that
specific target's quirks — see `docs/adding_an_adapter.md` if you're
building one of those. This doc is the other path: **for a simple,
function-shaped agent, you don't need to write any Python at all.**

## When this works

Your agent qualifies if it can be called like this:
```python
result = some_function(input_text)
```
and `result` is either a plain string, or a dict with the answer under a
known key. That's it — no async, no multi-turn state, no pre-built
dependencies that need passing in.

If your agent is more complex than that (tool-calling, async, needs a
pre-built `vector_store`/`llm` object handed to it, etc.), this path won't
fit and you want `docs/adding_an_adapter.md` instead — there's no shame in
that, the ADK stock-analysis agent in this portfolio needed a real,
hand-written adapter for exactly this reason.

## The whole recipe

**One YAML file** does everything — agent connection info and test cases
together. See `examples/simple_agent/agentsentinel.yaml` for a complete,
runnable, real example (an ordinary function that's never seen
AgentSentinel before, evaluated with zero custom code):

```yaml
agent:
  name: my-agent                      # shows up as --agent's value everywhere
  repo_path: .                         # relative to THIS file's location, or absolute
  requirements_file: requirements.txt  # optional - only used if venv/ doesn't exist yet
  entrypoint:
    module: agent                     # importable module path (agent.py -> "agent")
    function: answer                  # the function name inside that module
  output_style: string                # "string" if it returns text directly,
  # output_field: answer              # or "dict" + which key holds the text
  dotenv: false                       # true to load repo_path/.env before importing

cases:
  - id: case-001
    category: normal
    input_text: "a real question your agent should answer"
    expected:
      must_contain: ["something the correct answer should contain"]
    source: curated
    notes: "why this case exists"
```

Then run it exactly like a built-in agent, just with `--config` instead of
`--agent`:
```bash
python -m agentsentinel.cli run --config path/to/your/agentsentinel.yaml
python -m agentsentinel.cli gate --config path/to/your/agentsentinel.yaml --db-path your_project.db
```

`--config` works everywhere `--agent` does — same scorers, same regression
gate, same dashboard (results land in whatever `--db-path` you point at, and
the dashboard reads any SQLite file the same way regardless of whether its
runs came from a built-in adapter or a config).

## What actually happens under the hood

`GenericAgentAdapter` (`agentsentinel/adapters/generic_agent.py`) reads your
config and, on first run, creates a venv for your repo if one doesn't
already exist (using `requirements_file`) — same `ensure_venv` helper the
RAG chatbot adapter uses. Every test case then spawns
`agentsentinel/adapters/shims/generic_shim.py` under *that* venv's
interpreter — one shim script, shared by every config-based agent, that
dynamically imports your module and calls your function. This is the same
subprocess-isolation architecture the three hand-written adapters use (see
`docs/architecture.md`), just with a generic shim instead of a bespoke one,
because a simple function-call agent doesn't need anything bespoke.

## Try it right now

The example in `examples/simple_agent/` is real and runnable, not just
illustrative:
```bash
python -m agentsentinel.cli run --config examples/simple_agent/agentsentinel.yaml
```
First run creates `examples/simple_agent/venv/` automatically (a few
seconds, since that example has zero real dependencies); every run after
that reuses it. `tests/test_bring_your_own_agent.py` runs this exact config
in CI, so it's a live-verified example, not a stale one.
