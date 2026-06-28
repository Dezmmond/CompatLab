from typing import Protocol

from rich.console import Console
from rich.table import Table

from compatlab.src.report.models import ArtifactReport


class ProfileRow(Protocol):
    id: str
    name: str
    arch: str


def render_report(report: ArtifactReport, console: Console) -> None:
    console.print(f"[bold]Artifact:[/bold] {report.artifact.path}")
    console.print(f"[bold]Kind:[/bold] {report.artifact.kind}")
    if report.artifact.size_bytes is not None:
        console.print(f"[bold]Size:[/bold] {report.artifact.size_bytes} bytes")
    if report.elf is not None:
        _render_elf(report, console)
    if report.target is not None:
        console.print(f"[bold]Target:[/bold] {report.target.name} ({report.target.id})")
        status = "PASS" if report.is_compatible else "FAIL"
        style = "green" if report.is_compatible else "red"
        console.print(f"[bold]Compatibility:[/bold] [{style}]{status}[/{style}]")
    else:
        console.print("[bold]Scan:[/bold] [green]OK[/green]")
        console.print(f"[bold]Problems:[/bold] {len(report.problems)}")
        console.print(f"[bold]Warnings:[/bold] {len(report.warnings)}")
    if report.dependency_graph is not None:
        _render_dependency_graph(report, console)
    if report.diagnostics:
        _render_diagnostics(report, console)
    _render_summary(report, console)

    if report.problems:
        table = Table(title="Problems")
        table.add_column("Severity")
        table.add_column("ID")
        table.add_column("Details")
        for problem in report.problems:
            table.add_row(problem.severity, problem.id, problem.details)
        console.print(table)
    if report.warnings:
        table = Table(title="Warnings")
        table.add_column("Severity")
        table.add_column("Title")
        table.add_column("Details")
        for warning in report.warnings:
            table.add_row(warning.severity, warning.title, warning.details)
        console.print(table)


def _render_elf(report: ArtifactReport, console: Console) -> None:
    elf = report.elf
    if elf is None:
        return
    fields = [
        ("Class", elf.elf_class),
        ("Endianness", elf.endianness),
        ("OS ABI", elf.os_abi),
        ("Machine", elf.machine),
        ("ELF Type", elf.elf_type),
        ("Entry point", elf.entry_point),
        ("Dynamic", _yes_no(elf.is_dynamic)),
        ("Interpreter", elf.interpreter),
    ]
    for label, value in fields:
        if value is not None:
            console.print(f"[bold]{label}:[/bold] {value}")

    _render_list(console, "Needed libraries", elf.needed)
    _render_list(console, "RPATH", elf.rpath, empty="none")
    _render_list(console, "RUNPATH", elf.runpath, empty="none")
    if elf.required_versions:
        grouped: dict[str, list[str]] = {}
        for version in elf.required_versions:
            grouped.setdefault(version.namespace, []).append(version.raw)
        console.print("[bold]Required versions:[/bold]")
        for namespace, versions in grouped.items():
            console.print(f"  [bold]{namespace}:[/bold]")
            for version in versions:
                console.print(f"    - {version}")


def _render_dependency_graph(report: ArtifactReport, console: Console) -> None:
    graph = report.dependency_graph
    if graph is None:
        return
    console.print(f"[bold]Dependency nodes:[/bold] {len(graph.nodes)}")
    console.print(f"[bold]Dependency edges:[/bold] {len(graph.edges)}")
    table = Table(title="Dependency Resolution")
    table.add_column("From")
    table.add_column("Needed")
    table.add_column("Source")
    table.add_column("Resolved")
    for edge in graph.edges:
        resolved = edge.resolved_artifact_id or edge.resolved_path or edge.message or ""
        table.add_row(edge.from_artifact_id, edge.needed_name, edge.resolution_kind.value, resolved)
    console.print(table)


def _render_diagnostics(report: ArtifactReport, console: Console) -> None:
    table = Table(title="Diagnostics")
    table.add_column("Severity")
    table.add_column("Code", no_wrap=True)
    table.add_column("Title")
    table.add_column("Affected")
    table.add_column("Hint")
    for issue in report.diagnostics:
        table.add_row(
            issue.severity.value.upper(),
            issue.code,
            issue.title,
            issue.dependency_name or issue.affected_path or "",
            issue.hint or "",
        )
    console.print(table)


def _render_summary(report: ArtifactReport, console: Console) -> None:
    summary = report.summary
    style = (
        "red"
        if summary.status == "failed"
        else "yellow"
        if summary.status == "warning"
        else "green"
    )
    console.print("[bold]Summary:[/bold]")
    console.print(f"  [bold]Status:[/bold] [{style}]{summary.status}[/{style}]")
    console.print(f"  [bold]Errors:[/bold] {summary.errors}")
    console.print(f"  [bold]Warnings:[/bold] {summary.warnings}")
    console.print(f"  [bold]Infos:[/bold] {summary.infos}")


def _render_list(console: Console, title: str, values: list[str], empty: str | None = None) -> None:
    if not values:
        if empty is not None:
            console.print(f"[bold]{title}:[/bold] {empty}")
        return
    console.print(f"[bold]{title}:[/bold]")
    for value in values:
        console.print(f"  - {value}")


def _yes_no(value: bool | None) -> str | None:
    if value is None:
        return None
    return "yes" if value else "no"


def render_profiles(profiles: list[ProfileRow], console: Console) -> None:
    table = Table()
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Arch")
    table.add_column("glibc")
    for profile in profiles:
        table.add_row(profile.id, profile.name, profile.arch, profile.libc.version)
    console.print(table)
