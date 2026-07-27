from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

import agentsentinel.scoring  # noqa: F401 - import triggers scorer registration
from agentsentinel.adapters import available_adapters, build_adapter
from agentsentinel.cli import cli
from agentsentinel.runner.suite_runner import run_suite
from agentsentinel.scoring.registry import get_scorers, registered_names
from agentsentinel.storage.db import get_engine, save_full_run
from agentsentinel.testcases.loader import load_seed_cases

console = Console()

# Scorers that never call an LLM judge — safe to run with zero extra deps
# and zero API cost, appropriate for a fast per-PR gate (see
# docs/architecture.md's "fast/deterministic vs nightly/full" split).
# LLM-judge scorers (faithfulness, injection_resistance) are opt-in via
# --scorers so `agentsentinel run --agent toy-agent` never silently starts
# requiring a GOOGLE_API_KEY just because a new judge scorer got registered.
DETERMINISTIC_SCORERS = ["keyword_match", "latency", "tool_call_correctness"]


@cli.command()
@click.option("--agent", "agent_name", required=True, help=f"One of: {', '.join(available_adapters())}")
@click.option("--db-path", default=None, help="SQLite file to write results to (default: ./agentsentinel.db)")
@click.option(
    "--scorers",
    default=None,
    help=f"Comma-separated scorer names, or 'all'. Default: deterministic only ({','.join(DETERMINISTIC_SCORERS)}). "
    f"Available: {', '.join(registered_names())}",
)
def run(agent_name: str, db_path: str | None, scorers: str | None) -> None:
    """Run the seed test suite against an agent and print a scorecard."""
    agent = build_adapter(agent_name)
    cases = load_seed_cases(agent_target=agent_name)
    if not cases:
        console.print(f"[yellow]No seed test cases found for agent '{agent_name}'.[/yellow]")
        raise SystemExit(1)

    if scorers is None:
        scorer_names = DETERMINISTIC_SCORERS
    elif scorers == "all":
        scorer_names = None  # get_scorers(None) returns everything
    else:
        scorer_names = [s.strip() for s in scorers.split(",")]

    scorer_list = get_scorers(scorer_names)
    scorecard, traces = run_suite(agent, cases, scorer_list)

    engine = get_engine(db_path)
    save_full_run(engine, scorecard, traces)

    _print_scorecard(scorecard, traces)
    if scorecard.pass_rate < 1.0:
        raise SystemExit(1)


def _print_scorecard(scorecard, traces) -> None:
    console.print(f"\n[bold]Run {scorecard.run_id}[/bold] - agent: {scorecard.agent_name}")
    console.print(f"Pass rate: {scorecard.pass_rate:.0%}\n")

    # Surface adapter-level errors up front — these are agent/environment
    # failures (bad API key, timeout, target-repo bug) rather than a score
    # to weigh, and they explain why every metric for that case looks like
    # a failure. Without this, understanding *why* a case failed means
    # manually querying the SQLite traces table for the .error field.
    errored = [t for t in traces if t.error]
    if errored:
        console.print(f"[bold red]{len(errored)} case(s) errored (not scored, adapter/agent-level failure):[/bold red]")
        for trace in errored:
            first_line = trace.error.splitlines()[0]
            console.print(f"  [red]{trace.test_case_id}[/red]: {first_line}")
        console.print()

    table = Table(title="Aggregate scores")
    table.add_column("Metric")
    table.add_column("Mean score", justify="right")
    for metric, value in scorecard.aggregate.items():
        table.add_row(metric, f"{value:.2f}")
    console.print(table)

    detail = Table(title="Per-case results")
    detail.add_column("Case")
    detail.add_column("Metric")
    detail.add_column("Score", justify="right")
    detail.add_column("Passed")
    detail.add_column("Rationale")
    for result in scorecard.results:
        for score in result.scores:
            passed_str = "-" if score.passed is None else ("PASS" if score.passed else "FAIL")
            detail.add_row(result.test_case_id, score.metric_name, f"{score.score:.2f}", passed_str, score.rationale)
    console.print(detail)
