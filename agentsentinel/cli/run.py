from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

import agentsentinel.scoring  # noqa: F401 - import triggers scorer registration
from agentsentinel.adapters import available_adapters
from agentsentinel.cli import cli
from agentsentinel.cli._common import DETERMINISTIC_SCORERS, execute_and_save
from agentsentinel.scoring.registry import registered_names

console = Console()


@cli.command()
@click.option("--agent", "agent_name", default=None, help=f"One of the built-in adapters: {', '.join(available_adapters())}")
@click.option(
    "--config",
    "config_path",
    default=None,
    help="Path to a 'bring your own agent' YAML instead of --agent — see docs/bring_your_own_agent.md",
)
@click.option("--db-path", default=None, help="SQLite file to write results to (default: ./agentsentinel.db)")
@click.option(
    "--scorers",
    default=None,
    help=f"Comma-separated scorer names, or 'all'. Default: deterministic only ({','.join(DETERMINISTIC_SCORERS)}). "
    f"Available: {', '.join(registered_names())}",
)
def run(agent_name: str | None, config_path: str | None, db_path: str | None, scorers: str | None) -> None:
    """Run the seed test suite against an agent and print a scorecard."""
    if not agent_name and not config_path:
        console.print("[yellow]Provide either --agent <name> or --config <path>.[/yellow]")
        raise SystemExit(1)
    if agent_name and config_path:
        console.print("[yellow]Provide only one of --agent or --config, not both.[/yellow]")
        raise SystemExit(1)

    try:
        scorecard, traces, _engine = execute_and_save(agent_name, db_path, scorers, config_path=config_path)
    except ValueError as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        raise SystemExit(1)

    print_scorecard(scorecard, traces)
    if scorecard.pass_rate < 1.0:
        raise SystemExit(1)


def print_scorecard(scorecard, traces) -> None:
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
