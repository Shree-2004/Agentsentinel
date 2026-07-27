"""Runs the hand-labeled faithfulness calibration set against the live
judge and reports agreement — the deliverable that justifies trusting an
LLM judge in a CI gate at all, per docs/architecture.md. This is a real
check, not a formality: if agreement is low, the judge/prompt needs work
before any injection_resistance or faithfulness score should gate anything.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from agentsentinel.scoring.faithfulness import FaithfulnessScorer

_CALIBRATION_FILE = Path(__file__).parent / "faithfulness_calibration.yaml"


def load_calibration_set() -> list[dict]:
    return yaml.safe_load(_CALIBRATION_FILE.read_text(encoding="utf-8"))


def run_faithfulness_calibration() -> dict:
    """Returns {"agreement": float, "total": int, "results": [...]}."""
    scorer = FaithfulnessScorer()
    items = load_calibration_set()

    results = []
    agreed = 0
    for item in items:
        actual = scorer._verify(item["claim"], item["context"])
        is_agreement = actual == item["expected"]
        agreed += int(is_agreement)
        results.append(
            {
                "claim": item["claim"],
                "expected": item["expected"],
                "actual": actual,
                "agree": is_agreement,
            }
        )

    return {"agreement": agreed / len(items), "total": len(items), "results": results}
