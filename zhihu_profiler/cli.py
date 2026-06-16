"""Command-line interface for Zhihu Profiler."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from . import __version__
from .scraper.zhihu import ZhihuScraper
from .scraper.models import ScrapedData
from .analysis.profiler import Profiler, UserProfile
from .viz.dashboard import ReportGenerator

console = Console()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(console=console)],
)
logger = logging.getLogger("zhihu-profiler")


@click.group()
@click.version_option(version=__version__, prog_name="zhihu-profiler")
def main():
    """Zhihu Profiler - Deep personality profiling through Zhihu answer analysis."""
    pass


@main.command()
@click.argument("user", metavar="USER_ID_OR_URL")
@click.option(
    "--output", "-o",
    default="output",
    type=click.Path(path_type=Path),
    help="Output directory for reports",
)
@click.option(
    "--max-answers", "-n",
    default=500,
    type=int,
    help="Maximum number of answers to scrape",
)
@click.option(
    "--no-headless",
    is_flag=True,
    help="Show browser window (useful for login)",
)
@click.option(
    "--skip-scrape",
    is_flag=True,
    help="Skip scraping, load from saved data",
)
@click.option(
    "--data-file",
    type=click.Path(exists=True, path_type=Path),
    help="Load scraped data from JSON file",
)
@click.option(
    "--json-only",
    is_flag=True,
    help="Output only JSON profile, skip HTML report",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Verbose output",
)
def analyze(
    user: str,
    output: Path,
    max_answers: int,
    no_headless: bool,
    skip_scrape: bool,
    data_file: Path | None,
    json_only: bool,
    verbose: bool,
):
    """Analyze a Zhihu user's profile from their answers.

    USER_ID_OR_URL: Zhihu user ID or profile URL.
    Example: zhihu-profiler analyze https://www.zhihu.com/people/zhihu-admin
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    console.print()
    console.print(Panel.fit(
        "[bold magenta]Zhihu Profiler[/bold magenta] · Deep Personality Analysis",
        border_style="magenta",
    ))
    console.print()

    # Load or scrape data
    data: ScrapedData | None = None

    if data_file:
        console.print(f"[dim]Loading data from {data_file}...[/dim]")
        import json
        with open(data_file, "r", encoding="utf-8") as f:
            raw = json.load(f)
        data = ScrapedData(**raw)
        console.print(f"[green]Loaded: {len(data.answers)} answers[/green]")

    if not skip_scrape and not data:
        console.print(f"[bold]Scraping:[/bold] {user}")
        console.print(f"[dim]Max answers: {max_answers}, Headless: {not no_headless}[/dim]")
        console.print()

        async def _scrape():
            async with ZhihuScraper(
                headless=not no_headless,
                max_answers=max_answers,
            ) as scraper:
                return await scraper.scrape_user(user)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Scraping user data...", total=None)
            data = asyncio.run(_scrape())
            progress.update(task, completed=True)

        console.print()
        console.print(f"[green]Scraped {data.answers_scraped} answers from {data.user.name}[/green]")

        # Save raw data
        output.mkdir(parents=True, exist_ok=True)
        data_path = output / f"{data.user.id}_raw.json"
        with open(data_path, "w", encoding="utf-8") as f:
            import json
            f.write(data.model_dump_json(indent=2, ensure_ascii=False))
        console.print(f"[dim]Raw data saved to {data_path}[/dim]")

    if not data:
        console.print("[red]No data available. Use --data-file or run without --skip-scrape.[/red]")
        sys.exit(1)

    # Run analysis
    console.print()
    console.print("[bold]Running analysis pipeline...[/bold]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Analyzing...", total=None)
        profiler = Profiler()
        profile = profiler.profile(data)
        progress.update(task, completed=True)

    # Save JSON profile
    json_path = output / f"{data.user.id}_profile.json"
    profiler.save_profile(profile, json_path)
    console.print(f"[green]Profile saved to {json_path}[/green]")

    # Print summary
    console.print()
    console.print(Panel(profile.summary, title="Analysis Summary", border_style="green"))

    # Detailed tables
    if profile.personality:
        table = Table(title="Big Five Personality Traits")
        table.add_column("Trait", style="cyan")
        table.add_column("Score", style="magenta")
        table.add_column("Bar", style="green")
        for key, name in [
            ("openness", "Openness"),
            ("conscientiousness", "Conscientiousness"),
            ("extraversion", "Extraversion"),
            ("agreeableness", "Agreeableness"),
            ("neuroticism", "Neuroticism"),
        ]:
            score = profile.personality.get("big_five", {}).get(key, 0)
            bar = "█" * int(score / 5) + "░" * (20 - int(score / 5))
            table.add_row(name, f"{score:.1f}", bar)
        console.print(table)

    if profile.interests:
        table = Table(title="Top Interests")
        table.add_column("Domain", style="cyan")
        table.add_column("Score", style="magenta")
        for domain, score in profile.interests.get("top_domains", [])[:8]:
            table.add_row(domain, f"{score:.1f}")
        console.print(table)

    # Generate HTML report
    if not json_only:
        console.print()
        console.print("[bold]Generating interactive report...[/bold]")
        generator = ReportGenerator(output_dir=output)
        report_path = generator.generate(profile)
        console.print(f"[green bold]Report generated:[/green bold] {report_path}")

        # Try to open in browser
        import webbrowser
        webbrowser.open(f"file://{report_path.absolute()}")

    console.print()
    console.print("[bold green]Done![/bold green]")


@main.command()
@click.argument("profile_file", type=click.Path(exists=True, path_type=Path))
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output HTML path")
def report(profile_file: Path, output: Path | None):
    """Generate HTML report from a saved profile JSON."""
    profiler = Profiler()
    profile = profiler.load_profile(profile_file)
    generator = ReportGenerator()
    path = generator.generate(profile, output)
    console.print(f"[green]Report generated: {path}[/green]")

    import webbrowser
    webbrowser.open(f"file://{path.absolute()}")


@main.command()
@click.option(
    "--host",
    default="127.0.0.1",
    help="Host to bind to",
)
@click.option(
    "--port", "-p",
    default=8765,
    type=int,
    help="Port to listen on",
)
@click.option(
    "--no-open",
    is_flag=True,
    help="Don't open browser automatically",
)
def web(host: str, port: int, no_open: bool):
    """Launch the web interface for Zhihu Profiler."""
    console.print()
    console.print(Panel.fit(
        "[bold magenta]Zhihu Profiler[/bold magenta] · Web Interface",
        border_style="magenta",
    ))
    console.print()

    if not no_open:
        import webbrowser
        webbrowser.open(f"http://{host}:{port}")

    console.print(f"[green]Starting web server at http://{host}:{port}[/green]")
    console.print("[dim]Press Ctrl+C to stop[/dim]")
    console.print()

    import uvicorn
    from .web.server import app
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
