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
    console.print(f"[bold]Type:[/bold] {report.artifact.kind}")
    if report.artifact.size_bytes is not None:
        console.print(f"[bold]Size:[/bold] {report.artifact.size_bytes} bytes")
    if report.target is not None:
        console.print(f"[bold]Target:[/bold] {report.target.name} ({report.target.id})")

    status = "PASS" if report.is_compatible else "FAIL"
    style = "green" if report.is_compatible else "red"
    console.print(f"[bold]Compatibility:[/bold] [{style}]{status}[/{style}]")

    if report.problems:
        table = Table(title="Problems")
        table.add_column("Severity")
        table.add_column("ID")
        table.add_column("Details")
        for problem in report.problems:
            table.add_row(problem.severity, problem.id, problem.details)
        console.print(table)


def render_profiles(profiles: list[ProfileRow], console: Console) -> None:
    table = Table()
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Arch")
    table.add_column("glibc")
    for profile in profiles:
        table.add_row(profile.id, profile.name, profile.arch, profile.libc.version)
    console.print(table)
