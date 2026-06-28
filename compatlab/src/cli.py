from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from . import __version__
from .compare.engine import compare_report
from .elfscan.scanner import scan_path
from .profile.loader import (
    ProfileNotFoundError,
    list_builtin_profiles,
    load_target_profile,
)
from .report.json import write_json_report
from .report.pretty import render_profiles, render_report

app = typer.Typer(help="Preflight compatibility checker for Linux binary artifacts.")
profiles_app = typer.Typer(help="Inspect built-in target profiles.")
app.add_typer(profiles_app, name="profiles")
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"compatlab {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option("--version", callback=_version_callback, help="Show version and exit."),
    ] = False,
) -> None:
    _ = version


@app.command()
def scan(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=True, dir_okay=False)],
    json_output: Annotated[Path | None, typer.Option("--json", help="Write JSON report.")] = None,
) -> None:
    """Scan one Linux artifact and print a structured stub report."""
    report = scan_path(path)
    if json_output is not None:
        write_json_report(report, json_output)
    render_report(report, console)


@app.command()
def compare(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=True, dir_okay=False)],
    target: Annotated[str, typer.Option("--target", help="Built-in profile id or YAML path.")],
    json_output: Annotated[Path | None, typer.Option("--json", help="Write JSON report.")] = None,
) -> None:
    """Compare one Linux artifact with a target profile."""
    try:
        profile = load_target_profile(target)
    except ProfileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(2) from exc

    report = compare_report(scan_path(path), profile)
    if json_output is not None:
        write_json_report(report, json_output)
    render_report(report, console)
    if not report.is_compatible:
        raise typer.Exit(1)


@profiles_app.command("list")
def profiles_list() -> None:
    """List built-in target profiles."""
    render_profiles(list_builtin_profiles(), console)


@profiles_app.command("show")
def profiles_show(
    target: Annotated[str, typer.Argument(help="Built-in profile id or YAML path.")],
) -> None:
    """Show one target profile."""
    try:
        profile = load_target_profile(target)
    except ProfileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(2) from exc
    console.print_json(profile.model_dump_json(indent=2))


if __name__ == "__main__":
    app()
