"""Regression detection: run the toy agent twice against the same DB (once
healthy, once with a deliberately patched-in wrong answer) and confirm
check_regressions() flags the drop, then confirm a subsequent healthy run
does NOT flag the recovery as a regression (only drops count, not gains).
"""
from __future__ import annotations

from unittest.mock import patch

import agentsentinel.scoring  # noqa: F401 - registers builtin scorers
from agentsentinel.adapters.toy_agent import ToyAgentAdapter, _KNOWLEDGE_BASE
from agentsentinel.runner.suite_runner import run_suite
from agentsentinel.scoring.registry import get_scorers
from agentsentinel.storage.db import get_engine, save_full_run
from agentsentinel.storage.regression import check_regressions
from agentsentinel.testcases.loader import load_seed_cases
from sqlalchemy.orm import Session


def _run_once(db_path: str):
    agent = ToyAgentAdapter()
    cases = load_seed_cases(agent_target="toy-agent")
    scorers = get_scorers(["keyword_match", "latency", "tool_call_correctness"])
    scorecard, traces = run_suite(agent, cases, scorers)
    engine = get_engine(db_path)
    save_full_run(engine, scorecard, traces)
    return scorecard, engine


def test_regression_is_flagged_when_a_case_gets_worse(tmp_path):
    db_path = str(tmp_path / "regression_test.db")

    baseline_scorecard, engine = _run_once(db_path)

    broken_kb = dict(_KNOWLEDGE_BASE)
    broken_kb["capital of france"] = ("Berlin is the capital of France.", "geo-facts.md")
    with patch("agentsentinel.adapters.toy_agent._KNOWLEDGE_BASE", broken_kb):
        broken_scorecard, engine = _run_once(db_path)

    with Session(engine) as session:
        result = check_regressions(session, broken_scorecard.run_id, baseline_run_id=baseline_scorecard.run_id)

    assert result["baseline_run_id"] == baseline_scorecard.run_id
    regressed_cases = {r["test_case_id"] for r in result["regressions"]}
    assert "toy-001-capital" in regressed_cases


def test_recovery_is_not_flagged_as_a_regression(tmp_path):
    db_path = str(tmp_path / "regression_test.db")

    broken_kb = dict(_KNOWLEDGE_BASE)
    broken_kb["capital of france"] = ("Berlin is the capital of France.", "geo-facts.md")
    with patch("agentsentinel.adapters.toy_agent._KNOWLEDGE_BASE", broken_kb):
        broken_scorecard, engine = _run_once(db_path)

    fixed_scorecard, engine = _run_once(db_path)  # real _KNOWLEDGE_BASE, unpatched

    with Session(engine) as session:
        result = check_regressions(session, fixed_scorecard.run_id, baseline_run_id=broken_scorecard.run_id)

    assert result["regressions"] == []
