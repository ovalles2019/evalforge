"""EvalForge command-line interface."""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import get_settings
from .models import Dimension, RunResult
from .reporting import evaluate_gate, load_thresholds, write_junit
from .runner import run_eval
from .store import ResultsStore

app = typer.Typer(
    add_completion=False,
    help="EvalForge — Multi-Dimensional AI Eval Harness.",
    no_args_is_help=True,
)
console = Console()


def _parse_dimensions(value: str | None) -> list[Dimension] | None:
    if not value:
        return None
    return [Dimension(v.strip()) for v in value.split(",") if v.strip()]


def _metrics_table(run: RunResult) -> Table:
    table = Table(title=f"EvalForge run {run.run_id}  ({run.target} / judge={run.judge})")
    table.add_column("Dimension", style="cyan")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_column("Cases", justify="right")
    for dim in run.dimensions:
        first = True
        for name, value in dim.metrics.items():
            table.add_row(
                dim.dimension.value if first else "",
                name,
                f"{value:.4f}",
                str(dim.n_cases) if first else "",
            )
            first = False
    return table


@app.command()
def version() -> None:
    """Print the EvalForge version."""
    console.print(f"EvalForge {__version__}")


@app.command()
def run(
    dimensions: str = typer.Option(
        None, "--dimensions", "-d", help="Comma list: rag,tooluse,guardrail (default all)."
    ),
    persist: bool = typer.Option(True, help="Persist the run to the results store."),
    junit: str = typer.Option(None, help="Optional path to write JUnit XML."),
) -> None:
    """Run the eval suites against the configured target and print metrics."""
    settings = get_settings()
    result = asyncio.run(run_eval(settings, _parse_dimensions(dimensions)))

    if persist:
        ResultsStore(settings.database_url).save(result)
    if junit:
        write_junit(junit, result)

    console.print(_metrics_table(result))
    console.print(f"[dim]run_id={result.run_id} git={result.git_ref}@{result.git_sha}[/dim]")


@app.command()
def gate(
    dimensions: str = typer.Option(None, "--dimensions", "-d", help="Comma list (default all)."),
    junit: str = typer.Option("reports/junit.xml", help="Path to write JUnit XML."),
    persist: bool = typer.Option(True, help="Persist the run to the results store."),
    fresh: bool = typer.Option(
        True, "--fresh/--use-latest", help="Run a fresh eval (default) or gate the latest run."
    ),
) -> None:
    """Run the eval and enforce thresholds + regression checks. Exits non-zero on failure."""
    settings = get_settings()
    store = ResultsStore(settings.database_url)

    if fresh:
        result = asyncio.run(run_eval(settings, _parse_dimensions(dimensions)))
        # Baseline = most recent prior run (before we persist this one).
        baseline = store.baseline_metrics(result.git_ref, result.run_id)
        if persist:
            store.save(result)
    else:
        result = store.latest_run()
        if result is None:
            console.print("[red]No runs recorded yet. Run `evalforge run` first.[/red]")
            raise typer.Exit(code=2)
        baseline = store.baseline_metrics(result.git_ref, result.run_id)

    thresholds = load_thresholds(settings.thresholds_file)
    report = evaluate_gate(result.all_metrics(), thresholds, baseline)

    write_junit(junit, result, report)
    console.print(_metrics_table(result))
    console.print(report.summary())
    console.print(f"[dim]JUnit written to {junit}[/dim]")

    if not report.passed:
        console.print("[bold red]CI gate failed.[/bold red]")
        raise typer.Exit(code=1)
    console.print("[bold green]CI gate passed.[/bold green]")


@app.command()
def history(
    metric: str = typer.Argument(..., help="Metric name, e.g. rag.groundedness."),
    limit: int = typer.Option(20, help="Number of recent runs to show."),
) -> None:
    """Show the recent trend for a single metric."""
    store = ResultsStore(get_settings().database_url)
    points = store.metric_history(metric, limit)
    if not points:
        console.print(f"[yellow]No history for metric '{metric}'.[/yellow]")
        return
    table = Table(title=f"History: {metric}")
    table.add_column("Timestamp")
    table.add_column("Value", justify="right")
    for at, value in reversed(points):
        table.add_row(at, f"{value:.4f}")
    console.print(table)


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Bind host."),
    port: int = typer.Option(8000, help="Bind port."),
    reload: bool = typer.Option(False, help="Auto-reload (dev)."),
) -> None:
    """Start the FastAPI server (API + Prometheus /metrics endpoint)."""
    import uvicorn

    uvicorn.run("evalforge.api:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
