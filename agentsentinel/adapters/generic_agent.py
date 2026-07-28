"""The no-custom-Python-needed adapter. Where the other three adapters each
have a bespoke shim hand-written for that specific target's quirks, this
one adapter + agentsentinel/adapters/shims/generic_shim.py handles any
agent shaped like `result = some_function(input_text)` purely from a YAML
config — see docs/bring_your_own_agent.md.

Anything more exotic (async, multi-turn, tool-calling, needing pre-built
dependencies passed in) still needs a bespoke adapter per
docs/adding_an_adapter.md — this covers the common case, not every case.
"""
from __future__ import annotations

from pathlib import Path

from agentsentinel.adapters.subprocess_base import SubprocessAgentAdapter
from agentsentinel.adapters.venv_utils import ensure_venv, venv_python_path
from agentsentinel.core.models import RunContext, TestCase


class GenericAgentAdapter(SubprocessAgentAdapter):
    def __init__(self, config: dict):
        self._config = config
        self.name = config["name"]
        self.version = "0.1.0"
        self.timeout_s = float(config.get("timeout_s", 120.0))

        self._repo_path = Path(config["repo_path"]).resolve()
        self.shim_path = Path(__file__).parent / "shims" / "generic_shim.py"
        self.venv_python = venv_python_path(self._repo_path, config.get("venv_dir_name", "venv"))

    def setup(self, ctx: RunContext) -> None:
        requirements_file = self._config.get("requirements_file")
        if not self.venv_python.exists():
            if not requirements_file:
                raise FileNotFoundError(
                    f"No venv found at {self.venv_python}, and no requirements_file was given in the "
                    f"config to create one. Either set up a venv in {self._repo_path} yourself, or add "
                    f"`requirements_file: requirements.txt` to the config."
                )
            self.venv_python = ensure_venv(
                self._repo_path, requirements_file, self._config.get("venv_dir_name", "venv")
            )

    def _extra_payload(self, case: TestCase) -> dict:
        return {
            "config": {
                "repo_path": str(self._repo_path),
                "module": self._config["entrypoint"]["module"],
                "function": self._config["entrypoint"]["function"],
                "output_style": self._config.get("output_style", "string"),
                "output_field": self._config.get("output_field"),
                "dotenv": self._config.get("dotenv", True),
            }
        }
