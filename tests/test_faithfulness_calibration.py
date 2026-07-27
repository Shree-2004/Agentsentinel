"""Live test: runs the hand-labeled calibration set against the real judge
and asserts reasonable agreement. Skipped by default (hits a real Gemini
API) — same convention as the adapter live tests.
Run explicitly with: AGENTSENTINEL_RUN_LIVE_TESTS=1 pytest -v -m live
"""
from __future__ import annotations

import os

import pytest

from agentsentinel.scoring.calibration.run_calibration import run_faithfulness_calibration

pytestmark = pytest.mark.skipif(
    os.environ.get("AGENTSENTINEL_RUN_LIVE_TESTS") != "1",
    reason="live test — hits a real LLM API; set AGENTSENTINEL_RUN_LIVE_TESTS=1 to run",
)


@pytest.mark.live
def test_faithfulness_judge_agrees_with_human_labels():
    result = run_faithfulness_calibration()
    disagreements = [r for r in result["results"] if not r["agree"]]
    assert result["agreement"] >= 0.8, f"judge disagreed with human labels on: {disagreements}"
