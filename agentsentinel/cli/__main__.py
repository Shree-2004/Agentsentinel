import sys

# Wrapped agents are third-party code we don't control, and several of the
# ones in this portfolio print emoji/unicode to stdout (progress markers,
# arrows). On Windows, the default console codepage (cp1252) raises
# UnicodeEncodeError on those prints, which surfaces as a mysterious adapter
# crash with nothing to do with the agent's actual logic. Force UTF-8 before
# importing/running anything that might print.
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from agentsentinel.cli import cli
from agentsentinel.cli import run  # noqa: F401 - import registers the `run` command


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
