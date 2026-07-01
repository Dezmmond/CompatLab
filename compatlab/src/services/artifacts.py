from dataclasses import dataclass
from pathlib import Path

import typer
from rich.console import Console

from compatlab.src.bundle.resolver import (
    BundleResolutionError,
    resolve_bundle_dependencies,
)
from compatlab.src.compare.engine import compare_report as comparator
from compatlab.src.diagnostics import (
    FailOn,
    should_fail_for_diagnostics
)
from compatlab.src.elfscan.scanner import scan_path
from compatlab.src.problem.models import Problem
from compatlab.src.profile.loader import (
    ProfileLoadError,
    ProfileNotFoundError,
    load_profile_file,
    load_target_profile,
)
from compatlab.src.report.pretty import render_report
from .reports import (
    DependencyProblemFactory,
    DiagnosticsAugmenter,
    HtmlContextFactory,
    ReportWriter,
)


@dataclass(frozen=True)
class ScanCommandOptions:
    path: Path
    bundle_root: Path | None
    recursive: bool
    max_depth: int
    max_files: int
    fail_on: FailOn
    json_output: Path | None
    html_output: Path | None


@dataclass(frozen=True)
class CompareCommandOptions:
    path: Path
    target: str | None
    target_file: Path | None
    bundle_root: Path | None
    recursive: bool
    max_depth: int
    max_files: int
    fail_on: FailOn
    json_output: Path | None
    html_output: Path | None


class ArtifactCommandService:
    def __init__(
        self,
        *,
        console: Console,
        diagnostics: DiagnosticsAugmenter | None = None,
        writer: ReportWriter | None = None,
        html_contexts: HtmlContextFactory | None = None,
        dependency_problems: DependencyProblemFactory | None = None,
    ) -> None:
        self.console = console

        self.diagnostics = diagnostics or DiagnosticsAugmenter()
        self.writer = writer or ReportWriter(console)
        self.html_contexts = html_contexts or HtmlContextFactory()
        self.dependency_problems = dependency_problems or DependencyProblemFactory()

    def scan(self, options: ScanCommandOptions) -> None:
        report = scan_path(options.path)
        if options.bundle_root is not None:
            try:
                resolution = resolve_bundle_dependencies(
                    options.path,
                    options.bundle_root,
                    recursive=options.recursive,
                    max_depth=options.max_depth,
                    max_files=options.max_files,
                )
            except BundleResolutionError as exc:
                self.console.print(f"[red]{exc}[/red]")
                raise typer.Exit(2) from exc
            report = report.model_copy(
                update={
                    "dependency_graph": resolution.graph,
                    "warnings": [*report.warnings, *resolution.warnings],
                }
            )
        report = self.diagnostics.add_diagnostics(report)
        self.writer.write(
            report,
            json_output=options.json_output,
            html_output=options.html_output,
            html_context=self.html_contexts.scan(
                bundle_root=options.bundle_root,
                recursive=options.recursive,
            ),
        )
        render_report(report, self.console)
        self._exit_for_diagnostics(report, options.fail_on)

    def compare(self, options: CompareCommandOptions) -> None:
        profile = self._load_profile(options)
        scan_report = scan_path(options.path)
        if self._scan_failed(scan_report):
            self._handle_scan_failure(scan_report, profile, options)
            return

        if options.bundle_root is not None:
            report = self._compare_bundle(scan_report, profile, options)
        else:
            report = comparator(scan_report, profile)

        report = self.diagnostics.add_diagnostics(report)
        self.writer.write(
            report,
            json_output=options.json_output,
            html_output=options.html_output,
            html_context=self.html_contexts.compare(
                target=options.target,
                target_file=options.target_file,
                bundle_root=options.bundle_root,
                recursive=options.recursive,
            ),
        )
        render_report(report, self.console)
        self._exit_for_diagnostics(report, options.fail_on)

    def _load_profile(self, options: CompareCommandOptions):
        if (options.target is None) == (options.target_file is None):
            self.console.print("[red]Provide exactly one of --target or --target-file.[/red]")
            raise typer.Exit(2)

        try:
            if options.target_file is not None:
                return load_profile_file(options.target_file)
            return load_target_profile(options.target or "")
        except (ProfileNotFoundError, ProfileLoadError) as exc:
            self.console.print(f"[red]{exc}[/red]")
            raise typer.Exit(2) from exc

    def _scan_failed(self, report) -> bool:
        return report.elf is None or report.elf.elf_class is None

    def _handle_scan_failure(self, scan_report, profile, options: CompareCommandOptions) -> None:
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
                        artifact_path=str(options.path),
                    ),
                ],
            }
        )
        report = self.diagnostics.add_diagnostics(report)
        self.writer.write(
            report,
            json_output=options.json_output,
            html_output=options.html_output,
            html_context=self.html_contexts.compare(
                target=options.target,
                target_file=options.target_file,
                bundle_root=options.bundle_root,
                recursive=options.recursive,
            ),
        )
        render_report(report, self.console)
        raise typer.Exit(2)

    def _compare_bundle(self, scan_report, profile, options: CompareCommandOptions):
        try:
            resolution = resolve_bundle_dependencies(
                options.path,
                options.bundle_root,
                target=profile,
                recursive=options.recursive,
                max_depth=options.max_depth,
                max_files=options.max_files,
            )
        except BundleResolutionError as exc:
            self.console.print(f"[red]{exc}[/red]")
            raise typer.Exit(2) from exc

        bundled_libraries = resolution.bundled_library_names
        report = comparator(
            scan_report,
            profile,
            assumed_provided_libraries=bundled_libraries,
        )
        problems = [*report.problems, *self.dependency_problems.from_graph(resolution.graph)]
        warnings = [*report.warnings, *resolution.warnings]
        for artifact_id, artifact_report in resolution.reports.items():
            if artifact_id == resolution.graph.entrypoint_artifact_id:
                continue
            compared = comparator(
                artifact_report,
                profile,
                assumed_provided_libraries=bundled_libraries,
            )
            problems.extend(compared.problems)
            warnings.extend(compared.warnings)
        return report.model_copy(
            update={
                "dependency_graph": resolution.graph,
                "problems": problems,
                "warnings": warnings,
            }
        )

    def _exit_for_diagnostics(self, report, fail_on: FailOn) -> None:
        if should_fail_for_diagnostics(report.diagnostics, fail_on):
            raise typer.Exit(1)
