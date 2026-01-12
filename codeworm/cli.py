"""
ⒸAngelaMos | 2026
cli.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

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
@click.option("--devlog", type=click.Path(path_type=Path), required=True, help="Path to DevLog repository")
@click.option("--repo", type=(str, str), multiple=True, help="Add repo as NAME PATH pairs")
@click.pass_context
def run(ctx: click.Context, devlog: Path, repo: tuple) -> None:
    """
    Run the CodeWorm daemon with scheduler
    """
    from codeworm.daemon import CodeWormDaemon

    repos = [{"name": name, "path": Path(path), "weight": 5} for name, path in repo]

    settings = load_settings(
        debug=ctx.obj["debug"],
        devlog={"repo_path": devlog},
        repos=repos,
    )
    configure_logging(debug=settings.debug)

    console.print(f"[bold green]Starting CodeWorm[/bold green]")
    console.print(f"  DevLog: {devlog}")
    console.print(f"  Repos: {len(repos)}")

    daemon = CodeWormDaemon(settings)
    daemon.run()


@cli.command("run-once")
@click.option("--devlog", type=click.Path(path_type=Path), required=True, help="Path to DevLog repository")
@click.option("--repo", type=(str, str), multiple=True, help="Add repo as NAME PATH pairs")
@click.pass_context
def run_once(ctx: click.Context, devlog: Path, repo: tuple) -> None:
    """
    Run a single documentation cycle then exit
    """
    from codeworm.daemon import CodeWormDaemon

    repos = [{"name": name, "path": Path(path), "weight": 5} for name, path in repo]

    settings = load_settings(
        debug=ctx.obj["debug"],
        devlog={"repo_path": devlog},
        repos=repos,
    )
    configure_logging(debug=settings.debug)

    console.print("[bold]Running single documentation cycle...[/bold]")

    daemon = CodeWormDaemon(settings)
    result = asyncio.run(daemon.run_once())

    if result:
        console.print("[green]Documentation generated successfully[/green]")
    else:
        console.print("[yellow]No candidates found or all already documented[/yellow]")


@cli.command()
@click.option("--repo", type=click.Path(exists=True, path_type=Path), required=True, help="Repository to analyze")
@click.option("--limit", default=20, help="Max candidates to show")
@click.pass_context
def analyze(ctx: click.Context, repo: Path, limit: int) -> None:
    """
    Analyze a repository and show documentation candidates
    """
    from codeworm.analysis import CodeAnalyzer, ParserManager
    from codeworm.core.config import RepoEntry

    configure_logging(debug=ctx.obj["debug"])
    ParserManager.initialize()

    repo_config = RepoEntry(name=repo.name, path=repo, weight=5)
    analyzer = CodeAnalyzer([repo_config])

    console.print(f"[bold]Analyzing {repo}...[/bold]\n")

    candidates = analyzer.find_candidates(repo=repo_config, limit=limit)

    if not candidates:
        console.print("[yellow]No candidates found[/yellow]")
        return

    table = Table(title=f"Top {len(candidates)} Documentation Candidates")
    table.add_column("Score", style="cyan", justify="right")
    table.add_column("Function", style="green")
    table.add_column("File", style="dim")
    table.add_column("Lines", justify="right")
    table.add_column("Complexity", justify="right")

    for c in candidates:
        table.add_row(
            f"{c.score:.1f}",
            c.snippet.display_name,
            str(c.scanned_file.relative_path),
            str(c.snippet.line_count),
            str(int(c.snippet.complexity)),
        )

    console.print(table)


@cli.command("schedule-preview")
@click.option("--days", default=1, help="Number of days to preview")
@click.option("--timezone", default="America/Los_Angeles", help="Timezone for schedule")
@click.pass_context
def schedule_preview(ctx: click.Context, days: int, timezone: str) -> None:
    """
    Preview upcoming scheduled commit times
    """
    from codeworm.scheduler import CodeWormScheduler
    from codeworm.core.config import ScheduleSettings

    settings = ScheduleSettings(timezone=timezone)
    scheduler = CodeWormScheduler(settings)

    preview = scheduler.get_schedule_preview(days=days)

    console.print(f"[bold]Schedule Preview ({days} day(s))[/bold]\n")

    table = Table()
    table.add_column("Time", style="cyan")
    table.add_column("Hour", justify="right")
    table.add_column("Day", style="dim")

    for entry in preview:
        day_type = "[yellow]Weekend[/yellow]" if entry["is_weekend"] else "Weekday"
        table.add_row(
            entry["time"],
            str(entry["hour"]),
            day_type,
        )

    console.print(table)
    console.print(f"\n[dim]Total commits scheduled: {len(preview)}[/dim]")


@cli.command()
@click.option("--devlog", type=click.Path(path_type=Path), required=True, help="Path to DevLog repository")
@click.pass_context
def stats(ctx: click.Context, devlog: Path) -> None:
    """
    Show documentation statistics
    """
    from codeworm.core import StateManager

    settings = load_settings(
        debug=ctx.obj["debug"],
        devlog={"repo_path": devlog},
    )

    state = StateManager(settings.db_path)
    stats_data = state.get_stats()

    console.print("\n[bold]CodeWorm Statistics[/bold]\n")
    console.print(f"Total documented: [green]{stats_data['total_documented']}[/green]")
    console.print(f"Last 7 days: [cyan]{stats_data['last_7_days']}[/cyan]")

    if stats_data["by_repo"]:
        console.print("\n[bold]By Repository:[/bold]")
        for repo_name, count in stats_data["by_repo"].items():
            console.print(f"  {repo_name}: {count}")


@cli.command()
@click.option("--devlog", type=click.Path(path_type=Path), required=True, help="Path to DevLog repository")
@click.pass_context
def init(ctx: click.Context, devlog: Path) -> None:
    """
    Initialize a new DevLog repository
    """
    from codeworm.git import DevLogRepository

    configure_logging(debug=ctx.obj["debug"])

    console.print(f"[bold]Initializing DevLog at {devlog}...[/bold]")

    repo = DevLogRepository(repo_path=devlog)
    repo.ensure_directory_structure()

    console.print("[green]DevLog initialized successfully[/green]")
    console.print("\nDirectory structure created:")
    console.print("  snippets/python/")
    console.print("  snippets/typescript/")
    console.print("  snippets/javascript/")
    console.print("  snippets/go/")
    console.print("  snippets/rust/")
    console.print("  analysis/weekly/")
    console.print("  analysis/monthly/")
    console.print("  patterns/")
    console.print("  stats/")


@cli.command()
def version() -> None:
    """
    Show version information
    """
    from codeworm import __version__

    console.print(f"[bold]CodeWorm[/bold] v{__version__}")


def main() -> int:
    """
    CLI entry point
    """
    try:
        cli()
        return 0
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        return 130
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
