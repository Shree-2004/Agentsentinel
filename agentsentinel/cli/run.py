from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

import agentsentinel.scoring  # noqa: F401 - import triggers scorer registration
from agentsentinel.adapters import available_adapters, build_adapter
from agentsentinel.cli import cli
from agentsentinel.runner.suite_runner import run_suite
from agentsentinel.scoring.registry import get_scorers
from agentsentinel.storage.db import get_engine, save_full_run
from agentsentinel.testcases.loader import load_seed_cases

console = Console()


@cli.command()
@click.option("--agent", "agent_name", required=True, help=f"One of: {', '.join(available_adapters())}")
@click.option("--db-path", default=None, help="SQLite file to write results to (default: ./agentsentinel.db)")
def run(agent_name: str, db_path: str | None) -> None:
    """Run the seed test suite against an agent and print a scorecard."""
    agent = build_adapter(agent_name)
    cases = load_seed_cases(agent_target=agent_name)
    if not cases:
        console.print(f"[yellow]No seed test cases found for agent '{agent_name}'.[/yellow]")
        raise SystemExit(1)

    scorers = get_scorers()
    scorecard, traces = run_suite(agent, cases, scorers)

    engine = get_engine(db_path)
    save_full_run(engine, scorecard, traces)

    _print_scorecard(scorecard)
    if scorecard.pass_rate < 1.0:
        raise SystemExit(1)


def _print_scorecard(scorecard) -> None:
    console.print(f"\n[bold]Run {scorecard.run_id}[/bold] - agent: {scorecard.agent_name}")
    console.print(f"Pass rate: {scorecard.pass_rate:.0%}\n")

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
