"""Importing this package triggers every builtin scorer's @register call.
Add a new scorer module's import here to make it discoverable by name."""
from agentsentinel.scoring import (  # noqa: F401
    faithfulness,
    injection_resistance,
    keyword_match,
    latency_cost,
    tool_call_correctness,
)
from agentsentinel.scoring.registry import get_scorer, get_scorers, register, registered_names

__all__ = ["get_scorer", "get_scorers", "register", "registered_names"]
