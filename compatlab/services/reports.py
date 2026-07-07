from pathlib import Path

from rich.console import Console

from compatlab.diagnostics import diagnostics_from_report_parts, summarize_diagnostics
from compatlab.models import DependencyGraph, DependencyResolutionKind, Problem
from compatlab.report.html import HtmlReportContext, write_html_report
from compatlab.report.json import write_json_report
from compatlab.services.exceptions import CommandExit


class DiagnosticsAugmenter:
    @staticmethod
    def add_diagnostics(report):
        diagnostics = [
            *report.diagnostics,
            *diagnostics_from_report_parts(
                problems=report.problems,
                warnings=report.warnings,
                graph=report.dependency_graph,
            ),
        ]
        entries = []
        for entry in report.entries:
            entry_diagnostics = [
                *entry.diagnostics,
                *diagnostics_from_report_parts(
                    problems=entry.problems,
                    warnings=entry.warnings,
                ),
            ]
            entries.append(
                entry.model_copy(
                    update={
                        "diagnostics": entry_diagnostics,
                        "summary": summarize_diagnostics(entry_diagnostics),
                    }
                )
            )
            diagnostics.extend(entry_diagnostics)
        return report.model_copy(
            update={
                "diagnostics": diagnostics,
                "entries": entries,
                "summary": summarize_diagnostics(diagnostics),
            }
        )


class ReportWriter:
    def __init__(self, console: Console) -> None:
        self.console = console

    def write(
        self,
        report,
        *,
        json_output: Path | None,
        html_output: Path | None,
        html_context: HtmlReportContext,
    ) -> None:
        try:
            if json_output is not None:
                write_json_report(report, json_output)
            if html_output is not None:
                write_html_report(report, html_output, context=html_context)
        except OSError as exc:
            self.console.print(f"[red]Could not write report: {exc}[/red]")
            raise CommandExit(2) from exc


class HtmlContextFactory:
    @staticmethod
    def scan(
        *,
        bundle_root: Path | None,
        recursive: bool,
    ) -> HtmlReportContext:
        return HtmlReportContext(
            report_type="scan",
            command_mode="scan",
            bundle_root=str(bundle_root) if bundle_root is not None else None,
            recursive=recursive,
        )

    @staticmethod
    def compare(
        *,
        target: str | None,
        target_file: Path | None,
        bundle_root: Path | None,
        recursive: bool,
    ) -> HtmlReportContext:
        target_selector = (
            target if target is not None else str(target_file) if target_file is not None else None
        )
        return HtmlReportContext(
            report_type="compare",
            command_mode="compare",
            target_selector=target_selector,
            bundle_root=str(bundle_root) if bundle_root is not None else None,
            recursive=recursive,
        )


class DependencyProblemFactory:
    @staticmethod
    def from_graph(graph: DependencyGraph) -> list[Problem]:
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
