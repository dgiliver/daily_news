"""Command-line interface for Daily News Aggregator."""

from datetime import datetime, timedelta, date
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from daily_news.config import settings
from daily_news.storage import NewsDatabase
from daily_news.sources import load_sources

app = typer.Typer(
    name="daily-news",
    help="World News Aggregator - Search and browse your news archive",
    no_args_is_help=True,
)
console = Console()


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query (supports full-text search)"),
    days: int = typer.Option(7, "--days", "-d", help="Search last N days"),
    region: str = typer.Option(None, "--region", "-r", help="Filter by region"),
    category: str = typer.Option(None, "--category", "-c", help="Filter by category"),
    limit: int = typer.Option(20, "--limit", "-l", help="Max results"),
) -> None:
    """Search the news archive using full-text search."""
    db = NewsDatabase()
    since = datetime.utcnow() - timedelta(days=days)

    results = db.search_articles(
        query=query,
        since=since,
        region=region,
        category=category,
        limit=limit,
    )

    if not results:
        console.print(f"[yellow]No results found for '{query}'[/yellow]")
        return

    table = Table(title=f"Search Results: '{query}' (last {days} days)")
    table.add_column("Date", style="dim", width=10)
    table.add_column("Score", justify="right", width=6)
    table.add_column("Region", style="cyan", width=12)
    table.add_column("Title", width=50)
    table.add_column("Source", style="green", width=15)

    for article in results:
        table.add_row(
            article.collected_at.strftime("%m/%d"),
            f"{article.significance_score:.0f}",
            article.source_region.value[:12],
            article.title[:50] + ("..." if len(article.title) > 50 else ""),
            article.source_name[:15],
        )

    console.print(table)
    console.print(f"\n[dim]Found {len(results)} results[/dim]")


@app.command()
def digest(
    date_str: str = typer.Option(
        None, "--date", "-d", help="Date (YYYY-MM-DD), defaults to today"
    ),
    limit: int = typer.Option(15, "--limit", "-l", help="Number of stories"),
) -> None:
    """Show the digest for a specific date."""
    db = NewsDatabase()

    if date_str:
        try:
            target_date = date.fromisoformat(date_str)
        except ValueError:
            console.print("[red]Invalid date format. Use YYYY-MM-DD[/red]")
            raise typer.Exit(1)
    else:
        target_date = date.today()

    articles = db.get_articles_by_date(target_date, limit=limit)

    if not articles:
        console.print(f"[yellow]No digest found for {target_date}[/yellow]")
        return

    console.print(
        Panel(
            f"[bold]World News Digest[/bold]\n{target_date.strftime('%B %d, %Y')}",
            style="blue",
        )
    )

    for i, article in enumerate(articles, 1):
        region_color = {
            "americas_us": "blue",
            "americas_latam": "magenta",
            "europe": "green",
            "asia_pacific": "red",
            "middle_east": "yellow",
            "africa": "cyan",
            "local_ny": "orange3",
        }.get(article.source_region.value, "white")

        console.print(f"\n[bold]{i}. {article.title}[/bold]")
        console.print(
            f"   [{region_color}]{article.source_region.value}[/{region_color}] | "
            f"{article.source_name} | Score: {article.significance_score:.0f}"
        )
        console.print(f"   [dim]{article.url}[/dim]")
        if article.description:
            console.print(f"   {article.description[:150]}...")


@app.command()
def sources() -> None:
    """List all configured news sources."""
    all_sources = load_sources()

    table = Table(title=f"Configured News Sources ({len(all_sources)} total)")
    table.add_column("Name", width=30)
    table.add_column("Region", style="cyan", width=15)
    table.add_column("Category", style="green", width=12)
    table.add_column("Language", width=8)
    table.add_column("Priority", width=8)

    # Sort by region then name
    all_sources.sort(key=lambda s: (s.region.value, s.name))

    for source in all_sources:
        priority_style = {
            "high": "bold green",
            "medium": "yellow",
            "low": "dim",
        }.get(source.priority, "")

        table.add_row(
            source.name[:30],
            source.region.value,
            source.category.value,
            source.language,
            f"[{priority_style}]{source.priority}[/{priority_style}]",
        )

    console.print(table)

    # Summary by region
    console.print("\n[bold]Sources by Region:[/bold]")
    from collections import Counter

    region_counts = Counter(s.region.value for s in all_sources)
    for region, count in sorted(region_counts.items()):
        console.print(f"  {region}: {count}")


@app.command()
def stats(
    days: int = typer.Option(30, "--days", "-d", help="Stats for last N days"),
) -> None:
    """Show collection statistics."""
    db = NewsDatabase()
    stats_data = db.get_stats(days=days)

    console.print(Panel(f"[bold]Collection Statistics[/bold]\nLast {days} days", style="blue"))

    console.print(f"\n[bold]Total Articles:[/bold] {stats_data['total_articles']:,}")
    console.print(f"[bold]Collection Runs:[/bold] {stats_data['collection_runs']}")

    if stats_data["articles_by_region"]:
        console.print("\n[bold]Articles by Region:[/bold]")
        table = Table(show_header=False)
        table.add_column("Region", width=20)
        table.add_column("Count", justify="right")

        for region, count in sorted(
            stats_data["articles_by_region"].items(), key=lambda x: -x[1]
        ):
            table.add_row(region, str(count))

        console.print(table)


@app.command()
def export(
    output: str = typer.Argument(..., help="Output file path (CSV or JSON)"),
    days: int = typer.Option(30, "--days", "-d", help="Export last N days"),
    format: str = typer.Option("csv", "--format", "-f", help="Output format: csv or json"),
) -> None:
    """Export articles to file."""
    import csv
    import json

    db = NewsDatabase()
    articles = db.get_recent_articles(days=days, limit=10000)

    if not articles:
        console.print("[yellow]No articles to export[/yellow]")
        return

    output_path = Path(output)

    if format.lower() == "json" or output_path.suffix == ".json":
        data = [
            {
                "id": a.id,
                "title": a.title,
                "original_title": a.original_title,
                "url": str(a.url),
                "source": a.source_name,
                "region": a.source_region.value,
                "category": a.source_category.value,
                "significance_score": a.significance_score,
                "collected_at": a.collected_at.isoformat(),
                "description": a.description,
            }
            for a in articles
        ]
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

    else:  # CSV
        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "id", "title", "url", "source", "region", "category",
                "score", "collected_at", "description"
            ])
            for a in articles:
                writer.writerow([
                    a.id, a.title, str(a.url), a.source_name,
                    a.source_region.value, a.source_category.value,
                    a.significance_score, a.collected_at.isoformat(),
                    a.description[:200] if a.description else "",
                ])

    console.print(f"[green]Exported {len(articles)} articles to {output_path}[/green]")


@app.command()
def recent(
    days: int = typer.Option(1, "--days", "-d", help="Show articles from last N days"),
    limit: int = typer.Option(10, "--limit", "-l", help="Max articles to show"),
) -> None:
    """Show recent top articles."""
    db = NewsDatabase()
    articles = db.get_recent_articles(days=days, limit=limit)

    if not articles:
        console.print("[yellow]No recent articles found[/yellow]")
        return

    table = Table(title=f"Top {limit} Articles (last {days} day(s))")
    table.add_column("Score", justify="right", width=6)
    table.add_column("Region", style="cyan", width=12)
    table.add_column("Title", width=50)
    table.add_column("Source", style="green", width=15)

    for article in articles:
        table.add_row(
            f"{article.significance_score:.0f}",
            article.source_region.value[:12],
            article.title[:50] + ("..." if len(article.title) > 50 else ""),
            article.source_name[:15],
        )

    console.print(table)


if __name__ == "__main__":
    app()
