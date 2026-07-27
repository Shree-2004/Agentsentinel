"""Scorer registry: scorers self-register on import via @register, and the
runner looks them up by name. Keeps adding a new metric a one-file change
(write the scorer, import it in scoring/__init__.py) with no change to the
runner itself.
"""
from __future__ import annotations

from typing import Protocol

from agentsentinel.core.models import AgentTrace, MetricScore, TestCase


class Scorer(Protocol):
    name: str

    def score(self, case: TestCase, trace: AgentTrace) -> MetricScore: ...


_REGISTRY: dict[str, Scorer] = {}


def register(scorer: Scorer) -> Scorer:
    _REGISTRY[scorer.name] = scorer
    return scorer


def get_scorer(name: str) -> Scorer:
    return _REGISTRY[name]


def get_scorers(names: list[str] | None = None) -> list[Scorer]:
    if names is None:
        return list(_REGISTRY.values())
    return [_REGISTRY[n] for n in names]


def registered_names() -> list[str]:
    return list(_REGISTRY.keys())
