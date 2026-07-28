"""Shared between `run` and `gate` — both execute a suite and save it the
same way; `gate` additionally runs a regression check afterward.
"""
from __future__ import annotations

from agentsentinel.adapters import build_adapter
from agentsentinel.core.models import Scorecard, AgentTrace
from agentsentinel.runner.suite_runner import run_suite
from agentsentinel.scoring.registry import get_scorers
from agentsentinel.storage.db import get_engine, save_full_run
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
    agent_name: str, db_path: str | None, scorers: str | None
) -> tuple[Scorecard, list[AgentTrace], object]:
    """Runs the seed suite for `agent_name`, persists it, and returns
    (scorecard, traces, engine) — engine is returned so callers (gate) can
    run a regression check against the same database without reopening it."""
    agent = build_adapter(agent_name)
    cases = load_seed_cases(agent_target=agent_name)
    if not cases:
        raise ValueError(f"No seed test cases found for agent '{agent_name}'.")

    scorer_list = get_scorers(resolve_scorer_names(scorers))
    scorecard, traces = run_suite(agent, cases, scorer_list)

    engine = get_engine(db_path)
    save_full_run(engine, scorecard, traces)

    return scorecard, traces, engine
