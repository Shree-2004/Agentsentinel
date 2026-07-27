"""Loads TestCase objects from YAML files under testcases/seed/ (trusted,
CI-gating) or any other directory passed explicitly. YAML rather than Python
so review happens via normal PR diffs on data files, and non-engineers could
in principle contribute cases.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from agentsentinel.core.models import CaseCategory, CaseSource, TestCase

SEED_DIR = Path(__file__).parent / "seed"


def load_file(path: Path) -> list[TestCase]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    cases = []
    for entry in raw:
        cases.append(
            TestCase(
                id=entry["id"],
                agent_target=entry["agent_target"],
                input_text=entry["input_text"],
                category=CaseCategory(entry["category"]),
                multi_turn=entry.get("multi_turn", False),
                expected=entry.get("expected", {}),
                tags=entry.get("tags", []),
                source=CaseSource(entry.get("source", "curated")),
                notes=entry.get("notes", ""),
            )
        )
    return cases


def load_seed_cases(agent_target: str | None = None, directory: Path | None = None) -> list[TestCase]:
    directory = directory or SEED_DIR
    cases: list[TestCase] = []
    for path in sorted(directory.glob("*.yaml")):
        cases.extend(load_file(path))
    if agent_target is not None:
        cases = [c for c in cases if c.agent_target in (agent_target, "*")]
    return cases
