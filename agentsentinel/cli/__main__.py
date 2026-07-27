from agentsentinel.cli import cli
from agentsentinel.cli import run  # noqa: F401 - import registers the `run` command


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
