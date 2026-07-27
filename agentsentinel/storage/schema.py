"""SQLAlchemy models mirroring the core dataclasses 1:1 so serialization
stays boring: Run -> Scorecard, Trace -> AgentTrace, Score -> MetricScore.
SQLite by default (zero-ops for a portfolio project); swapping to Postgres
later is just a connection-string change since nothing here is SQLite-specific.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class RunRow(Base):
    __tablename__ = "runs"

    id = Column(String, primary_key=True)
    agent_name = Column(String, index=True, nullable=False)
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=False)
    git_sha = Column(String, nullable=True)
    config_json = Column(JSON, default=dict)
    pass_rate = Column(Float, default=0.0)
    aggregate_json = Column(JSON, default=dict)
    baseline_run_id = Column(String, nullable=True)
    regressions_json = Column(JSON, default=list)

    traces = relationship("TraceRow", back_populates="run", cascade="all, delete-orphan")


class TraceRow(Base):
    __tablename__ = "traces"

    trace_id = Column(String, primary_key=True)
    run_id = Column(String, ForeignKey("runs.id"), index=True, nullable=False)
    test_case_id = Column(String, index=True, nullable=False)
    agent_name = Column(String, index=True, nullable=False)
    output_text = Column(Text, default="")
    tool_calls_json = Column(JSON, default=list)
    sources_json = Column(JSON, default=list)
    latency_ms = Column(Float, default=0.0)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    cost_usd_estimate = Column(Float, nullable=True)
    error = Column(Text, nullable=True)
    raw_output_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    run = relationship("RunRow", back_populates="traces")
    scores = relationship("ScoreRow", back_populates="trace", cascade="all, delete-orphan")


class ScoreRow(Base):
    __tablename__ = "scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trace_id = Column(String, ForeignKey("traces.trace_id"), index=True, nullable=False)
    metric_name = Column(String, index=True, nullable=False)
    score = Column(Float, nullable=False)
    passed = Column(Boolean, nullable=True)
    rationale = Column(Text, default="")
    raw_json = Column(JSON, default=dict)

    trace = relationship("TraceRow", back_populates="scores")
