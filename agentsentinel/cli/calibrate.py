from __future__ import annotations

from rich.console import Console
from rich.table import Table

from agentsentinel.cli import cli
from agentsentinel.scoring.calibration.run_calibration import run_faithfulness_calibration

console = Console()


@cli.command()
def calibrate() -> None:
    """Run the hand-labeled calibration set against the live faithfulness
    judge and report agreement. Requires GOOGLE_API_KEY (see .env.example)."""
    result = run_faithfulness_calibration()

    console.print(f"\n[bold]Faithfulness judge calibration[/bold]")
    console.print(f"Agreement: {result['agreement']:.0%} ({int(result['agreement'] * result['total'])}/{result['total']})\n")

    table = Table()
    table.add_column("Agree")
    table.add_column("Expected")
    table.add_column("Actual")
    table.add_column("Claim")
    for r in result["results"]:
        mark = "[green]OK[/green]" if r["agree"] else "[red]XX[/red]"
        table.add_row(mark, r["expected"], r["actual"], r["claim"])
    console.print(table)

    if result["agreement"] < 0.8:
        console.print("\n[bold red]Agreement below 80% — do not trust this judge in a CI gate yet.[/bold red]")
        raise SystemExit(1)
