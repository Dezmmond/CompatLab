from datetime import UTC, datetime

from compatlab.diagnostics import summarize_diagnostics
from compatlab.models import (
    ArtifactInfo,
    ArtifactReport,
    DependencyEdge,
    DependencyGraph,
    DependencyResolutionKind,
    DiagnosticCategory,
    DiagnosticIssue,
    DiagnosticSeverity,
    ElfInfo,
    LibcProfile,
    LibstdcxxProfile,
    Problem,
    SymbolVersion,
    TargetProfile,
)
from compatlab.report import HtmlReportContext, render_html_report


def _context() -> HtmlReportContext:
    return HtmlReportContext(
        report_type="compare",
        command_mode="compare",
        target_selector="ubuntu-2204",
        bundle_root="/tmp/dist",
        recursive=True,
        generated_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
    )


def test_html_report_renders_empty_diagnostics() -> None:
    report = ArtifactReport(artifact=ArtifactInfo(path="/tmp/app", kind="ELF"))

    html = render_html_report(report, context=_context())

    assert "CompatLab ArtifactDoctor" in html
    assert "Static compatibility report" in html
    assert "No diagnostics." in html
    assert "2026-01-02T03:04:05+00:00" in html


def test_html_report_renders_diagnostic_severities_and_escapes_values() -> None:
    diagnostics = [
        DiagnosticIssue(
            code="CL_ELF_SCAN_FAILED",
            severity=DiagnosticSeverity.ERROR,
            category=DiagnosticCategory.ARTIFACT,
            title="<script>alert(1)</script>",
            message='message with "quotes" & ampersand',
            affected_path="/tmp/a&b/app",
            hint="check <file>",
        ),
        DiagnosticIssue(
            code="CL_RPATH_ABSOLUTE",
            severity=DiagnosticSeverity.WARNING,
            category=DiagnosticCategory.RPATH,
            title="Absolute RPATH",
            message="RPATH points to build host",
        ),
        DiagnosticIssue(
            code="CL_NOTE",
            severity=DiagnosticSeverity.INFO,
            category=DiagnosticCategory.TARGET,
            title="Informational",
            message="FYI",
        ),
    ]
    report = ArtifactReport(
        artifact=ArtifactInfo(path="/tmp/a&b/app", kind="ELF"),
        diagnostics=diagnostics,
        summary=summarize_diagnostics(diagnostics),
    )

    html = render_html_report(report, context=_context())

    assert "CL_ELF_SCAN_FAILED" in html
    assert "CL_RPATH_ABSOLUTE" in html
    assert "CL_NOTE" in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>alert(1)</script>" not in html
    assert "/tmp/a&amp;b/app" in html
    assert "&quot;quotes&quot; &amp; ampersand" in html
    assert "check &lt;file&gt;" in html


def test_html_report_renders_dependency_graph_states() -> None:
    graph = DependencyGraph(
        entrypoint_artifact_id="bin/app",
        edges=[
            DependencyEdge(
                from_artifact_id="bin/app",
                needed_name="libok.so",
                resolution_kind=DependencyResolutionKind.BUNDLED,
                resolved_artifact_id="lib/libok.so",
                resolved_path="/tmp/dist/lib/libok.so",
            ),
            DependencyEdge(
                from_artifact_id="bin/app",
                needed_name="libmissing.so",
                resolution_kind=DependencyResolutionKind.MISSING,
                message="not found",
            ),
            DependencyEdge(
                from_artifact_id="bin/app",
                needed_name="libambiguous.so",
                resolution_kind=DependencyResolutionKind.AMBIGUOUS,
                candidates=["/tmp/dist/a/libambiguous.so", "/tmp/dist/b/libambiguous.so"],
            ),
        ],
        unresolved_dependencies=[
            DependencyEdge(
                from_artifact_id="bin/app",
                needed_name="libmissing.so",
                resolution_kind=DependencyResolutionKind.MISSING,
            )
        ],
    )
    report = ArtifactReport(
        artifact=ArtifactInfo(path="/tmp/dist/bin/app", kind="ELF"),
        dependency_graph=graph,
    )

    html = render_html_report(report, context=_context())

    assert "Dependency Resolution" in html
    assert "libok.so" in html
    assert "bundled" in html
    assert "libmissing.so" in html
    assert "missing" in html
    assert "libambiguous.so" in html
    assert "ambiguous" in html


def test_html_report_renders_legacy_issues_and_technical_details() -> None:
    report = ArtifactReport(
        artifact=ArtifactInfo(path="/tmp/app", kind="ELF", size_bytes=42, sha256="abc"),
        elf=ElfInfo(
            elf_class="ELF64",
            machine="Advanced Micro Devices X86-64",
            interpreter="/lib64/ld-linux-x86-64.so.2",
            needed=["libc.so.6"],
            required_versions=[SymbolVersion(namespace="GLIBC", version="2.34", raw="GLIBC_2.34")],
        ),
        target=TargetProfile(
            id="local",
            name="Local",
            arch="x86_64",
            libc=LibcProfile(family="glibc", version="2.39"),
            libstdcxx=LibstdcxxProfile(max_glibcxx="3.4.33", max_cxxabi="1.3.15"),
            interpreters=["/lib64/ld-linux-x86-64.so.2"],
        ),
        problems=[
            Problem(
                id="profile.library_not_provided",
                severity="HIGH",
                title="Missing library",
                details="libfoo.so is absent",
                artifact_path="/tmp/app",
            )
        ],
        warnings=[
            Problem(
                id="bad.rpath.absolute",
                severity="LOW",
                title="Absolute RPATH",
                details="/tmp/build/lib",
            )
        ],
    )

    html = render_html_report(report, context=_context())

    assert "Compatibility Problems and Warnings" in html
    assert "profile.library_not_provided" in html
    assert "bad.rpath.absolute" in html
    assert "Raw Metadata / Technical Details" in html
    assert "GLIBC_2.34" in html
    assert "glibc 2.39" in html
