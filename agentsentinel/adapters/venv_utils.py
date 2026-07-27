"""Small helper for locating/creating a target repo's own venv, so
SubprocessAgentAdapter subclasses don't each reimplement this.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def venv_python_path(repo_path: Path, venv_dir_name: str = "venv") -> Path:
    venv_dir = repo_path / venv_dir_name
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def ensure_venv(repo_path: Path, requirements_file: str = "requirements.txt", venv_dir_name: str = "venv") -> Path:
    """Creates repo_path/venv and installs repo_path/requirements.txt into it
    if the venv doesn't already exist. Idempotent — if the venv is already
    there (as it is for the LangGraph research repo, which ships its own),
    this is a no-op and just returns the interpreter path."""
    python_path = venv_python_path(repo_path, venv_dir_name)
    if python_path.exists():
        return python_path

    venv_dir = repo_path / venv_dir_name
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)

    requirements_path = repo_path / requirements_file
    if requirements_path.exists():
        subprocess.run(
            [str(python_path), "-m", "pip", "install", "--quiet", "-r", str(requirements_path)],
            check=True,
        )
    return python_path
