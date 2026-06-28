from pathlib import Path
import json
from typing import Annotated

import typer
from rich.console import Console
import yaml

from . import __version__
from .compare.engine import compare_report
from .elfscan.scanner import scan_path
from .problem.models import Problem
from .profile.detect import detect_current_system
from .profile.generate import generate_target_profile_from_facts
from .profile.loader import (
    ProfileLoadError,
    ProfileNotFoundError,
    list_builtin_profiles,
    load_profile_file,
    load_target_profile,
)
from .profile.models import SystemFacts, TargetProfile
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
    target: Annotated[str | None, typer.Option("--target", help="Built-in profile id.")] = None,
    target_file: Annotated[
        Path | None,
        typer.Option("--target-file", help="External YAML target profile."),
    ] = None,
    json_output: Annotated[Path | None, typer.Option("--json", help="Write JSON report.")] = None,
) -> None:
    """Compare one Linux artifact with a target profile."""
    if (target is None) == (target_file is None):
        console.print("[red]Provide exactly one of --target or --target-file.[/red]")
        raise typer.Exit(2)

    try:
        profile = (
            load_profile_file(target_file)
            if target_file is not None
            else load_target_profile(target or "")
        )
    except (ProfileNotFoundError, ProfileLoadError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(2) from exc

    scan_report = scan_path(path)
    if scan_report.elf is None or scan_report.elf.elf_class is None:
        report = scan_report.model_copy(
            update={
                "target": profile,
                "problems": [
                    *scan_report.problems,
                    Problem(
                        id="scan.failed",
                        severity="HIGH",
                        title="Artifact could not be scanned as ELF",
                        details="readelf did not return a parseable ELF header.",
                        artifact_path=str(path),
                    ),
                ],
            }
        )
        if json_output is not None:
            write_json_report(report, json_output)
        render_report(report, console)
        raise typer.Exit(2)

    report = compare_report(scan_report, profile)
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


@profiles_app.command("detect")
def profiles_detect(
    json_output: Annotated[
        Path | None,
        typer.Option("--json", help="Write raw detected system facts as JSON."),
    ] = None,
) -> None:
    """Detect raw facts from the current Linux system."""
    facts = detect_current_system()
    if json_output is not None:
        _write_system_facts_json(facts, json_output)
    _render_system_facts(facts)


@profiles_app.command("generate")
def profiles_generate(
    from_current: Annotated[
        bool,
        typer.Option("--from-current", help="Generate from the current Linux system."),
    ] = False,
    name: Annotated[str, typer.Option("--name", help="Generated target profile id.")] = "local",
    output: Annotated[
        Path | None, typer.Option("--output", help="Output YAML profile path.")
    ] = None,
) -> None:
    """Generate a YAML target profile."""
    if not from_current:
        console.print("[red]Only --from-current is supported in v0.4.[/red]")
        raise typer.Exit(2)
    if output is None:
        console.print("[red]--output is required.[/red]")
        raise typer.Exit(2)

    facts = detect_current_system()
    profile = generate_target_profile_from_facts(facts, name=name)
    _write_target_profile_yaml(profile, output)
    console.print(f"[bold]Profile:[/bold] {output}")
    console.print("[bold]Status:[/bold] generated")
    console.print(f"[bold]Target:[/bold] {profile.id}")
    console.print(f"[bold]Architecture:[/bold] {profile.arch}")


@profiles_app.command("validate")
def profiles_validate(
    profile_file: Annotated[Path, typer.Argument(help="YAML target profile path.")],
    json_output: Annotated[
        Path | None,
        typer.Option("--json", help="Write validation result as JSON."),
    ] = None,
) -> None:
    """Validate a YAML target profile."""
    try:
        profile = load_profile_file(profile_file)
    except (ProfileNotFoundError, ProfileLoadError) as exc:
        if json_output is not None:
            json_output.write_text(
                json.dumps(
                    {"profile": str(profile_file), "status": "invalid", "error": str(exc)},
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        console.print(f"[bold]Profile:[/bold] {profile_file}")
        console.print("[bold]Status:[/bold] [red]invalid[/red]")
        console.print(f"[bold]Error:[/bold] {exc}")
        raise typer.Exit(2) from exc

    if json_output is not None:
        json_output.write_text(
            json.dumps(
                {
                    "profile": str(profile_file),
                    "status": "valid",
                    "target": profile.id,
                    "architecture": profile.arch,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    console.print(f"[bold]Profile:[/bold] {profile_file}")
    console.print("[bold]Status:[/bold] [green]valid[/green]")
    console.print(f"[bold]Target:[/bold] {profile.id}")
    console.print(f"[bold]Architecture:[/bold] {profile.arch}")


def _write_system_facts_json(facts: SystemFacts, path: Path) -> None:
    path.write_text(facts.model_dump_json(indent=2) + "\n", encoding="utf-8")


def _write_target_profile_yaml(profile: TargetProfile, path: Path) -> None:
    raw = profile.model_dump(mode="json", exclude_none=True)
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")


def _render_system_facts(facts: SystemFacts) -> None:
    console.print("[bold]System profile detected[/bold]")
    console.print(
        f"[bold]OS:[/bold] {facts.os_release.pretty_name or facts.os_release.id or 'unknown'}"
    )
    console.print(f"[bold]Architecture:[/bold] {facts.architecture or 'unknown'}")
    console.print(f"[bold]glibc:[/bold] {facts.glibc_version or 'unknown'}")
    console.print(f"[bold]GLIBC max:[/bold] {_last_or_unknown(facts.symbol_versions.glibc)}")
    console.print(f"[bold]GLIBCXX max:[/bold] {_last_or_unknown(facts.symbol_versions.glibcxx)}")
    console.print(f"[bold]CXXABI max:[/bold] {_last_or_unknown(facts.symbol_versions.cxxabi)}")
    console.print(f"[bold]Interpreters:[/bold] {len(facts.dynamic_linkers)}")
    console.print(f"[bold]Libraries:[/bold] {len(facts.libraries)}")
    console.print(f"[bold]Warnings:[/bold] {len(facts.warnings)}")


def _last_or_unknown(values: list[str]) -> str:
    if not values:
        return "unknown"
    return values[-1]


if __name__ == "__main__":
    app()
