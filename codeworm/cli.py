"""
ⒸAngelaMos | 2026
cli.py
"""
import sys
from pathlib import Path

import click
from rich.console import Console

from codeworm.core import configure_logging, get_logger, load_settings

console = Console()


@click.group()
@click.option("--debug", is_flag=True, help="Enable debug logging")
@click.pass_context
def cli(ctx: click.Context, debug: bool) -> None:
    """
    CodeWorm - Autonomous Code Documentation Agent
    """
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug


@cli.command()
@click.option("--devlog-path", type=click.Path(path_type=Path), required=True)
@click.pass_context
def run(ctx: click.Context, devlog_path: Path) -> None:
    """
    Run the CodeWorm daemon
    """
    from codeworm.daemon import CodeWormDaemon

    settings = load_settings(
        debug=ctx.obj["debug"],
        devlog={"repo_path": devlog_path},
    )
    configure_logging(debug=settings.debug)
    logger = get_logger("cli")

    logger.info("starting_daemon", devlog_path=str(devlog_path))
    daemon = CodeWormDaemon(settings)
    daemon.run()


@cli.command()
@click.option("--devlog-path", type=click.Path(path_type=Path), required=True)
@click.pass_context
def stats(ctx: click.Context, devlog_path: Path) -> None:
    """
    Show documentation statistics
    """
    from codeworm.core import StateManager

    settings = load_settings(
        debug=ctx.obj["debug"],
        devlog={"repo_path": devlog_path},
    )
    configure_logging(debug=settings.debug)

    state = StateManager(settings.db_path)
    stats_data = state.get_stats()

    console.print("\n[bold]CodeWorm Statistics[/bold]\n")
    console.print(f"Total documented: [green]{stats_data['total_documented']}[/green]")
    console.print(f"Last 7 days: [cyan]{stats_data['last_7_days']}[/cyan]")

    if stats_data["by_repo"]:
        console.print("\n[bold]By Repository:[/bold]")
        for repo, count in stats_data["by_repo"].items():
            console.print(f"  {repo}: {count}")


@cli.command()
def version() -> None:
    """
    Show version information
    """
    from codeworm import __version__

    console.print(f"CodeWorm v{__version__}")


def main() -> int:
    """
    CLI entry point
    """
    try:
        cli()
        return 0
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
