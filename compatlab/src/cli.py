from pathlib import Path
import json
from typing import Annotated

import typer
from rich.console import Console
import yaml

from . import __version__
from .bundle.models import DependencyGraph, DependencyResolutionKind
from .bundle.resolver import (
    DEFAULT_MAX_DEPTH,
    DEFAULT_MAX_FILES,
    BundleResolutionError,
    resolve_bundle_dependencies,
)
from .compare.engine import compare_report
from .elfscan.scanner import scan_path
from .problem.models import Problem
from .profile.detect import detect_current_system
from .profile.docker_cli import DockerError
from .profile.docker_image import detect_docker_image_system
from .profile.generate import generate_target_profile_from_facts
from .profile.loader import (
    ProfileLoadError,
    ProfileNotFoundError,
    list_builtin_profiles,
    load_profile_file,
    load_target_profile,
)
from .profile.models import SystemFacts, TargetProfile
from .profile.runtime_presets import (
    RuntimePreset,
    RuntimePresetError,
    get_runtime_preset,
    list_runtime_presets,
)
from .report.json import write_json_report
from .report.pretty import render_profiles, render_report

app = typer.Typer(help="Preflight compatibility checker for Linux binary artifacts.")
profiles_app = typer.Typer(help="Inspect built-in target profiles.")
runtime_presets_app = typer.Typer(help="Inspect built-in Docker runtime presets.")
app.add_typer(profiles_app, name="profiles")
profiles_app.add_typer(runtime_presets_app, name="runtime-presets")
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
    bundle_root: Annotated[
        Path | None,
        typer.Option("--bundle-root", exists=True, file_okay=False, dir_okay=True),
    ] = None,
    recursive: Annotated[
        bool, typer.Option("--recursive", help="Resolve transitive bundled ELF dependencies.")
    ] = False,
    max_depth: Annotated[
        int, typer.Option("--max-depth", help="Maximum recursive dependency depth.")
    ] = DEFAULT_MAX_DEPTH,
    max_files: Annotated[
        int, typer.Option("--max-files", help="Maximum files to index under bundle root.")
    ] = DEFAULT_MAX_FILES,
    json_output: Annotated[Path | None, typer.Option("--json", help="Write JSON report.")] = None,
) -> None:
    """Scan one Linux artifact and print a structured stub report."""
    report = scan_path(path)
    if bundle_root is not None:
        try:
            resolution = resolve_bundle_dependencies(
                path,
                bundle_root,
                recursive=recursive,
                max_depth=max_depth,
                max_files=max_files,
            )
        except BundleResolutionError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(2) from exc
        report = report.model_copy(
            update={
                "dependency_graph": resolution.graph,
                "warnings": [*report.warnings, *resolution.warnings],
            }
        )
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
    bundle_root: Annotated[
        Path | None,
        typer.Option("--bundle-root", exists=True, file_okay=False, dir_okay=True),
    ] = None,
    recursive: Annotated[
        bool, typer.Option("--recursive", help="Resolve transitive bundled ELF dependencies.")
    ] = False,
    max_depth: Annotated[
        int, typer.Option("--max-depth", help="Maximum recursive dependency depth.")
    ] = DEFAULT_MAX_DEPTH,
    max_files: Annotated[
        int, typer.Option("--max-files", help="Maximum files to index under bundle root.")
    ] = DEFAULT_MAX_FILES,
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

    if bundle_root is not None:
        try:
            resolution = resolve_bundle_dependencies(
                path,
                bundle_root,
                target=profile,
                recursive=recursive,
                max_depth=max_depth,
                max_files=max_files,
            )
        except BundleResolutionError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(2) from exc
        bundled_libraries = resolution.bundled_library_names
        report = compare_report(
            scan_report,
            profile,
            assumed_provided_libraries=bundled_libraries,
        )
        problems = [*report.problems, *_dependency_problems(resolution.graph)]
        warnings = [*report.warnings, *resolution.warnings]
        for artifact_id, artifact_report in resolution.reports.items():
            if artifact_id == resolution.graph.entrypoint_artifact_id:
                continue
            compared = compare_report(
                artifact_report,
                profile,
                assumed_provided_libraries=bundled_libraries,
            )
            problems.extend(compared.problems)
            warnings.extend(compared.warnings)
        report = report.model_copy(
            update={
                "dependency_graph": resolution.graph,
                "problems": problems,
                "warnings": warnings,
            }
        )
    else:
        report = compare_report(scan_report, profile)
    if json_output is not None:
        write_json_report(report, json_output)
    render_report(report, console)
    if not report.is_compatible:
        raise typer.Exit(1)


def _dependency_problems(graph: DependencyGraph) -> list[Problem]:
    problems: list[Problem] = []
    for edge in graph.unresolved_dependencies:
        severity = "HIGH"
        title = "Dependency could not be resolved"
        if edge.resolution_kind == DependencyResolutionKind.AMBIGUOUS:
            severity = "HIGH"
            title = "Dependency resolution is ambiguous"
        problems.append(
            Problem(
                id=f"bundle.dependency_{edge.resolution_kind.value}",
                severity=severity,
                title=title,
                details=edge.message or f"{edge.needed_name} could not be resolved.",
                artifact_path=edge.from_artifact_id,
                evidence={
                    "from_artifact_id": edge.from_artifact_id,
                    "needed": edge.needed_name,
                    "candidates": ", ".join(edge.candidates),
                },
            )
        )
    return problems


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


@runtime_presets_app.command("list")
def runtime_presets_list() -> None:
    """List built-in Docker runtime presets."""
    console.print("[bold]Available runtime presets:[/bold]")
    for preset in list_runtime_presets():
        console.print(f"{preset.name:18} {preset.description}")


@runtime_presets_app.command("show")
def runtime_presets_show(
    name: Annotated[str, typer.Argument(help="Runtime preset name.")],
) -> None:
    """Show one Docker runtime preset."""
    try:
        preset = get_runtime_preset(name)
    except RuntimePresetError as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(2) from exc
    _render_runtime_preset(preset)


@profiles_app.command("detect")
def profiles_detect(
    from_image: Annotated[
        str | None,
        typer.Option("--from-image", help="Detect raw facts from a Docker image."),
    ] = None,
    platform: Annotated[
        str | None,
        typer.Option("--platform", help="Docker image platform, for example linux/amd64."),
    ] = None,
    pull: Annotated[
        bool, typer.Option("--pull", help="Pull Docker image before detection.")
    ] = False,
    runtime_preset: Annotated[
        str | None,
        typer.Option(
            "--runtime-preset", help="Install a built-in runtime preset before detection."
        ),
    ] = None,
    json_output: Annotated[
        Path | None,
        typer.Option("--json", help="Write raw detected system facts as JSON."),
    ] = None,
) -> None:
    """Detect raw facts from the current Linux system."""
    if runtime_preset is not None and from_image is None:
        console.print("[red]--runtime-preset is valid only with --from-image.[/red]")
        raise typer.Exit(2)
    try:
        facts = (
            detect_docker_image_system(
                from_image,
                platform=platform,
                pull=pull,
                runtime_preset=runtime_preset,
            )
            if from_image is not None
            else detect_current_system()
        )
    except (DockerError, RuntimePresetError) as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(2) from exc
    if json_output is not None:
        _write_system_facts_json(facts, json_output)
    _render_system_facts(facts)


@profiles_app.command("generate")
def profiles_generate(
    from_current: Annotated[
        bool,
        typer.Option("--from-current", help="Generate from the current Linux system."),
    ] = False,
    from_image: Annotated[
        str | None,
        typer.Option("--from-image", help="Generate from a Docker image."),
    ] = None,
    platform: Annotated[
        str | None,
        typer.Option("--platform", help="Docker image platform, for example linux/amd64."),
    ] = None,
    pull: Annotated[
        bool, typer.Option("--pull", help="Pull Docker image before generation.")
    ] = False,
    runtime_preset: Annotated[
        str | None,
        typer.Option(
            "--runtime-preset", help="Install a built-in runtime preset before generation."
        ),
    ] = None,
    name: Annotated[str, typer.Option("--name", help="Generated target profile id.")] = "local",
    output: Annotated[
        Path | None, typer.Option("--output", help="Output YAML profile path.")
    ] = None,
) -> None:
    """Generate a YAML target profile."""
    if from_current == (from_image is not None):
        console.print("[red]Provide exactly one of --from-current or --from-image.[/red]")
        raise typer.Exit(2)
    if runtime_preset is not None and from_image is None:
        console.print("[red]--runtime-preset is valid only with --from-image.[/red]")
        raise typer.Exit(2)
    if output is None:
        console.print("[red]--output is required.[/red]")
        raise typer.Exit(2)

    try:
        facts = (
            detect_docker_image_system(
                from_image,
                platform=platform,
                pull=pull,
                runtime_preset=runtime_preset,
            )
            if from_image is not None
            else detect_current_system()
        )
    except (DockerError, RuntimePresetError) as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(2) from exc

    profile = generate_target_profile_from_facts(facts, name=name)
    _write_target_profile_yaml(profile, output)
    if from_image is not None:
        console.print("[bold]Docker image profile generated[/bold]")
        console.print(f"[bold]Image:[/bold] {from_image}")
        if runtime_preset is not None:
            console.print(f"[bold]Runtime preset:[/bold] {runtime_preset}")
        console.print(f"[bold]Name:[/bold] {profile.id}")
        console.print(f"[bold]Architecture:[/bold] {profile.arch}")
        console.print(f"[bold]OS:[/bold] {profile.name}")
        console.print(f"[bold]Output:[/bold] {output}")
    else:
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


def _render_runtime_preset(preset: RuntimePreset) -> None:
    console.print(f"[bold]Runtime preset:[/bold] {preset.name}")
    console.print(f"[bold]Description:[/bold] {preset.description}")
    console.print(f"[bold]Package managers:[/bold] {', '.join(preset.supported_package_managers)}")
    console.print("[bold]Packages:[/bold]")
    for manager in preset.supported_package_managers:
        packages = preset.packages_by_manager.get(manager, [])
        console.print(f"  {manager}: {', '.join(packages)}")
    if preset.limitations:
        console.print("[bold]Limitations:[/bold]")
        for limitation in preset.limitations:
            console.print(f"  {limitation}")


def _last_or_unknown(values: list[str]) -> str:
    if not values:
        return "unknown"
    return values[-1]


if __name__ == "__main__":
    app()
