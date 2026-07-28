from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click

from agentsentinel.cli import cli

_APP_PATH = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"


@cli.command()
def dashboard() -> None:
    """Launch the Streamlit dashboard (requires `pip install -e ".[dashboard]"`)."""
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(_APP_PATH)])
