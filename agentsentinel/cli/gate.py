from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table
from sqlalchemy.orm import Session

from agentsentinel.adapters import available_adapters
from agentsentinel.cli import cli
from agentsentinel.cli._common import DETERMINISTIC_SCORERS, execute_and_save
from agentsentinel.cli.run import print_scorecard
from agentsentinel.scoring.registry import registered_names
from agentsentinel.storage.regression import check_regressions

console = Console()


@cli.command()
@click.option("--agent", "agent_name", required=True, help=f"One of: {', '.join(available_adapters())}")
@click.option("--db-path", default=None, help="SQLite file to read/write (default: ./agentsentinel.db)")
@click.option(
    "--scorers",
    default=None,
    help=f"Comma-separated scorer names, or 'all'. Default: deterministic only ({','.join(DETERMINISTIC_SCORERS)}). "
    f"Available: {', '.join(registered_names())}",
)
@click.option(
    "--baseline",
    default=None,
    help="Run id to compare against. Default: the most recent prior run for this agent in the same database.",
)
@click.option("--pass-rate-floor", default=1.0, type=float, help="Exit non-zero if pass_rate drops below this.")
def gate(agent_name: str, db_path: str | None, scorers: str | None, baseline: str | None, pass_rate_floor: float) -> None:
    """Run the suite, check for regressions against a baseline run, and
    exit non-zero if any regressed or pass_rate is below the floor - the
    command a CI job actually calls (see docs/architecture.md's
    fast/deterministic-per-PR vs. nightly/full split)."""
    try:
        scorecard, traces, engine = execute_and_save(agent_name, db_path, scorers)
    except ValueError as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        raise SystemExit(1)

    print_scorecard(scorecard, traces)

    with Session(engine) as session:
        result = check_regressions(session, scorecard.run_id, baseline_run_id=baseline)

    _print_regression_result(result)

    failed = False
    if result["regressions"]:
        failed = True
    if scorecard.pass_rate < pass_rate_floor:
        console.print(f"\n[bold red]Pass rate {scorecard.pass_rate:.0%} below floor {pass_rate_floor:.0%}.[/bold red]")
        failed = True

    if failed:
        raise SystemExit(1)
    console.print("\n[bold green]Gate passed.[/bold green]")


def _print_regression_result(result: dict) -> None:
    if result["baseline_run_id"] is None:
        console.print("\n[dim]No prior run found for this agent - nothing to compare against yet.[/dim]")
        return

    console.print(f"\nBaseline: {result['baseline_run_id']}")
    regressions = result["regressions"]
    if not regressions:
        console.print("[green]No regressions.[/green]")
        return

    table = Table(title=f"{len(regressions)} regression(s) found")
    table.add_column("Case")
    table.add_column("Metric")
    table.add_column("Baseline", justify="right")
    table.add_column("Current", justify="right")
    table.add_column("Delta", justify="right")
    for r in regressions:
        table.add_row(
            r["test_case_id"], r["metric_name"], f"{r['baseline_score']:.2f}", f"{r['current_score']:.2f}",
            f"[red]{r['delta']:+.2f}[/red]",
        )
    console.print(table)
