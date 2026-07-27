"""Core data model shared by every adapter, scorer, and storage layer.

TestCase.expected is intentionally a loose dict rather than a rigid schema:
a normal case cares about {"must_contain": [...]}, an injection case cares
about {"forbidden_action": ..., "canary_string": ...}. Scorers read only the
keys they understand and ignore the rest, so new case categories don't
require a schema migration.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
import uuid


class CaseCategory(str, Enum):
    NORMAL = "normal"
    EDGE_CASE = "edge_case"
    ADVERSARIAL_INJECTION = "adversarial_injection"


class CaseSource(str, Enum):
    CURATED = "curated"
    LLM_GENERATED = "llm_generated"
    REGRESSION = "regression"


@dataclass
class TestCase:
    id: str
    agent_target: str
    input_text: str
    category: CaseCategory
    multi_turn: bool = False
    expected: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    source: CaseSource = CaseSource.CURATED
    notes: str = ""


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any] = field(default_factory=dict)
    result_summary: Optional[str] = None


@dataclass
class SourceRef:
    """Superset of fields across all adapter types. Each adapter populates
    what it has (a RAG chunk has page/score; an MCP tool call has none) and
    leaves the rest None rather than inventing placeholder values."""

    content: str
    source: str
    label: Optional[str] = None
    page: Optional[int] = None
    chunk_index: Optional[int] = None
    score: Optional[float] = None


@dataclass
class AgentTrace:
    test_case_id: str
    agent_name: str
    output_text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    sources: list[SourceRef] = field(default_factory=list)
    latency_ms: float = 0.0
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    cost_usd_estimate: Optional[float] = None
    error: Optional[str] = None
    raw_output: Any = None
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class MetricScore:
    metric_name: str
    score: float  # normalized 0.0-1.0
    passed: Optional[bool] = None
    rationale: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalResult:
    trace_id: str
    test_case_id: str
    agent_name: str
    scores: list[MetricScore] = field(default_factory=list)


@dataclass
class Scorecard:
    run_id: str
    agent_name: str
    started_at: datetime
    finished_at: datetime
    results: list[EvalResult] = field(default_factory=list)
    aggregate: dict[str, float] = field(default_factory=dict)  # metric_name -> mean
    pass_rate: float = 0.0
    baseline_run_id: Optional[str] = None
    regressions: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class RunContext:
    run_id: str
    config: dict[str, Any] = field(default_factory=dict)
    shared: dict[str, Any] = field(default_factory=dict)
