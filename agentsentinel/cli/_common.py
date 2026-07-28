"""Shared between `run` and `gate` — both execute a suite and save it the
same way; `gate` additionally runs a regression check afterward.
"""
from __future__ import annotations

from agentsentinel.adapters import build_adapter
from agentsentinel.core.models import Scorecard, AgentTrace
from agentsentinel.runner.suite_runner import run_suite
from agentsentinel.scoring.registry import get_scorers
from agentsentinel.storage.db import get_engine, save_full_run
from agentsentinel.testcases.external_config import load_external_config
from agentsentinel.testcases.loader import load_seed_cases

# Scorers that never call an LLM judge — safe to run with zero extra deps
# and zero API cost, appropriate for a fast per-PR gate (see
# docs/architecture.md's "fast/deterministic vs nightly/full" split).
# LLM-judge scorers (faithfulness, injection_resistance) are opt-in via
# --scorers so a bare `run`/`gate` never silently starts requiring a
# GOOGLE_API_KEY just because a new judge scorer got registered.
DETERMINISTIC_SCORERS = ["keyword_match", "latency", "tool_call_correctness"]


def resolve_scorer_names(scorers: str | None) -> list[str] | None:
    if scorers is None:
        return DETERMINISTIC_SCORERS
    if scorers == "all":
        return None  # get_scorers(None) returns everything
    return [s.strip() for s in scorers.split(",")]


def execute_and_save(
    agent_name: str | None, db_path: str | None, scorers: str | None, config_path: str | None = None
) -> tuple[Scorecard, list[AgentTrace], object]:
    """Runs a suite and persists it, returning (scorecard, traces, engine) —
    engine is returned so callers (gate) can run a regression check against
    the same database without reopening it.

    Two ways to specify what to run, mutually exclusive:
    - agent_name: one of the built-in adapters, cases from testcases/seed/
    - config_path: a "bring your own agent" YAML (see
      testcases/external_config.py) bundling both the agent connection info
      and its cases in one file — for agents that don't have a hand-written
      adapter in this repo.
    """
    if config_path:
        agent, cases = load_external_config(config_path)
    else:
        agent = build_adapter(agent_name)
        cases = load_seed_cases(agent_target=agent_name)

    if not cases:
        raise ValueError(f"No test cases found for agent '{agent_name or config_path}'.")

    scorer_list = get_scorers(resolve_scorer_names(scorers))
    scorecard, traces = run_suite(agent, cases, scorer_list)

    engine = get_engine(db_path)
    save_full_run(engine, scorecard, traces)

    return scorecard, traces, engine
