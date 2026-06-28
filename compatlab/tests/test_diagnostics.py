from pathlib import Path

from compatlab.src.bundle.models import DependencyEdge, DependencyGraph, DependencyResolutionKind
from compatlab.src.diagnostics import (
    DiagnosticCategory,
    DiagnosticIssue,
    DiagnosticSeverity,
    FailOn,
    diagnostics_from_report_parts,
    should_fail_for_diagnostics,
    summarize_diagnostics,
)
from compatlab.src.problem.models import Problem


def test_diagnostic_issue_serializes_stable_enum_values() -> None:
    issue = DiagnosticIssue(
        code="CL_LIB_MISSING",
        severity=DiagnosticSeverity.ERROR,
        category=DiagnosticCategory.BUNDLE,
        title="Missing shared library",
        message="libssl.so.3 is missing.",
    )

    dumped = issue.model_dump(mode="json")

    assert dumped["severity"] == "error"
    assert dumped["category"] == "bundle"


def test_summarize_diagnostics_counts_status_and_codes() -> None:
    issues = [
        DiagnosticIssue(
            code="CL_LIB_MISSING",
            severity=DiagnosticSeverity.ERROR,
            category=DiagnosticCategory.BUNDLE,
            title="Missing shared library",
            message="missing",
        ),
        DiagnosticIssue(
            code="CL_RPATH_ABSOLUTE",
            severity=DiagnosticSeverity.WARNING,
            category=DiagnosticCategory.RPATH,
            title="Absolute RPATH",
            message="warning",
        ),
    ]

    summary = summarize_diagnostics(issues)

    assert summary.status == "failed"
    assert summary.errors == 1
    assert summary.warnings == 1
    assert summary.issue_codes == {"CL_LIB_MISSING": 1, "CL_RPATH_ABSOLUTE": 1}


def test_quality_gate_fail_on_modes() -> None:
    warning = DiagnosticIssue(
        code="CL_RPATH_ABSOLUTE",
        severity=DiagnosticSeverity.WARNING,
        category=DiagnosticCategory.RPATH,
        title="Absolute RPATH",
        message="warning",
    )

    assert not should_fail_for_diagnostics([warning], FailOn.ERROR)
    assert should_fail_for_diagnostics([warning], FailOn.WARNING)
    assert not should_fail_for_diagnostics([warning], FailOn.NEVER)


def test_problem_mapping_to_stable_diagnostic_code() -> None:
    problem = Problem(
        id="glibcxx.too_new",
        severity="HIGH",
        title="Artifact requires newer libstdc++ symbols than target provides",
        details="Artifact requires GLIBCXX_3.4.30, but target provides GLIBCXX_3.4.29.",
        artifact_path=str(Path("dist/app")),
        evidence={"required": "GLIBCXX_3.4.30", "provided": "GLIBCXX_3.4.29"},
    )

    issues = diagnostics_from_report_parts(problems=[problem], warnings=[])

    assert len(issues) == 1
    assert issues[0].code == "CL_SYMBOL_GLIBCXX_TOO_NEW"
    assert issues[0].required == "GLIBCXX_3.4.30"
    assert issues[0].provided == "GLIBCXX_3.4.29"


def test_bundle_missing_dependency_diagnostic_has_chain() -> None:
    graph = DependencyGraph(
        entrypoint_artifact_id="bin/app",
        edges=[
            DependencyEdge(
                from_artifact_id="bin/app",
                needed_name="libfoo.so",
                resolution_kind=DependencyResolutionKind.BUNDLED,
                resolved_artifact_id="lib/libfoo.so",
            ),
            DependencyEdge(
                from_artifact_id="lib/libfoo.so",
                needed_name="libssl.so.3",
                resolution_kind=DependencyResolutionKind.MISSING,
            ),
        ],
        unresolved_dependencies=[
            DependencyEdge(
                from_artifact_id="lib/libfoo.so",
                needed_name="libssl.so.3",
                resolution_kind=DependencyResolutionKind.MISSING,
            )
        ],
    )

    issues = diagnostics_from_report_parts(problems=[], warnings=[], graph=graph)

    assert issues[0].code == "CL_LIB_MISSING"
    assert issues[0].dependency_chain == ["bin/app", "lib/libfoo.so", "libssl.so.3"]


def test_bundle_ambiguous_dependency_diagnostic_is_warning() -> None:
    graph = DependencyGraph(
        entrypoint_artifact_id="app",
        unresolved_dependencies=[
            DependencyEdge(
                from_artifact_id="app",
                needed_name="libz.so.1",
                resolution_kind=DependencyResolutionKind.AMBIGUOUS,
                candidates=["dist/lib/libz.so.1", "dist/vendor/libz.so.1"],
            )
        ],
    )

    issues = diagnostics_from_report_parts(problems=[], warnings=[], graph=graph)

    assert issues[0].code == "CL_BUNDLE_AMBIGUOUS_LIB"
    assert issues[0].severity == DiagnosticSeverity.WARNING
