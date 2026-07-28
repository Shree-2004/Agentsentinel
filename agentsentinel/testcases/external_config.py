"""Loads a combined "bring your own agent" config: one YAML file with an
`agent:` block (connection info for GenericAgentAdapter) and a `cases:`
block (same TestCase schema as the built-in seed YAMLs). One file rather
than two, so onboarding a new agent this way means writing exactly one
document — see docs/bring_your_own_agent.md.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from agentsentinel.adapters.generic_agent import GenericAgentAdapter
from agentsentinel.core.models import TestCase
from agentsentinel.testcases.loader import parse_case_entries


def load_external_config(path: str | Path) -> tuple[GenericAgentAdapter, list[TestCase]]:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    agent_config = dict(raw["agent"])
    # repo_path in the config is conventionally relative to the config
    # file's own location (so a config can live anywhere, travel with a
    # project, etc.) rather than relative to wherever `agentsentinel` is
    # invoked from.
    repo_path = Path(agent_config["repo_path"])
    if not repo_path.is_absolute():
        agent_config["repo_path"] = str((path.parent / repo_path).resolve())

    agent = GenericAgentAdapter(agent_config)
    cases = parse_case_entries(raw.get("cases", []), default_agent_target=agent.name)

    return agent, cases
