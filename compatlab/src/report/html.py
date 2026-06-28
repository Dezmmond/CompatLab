from __future__ import annotations

from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Iterable, Sequence

from pydantic import BaseModel

from compatlab.src.bundle.models import DependencyEdge, DependencyGraph
from compatlab.src.diagnostics import DiagnosticIssue, DiagnosticSummary
from compatlab.src.elfscan.models import SymbolVersion
from compatlab.src.problem.models import Problem
from compatlab.src.report.models import ArtifactReport


class HtmlReportContext(BaseModel):
    report_type: str
    command_mode: str | None = None
    target_selector: str | None = None
    bundle_root: str | None = None
    recursive: bool = False
    generated_at: datetime | None = None


def write_html_report(
    report: ArtifactReport,
    output_path: Path,
    *,
    context: HtmlReportContext,
) -> None:
    output_path.write_text(render_html_report(report, context=context), encoding="utf-8")


def render_html_report(report: ArtifactReport, *, context: HtmlReportContext) -> str:
    generated_at = context.generated_at or datetime.now(UTC)
    body = "\n".join(
        [
            _render_header(report, context, generated_at),
            _render_summary(report.summary),
            _render_diagnostics(report.diagnostics),
            _render_dependency_graph(report.dependency_graph),
            _render_legacy_issues(report.problems, report.warnings),
            _render_technical_details(report),
        ]
    )
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>CompatLab ArtifactDoctor Report</title>",
            f"<style>{_CSS}</style>",
            "</head>",
            "<body>",
            '<main class="page">',
            body,
            "</main>",
            "</body>",
            "</html>",
            "",
        ]
    )


def html_escape(value: object) -> str:
    if value is None or value == "":
        return "-"
    return escape(str(value), quote=True)


def _render_header(
    report: ArtifactReport,
    context: HtmlReportContext,
    generated_at: datetime,
) -> str:
    rows = [
        ("Report type", context.report_type),
        ("Generated", generated_at.isoformat(timespec="seconds")),
        ("Artifact path", report.artifact.path),
        ("Artifact kind", report.artifact.kind),
        ("Command mode", context.command_mode),
        ("Target", _target_label(report, context)),
        ("Bundle root", context.bundle_root),
        ("Recursive", "yes" if context.recursive else "no"),
    ]
    return _section(
        "CompatLab ArtifactDoctor",
        '<p class="subtitle">Static compatibility report</p>' + _definition_list(rows),
        section_class="hero",
    )


def _render_summary(summary: DiagnosticSummary | None) -> str:
    summary = summary or DiagnosticSummary()
    total = summary.errors + summary.warnings + summary.infos
    cards = [
        ("Status", summary.status, f"status {summary.status}"),
        ("Errors", summary.errors, "metric"),
        ("Warnings", summary.warnings, "metric"),
        ("Info", summary.infos, "metric"),
        ("Total diagnostics", total, "metric"),
    ]
    issue_codes = (
        _table(
            ["Code", "Count"],
            [(code, count) for code, count in sorted(summary.issue_codes.items())],
            empty="No diagnostic issue codes.",
        )
        if summary.issue_codes
        else '<p class="muted">No diagnostic issue codes.</p>'
    )
    return _section(
        "Summary",
        '<div class="summary-grid">'
        + "".join(
            f'<div class="{html_escape(css_class)}">'
            f"<span>{html_escape(label)}</span><strong>{html_escape(value)}</strong></div>"
            for label, value, css_class in cards
        )
        + "</div>"
        + "<h3>Issue Codes</h3>"
        + issue_codes,
    )


def _render_diagnostics(diagnostics: Sequence[DiagnosticIssue]) -> str:
    rows = [
        (
            issue.severity.value,
            issue.code,
            issue.category.value,
            issue.title,
            issue.affected_path,
            issue.dependency_name,
            issue.message,
            issue.hint,
        )
        for issue in diagnostics
    ]
    return _section(
        "Diagnostics",
        _table(
            [
                "Severity",
                "Code",
                "Category",
                "Title",
                "Affected Path",
                "Dependency",
                "Message",
                "Hint",
            ],
            rows,
            empty="No diagnostics.",
        ),
    )


def _render_dependency_graph(graph: DependencyGraph | None) -> str:
    if graph is None:
        return _section("Dependency Resolution", '<p class="muted">No dependency graph.</p>')

    parent_by_child = _parent_map(graph.edges)
    rows = []
    for edge in graph.edges:
        relationship = parent_by_child.get(edge.resolved_artifact_id or "", edge.from_artifact_id)
        rows.append(
            (
                edge.needed_name,
                edge.from_artifact_id,
                edge.resolution_kind.value,
                edge.resolved_path or edge.resolved_artifact_id,
                len(edge.candidates),
                _dependency_chain_label(edge, relationship),
            )
        )
    content = _definition_list(
        [
            ("Entrypoint", graph.entrypoint_artifact_id),
            ("Nodes", len(graph.nodes)),
            ("Edges", len(graph.edges)),
            ("Unresolved", len(graph.unresolved_dependencies)),
        ]
    ) + _table(
        [
            "Dependency",
            "Requester",
            "State",
            "Resolved Path",
            "Candidates",
            "Parent / Chain",
        ],
        rows,
        empty="No dependency edges.",
    )
    return _section("Dependency Resolution", content)


def _render_legacy_issues(problems: Sequence[Problem], warnings: Sequence[Problem]) -> str:
    problem_rows = [
        (problem.severity, problem.id, problem.title, problem.artifact_path, problem.details)
        for problem in problems
    ]
    warning_rows = [
        (warning.severity, warning.id, warning.title, warning.artifact_path, warning.details)
        for warning in warnings
    ]
    content = (
        "<h3>Problems</h3>"
        + _table(
            ["Severity", "ID", "Title", "Artifact Path", "Details"],
            problem_rows,
            empty="No compatibility problems.",
        )
        + "<h3>Warnings</h3>"
        + _table(
            ["Severity", "ID", "Title", "Artifact Path", "Details"],
            warning_rows,
            empty="No compatibility warnings.",
        )
    )
    return _section("Compatibility Problems and Warnings", content)


def _render_technical_details(report: ArtifactReport) -> str:
    rows: list[tuple[str, object]] = [
        ("Schema version", report.schema_version),
        ("Tool", report.tool),
        ("Artifact size", report.artifact.size_bytes),
        ("Artifact SHA256", report.artifact.sha256),
    ]
    if report.elf is not None:
        rows.extend(
            [
                ("ELF class", report.elf.elf_class),
                ("Endianness", report.elf.endianness),
                ("OS ABI", report.elf.os_abi),
                ("Machine", report.elf.machine),
                ("ELF type", report.elf.elf_type),
                ("Entry point", report.elf.entry_point),
                ("Dynamic", report.elf.is_dynamic),
                ("Interpreter", report.elf.interpreter),
                ("Needed libraries", ", ".join(report.elf.needed)),
                ("RPATH", ", ".join(report.elf.rpath)),
                ("RUNPATH", ", ".join(report.elf.runpath)),
                ("Required symbol versions", _symbol_versions(report.elf.required_versions)),
            ]
        )
    if report.target is not None:
        rows.extend(
            [
                ("Target ID", report.target.id),
                ("Target name", report.target.name),
                ("Target arch", report.target.arch),
                ("Target libc", f"{report.target.libc.family} {report.target.libc.version}"),
                ("Target interpreters", ", ".join(report.target.interpreters)),
                (
                    "Target libraries",
                    ", ".join(library.soname for library in report.target.provided_libraries),
                ),
            ]
        )
        if report.target.libstdcxx is not None:
            rows.extend(
                [
                    ("Target max GLIBCXX", report.target.libstdcxx.max_glibcxx),
                    ("Target max CXXABI", report.target.libstdcxx.max_cxxabi),
                ]
            )
        if report.target.metadata is not None:
            rows.extend(
                [
                    ("Profile source", report.target.metadata.source),
                    ("Profile generated by", report.target.metadata.generated_by),
                    ("Profile generated at", report.target.metadata.generated_at),
                    ("Profile source image", report.target.metadata.source_image),
                    ("Profile platform", report.target.metadata.platform),
                    ("Runtime preset", report.target.metadata.runtime_preset),
                    (
                        "Runtime packages",
                        ", ".join(report.target.metadata.runtime_packages or []),
                    ),
                    ("Package manager", report.target.metadata.package_manager),
                ]
            )
    return _section("Raw Metadata / Technical Details", _definition_list(rows))


def _section(title: str, content: str, *, section_class: str = "") -> str:
    classes = f' class="section {section_class}"' if section_class else ' class="section"'
    return f"<section{classes}><h1>{html_escape(title)}</h1>{content}</section>"


def _definition_list(rows: Iterable[tuple[str, object]]) -> str:
    rendered = []
    for label, value in rows:
        rendered.append(f"<dt>{html_escape(label)}</dt><dd>{html_escape(value)}</dd>")
    return '<dl class="details">' + "".join(rendered) + "</dl>"


def _table(headers: Sequence[str], rows: Sequence[Sequence[object]], *, empty: str) -> str:
    if not rows:
        return f'<p class="muted">{html_escape(empty)}</p>'
    head = "".join(f"<th>{html_escape(header)}</th>" for header in headers)
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{html_escape(value)}</td>" for value in row) + "</tr>")
    return (
        '<div class="table-wrap"><table><thead><tr>'
        + head
        + "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table></div>"
    )


def _target_label(report: ArtifactReport, context: HtmlReportContext) -> str | None:
    if context.target_selector:
        return context.target_selector
    if report.target is None:
        return None
    return f"{report.target.name} ({report.target.id})"


def _parent_map(edges: Sequence[DependencyEdge]) -> dict[str, str]:
    parents: dict[str, str] = {}
    for edge in edges:
        if edge.resolved_artifact_id is not None:
            parents.setdefault(edge.resolved_artifact_id, edge.from_artifact_id)
    return parents


def _dependency_chain_label(edge: DependencyEdge, parent: str | None) -> str:
    if edge.resolved_artifact_id is not None and parent is not None:
        return f"{parent} -> {edge.resolved_artifact_id}"
    if edge.message:
        return edge.message
    return edge.from_artifact_id


def _symbol_versions(versions: Sequence[SymbolVersion]) -> str:
    if not versions:
        return ""
    grouped: dict[str, list[str]] = {}
    for version in versions:
        grouped.setdefault(version.namespace, []).append(version.raw)
    return "; ".join(
        f"{namespace}: {', '.join(values)}" for namespace, values in sorted(grouped.items())
    )


_CSS = """
:root {
  color-scheme: light;
  --bg: #f6f7f9;
  --panel: #ffffff;
  --text: #1f2933;
  --muted: #657383;
  --line: #d8dee6;
  --ok: #156f45;
  --warn: #8a5a00;
  --fail: #a12828;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.page {
  max-width: 1180px;
  margin: 0 auto;
  padding: 28px 20px 48px;
}
.section {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  margin: 0 0 18px;
  padding: 22px;
}
.hero h1 {
  font-size: 30px;
  margin-bottom: 2px;
}
h1 {
  font-size: 21px;
  line-height: 1.2;
  margin: 0 0 14px;
}
h3 {
  font-size: 15px;
  margin: 18px 0 8px;
}
.subtitle {
  color: var(--muted);
  margin: 0 0 18px;
}
.details {
  display: grid;
  grid-template-columns: minmax(150px, 240px) minmax(0, 1fr);
  gap: 8px 18px;
  margin: 0;
}
dt {
  color: var(--muted);
  font-weight: 600;
}
dd {
  margin: 0;
  overflow-wrap: anywhere;
}
.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 10px;
}
.summary-grid > div {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 12px;
}
.summary-grid span {
  color: var(--muted);
  display: block;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}
.summary-grid strong {
  display: block;
  font-size: 22px;
  margin-top: 2px;
}
.status.passed strong { color: var(--ok); }
.status.warning strong { color: var(--warn); }
.status.failed strong { color: var(--fail); }
.table-wrap {
  overflow-x: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
}
th, td {
  border-bottom: 1px solid var(--line);
  padding: 8px 10px;
  text-align: left;
  vertical-align: top;
}
th {
  color: var(--muted);
  font-size: 12px;
  text-transform: uppercase;
}
td {
  overflow-wrap: anywhere;
}
.muted {
  color: var(--muted);
  margin: 0;
}
@media (max-width: 720px) {
  .page { padding: 14px; }
  .section { padding: 16px; }
  .details { grid-template-columns: 1fr; gap: 2px; }
}
"""
