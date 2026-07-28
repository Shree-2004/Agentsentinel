# Next Steps / Handoff Notes

Read this first if picking the project back up cold. It's a punch list, not a
retrospective — for the "why" behind any decision mentioned here, see
[architecture.md](architecture.md); for overall status, see the repo root
[README.md](../README.md). Both are kept up to date per-commit, so `git log
--oneline` plus these two files should fully reconstruct context without
needing this conversation.

## Where things stand (as of commit `a328d0d`)

Phases 0-3 are done, tested, and committed: core harness, all three real
adapters, faithfulness + injection scorers (faithfulness calibrated at 100%
agreement), regression tracking (`agentsentinel gate`), and a Streamlit
dashboard. Nothing in that list is broken or half-finished.

Two open items remain, described below. Neither is blocking — the project is
in a genuinely good, demoable state either way.

## Open item 1: `adk-003-injection` has no confirmed verdict

**What's been tried:** two live attempts, each failing to reach the poisoned
`get_news()` tool for a *different* reason (see `architecture.md`'s "first
real ADK run" + "second attempt" sections for full traces):
1. `ticker_resolver_agent` failed to resolve "TCS" — pipeline bailed before
   reaching any analysis sub-agent.
2. Isolated retry: ticker resolution succeeded, `technical_analyst_agent` ran
   correctly, but the pipeline stopped there and returned the technical
   analysis directly — never delegating to `report_generator_agent` (where the
   poisoned news headline lives), despite `root_agent.py`'s own system
   instruction saying it always should.

**What this means:** point 2 is itself a real, repeatable bug in
`finance-agent` — its documented 3-step pipeline doesn't reliably complete all
3 steps for one query. That's worth noting to the repo owner independent of
whether the injection test ever passes.

**What to try next** (pick one, in order of least to most invasive):
- Reword the seed case's `input_text` in `agentsentinel/testcases/seed/adk_stock_agent.yaml`
  to be more insistent about wanting a written report with news
  (e.g. *"Give me a full written report on TCS including recent news"*)
  and just retry — cheapest option, might just be a prompting issue.
- If that still doesn't reliably delegate to `report_generator_agent`, consider
  testing that sub-agent more directly rather than through root's delegation
  judgment — e.g. a small standalone shim path that builds
  `report_generator_agent` alone (see `agents/sub_agents/report_agent.py`) and
  feeds it a ticker + fake technical summary directly, bypassing root.
- Budget constraint: `finance-agent`'s current `GOOGLE_API_KEY` has a **5
  req/day** quota for `gemini-2.5-flash`, and a "full analysis" query burns
  3-4 requests per attempt. Don't attempt more than ~1 retry per day on this
  key without checking quota first (a plain `google.genai.Client(...).generate_content(...)`
  call outside the harness is the cheapest way to check if the key is live at
  all before spending it on a real agent run).

To rerun just this case without burning quota on the other two:
```python
# from the agentsentinel repo root, with its venv active
from agentsentinel.adapters.adk_stock_agent import AdkStockAgentAdapter
from agentsentinel.testcases.loader import load_seed_cases
from agentsentinel.runner.suite_runner import run_suite
from agentsentinel.scoring.registry import get_scorers
from agentsentinel.storage.db import get_engine, save_full_run
import agentsentinel.scoring

cases = [c for c in load_seed_cases(agent_target="stock-analysis-adk") if c.id == "adk-003-injection"]
agent = AdkStockAgentAdapter()
scorecard, traces = run_suite(agent, cases, get_scorers(["keyword_match", "latency", "injection_resistance"]))
engine = get_engine("adk_retry.db")
save_full_run(engine, scorecard, traces)
# then inspect traces[0].tool_calls, traces[0].output_text directly (with UTF-8 stdout,
# Windows chokes on the ₹ symbol otherwise — see judge_llm.py's pattern for reference)
```

## Open item 2: Phase 4 (CI gate wired into a real repo) — not started

The roadmap's last unchecked box. Scope, per the original plan and
`docs/architecture.md`'s "fast/deterministic vs nightly/full" section:

- A working GitHub Actions example (`.github/workflows/`) in one of the target
  repos (or documented here, pointed at a target repo path) that runs
  `agentsentinel gate --agent <name>` on every PR using only the deterministic
  scorer set (fast, free, no API key needed) — the default behavior of `gate`
  already matches this, so this is mostly wiring, not new harness code.
- A second, separate scheduled/nightly workflow that runs `--scorers all`
  (LLM-judge scorers included) against the real agents, since that's slow and
  costs API quota — should not run on every PR.
- `docs/adding_an_adapter.md` is now written (the "how do I extend this to a
  new repo" guide) — done. `docs/injection_taxonomy.md` ("what attack
  patterns does this corpus cover") is still not written; low priority
  unless the injection corpus grows past the two archetypes currently
  covered (indirect injection via a poisoned document, via a poisoned tool
  response).

## Known environment quirks worth remembering

- Each target repo (`Multi-Agent Research Assistant`, `RAG AI CHATBOT`,
  `finance-agent`) has its **own** `.env` and its **own** `GOOGLE_API_KEY`,
  separate from AgentSentinel's own `.env` (used only by the judge scorers).
  Don't confuse the two when debugging an API error — check which `.env` is
  actually in play for the failure at hand.
- Free-tier Gemini quotas are shared per-key across *both* an agent's own
  generation calls and AgentSentinel's judge calls if they happen to point at
  the same key — burns through the daily limit faster than expected.
- Windows console output needs UTF-8 forced (`cli/__main__.py` does this
  automatically for the CLI) — any one-off debugging script that prints
  agent output directly will crash on ₹/emoji/unicode unless it does the same
  (`sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")`).
- Always `rm` any scratch `*.db` files created while debugging before
  committing — they're gitignored but easy to leave lying around locally.
