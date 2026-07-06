from enum import Enum
from typing import Sequence

from compatlab.models import (
    DependencyEdge,
    DependencyGraph,
    DiagnosticSeverity,
    DiagnosticCategory,
    DiagnosticIssue,
    DiagnosticSummary,
    DependencyResolutionKind,
    Problem,
)


class FailOn(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    NEVER = "never"


PROBLEM_CODE_MAP = {
    "wrong.architecture": (
        "CL_ARCH_MISMATCH",
        DiagnosticSeverity.ERROR,
        DiagnosticCategory.ARTIFACT,
        "Use an artifact built for the target architecture.",
    ),
    "missing.interpreter": (
        "CL_INTERP_MISSING",
        DiagnosticSeverity.ERROR,
        DiagnosticCategory.LOADER,
        "Build a dynamic artifact with a target-compatible program interpreter.",
    ),
    "profile.interpreter_not_provided": (
        "CL_INTERP_MISSING",
        DiagnosticSeverity.ERROR,
        DiagnosticCategory.LOADER,
        "Use a target image that provides the required dynamic linker.",
    ),
    "profile.library_not_provided": (
        "CL_LIB_MISSING",
        DiagnosticSeverity.ERROR,
        DiagnosticCategory.TARGET,
        "Install the runtime library on the target image or include it in the bundle.",
    ),
    "glibc.too_new": (
        "CL_SYMBOL_GLIBC_TOO_NEW",
        DiagnosticSeverity.ERROR,
        DiagnosticCategory.SYMBOLS,
        "Rebuild on an older baseline distribution or choose a newer target profile.",
    ),
    "glibcxx.too_new": (
        "CL_SYMBOL_GLIBCXX_TOO_NEW",
        DiagnosticSeverity.ERROR,
        DiagnosticCategory.SYMBOLS,
        "Bundle a compatible libstdc++ or choose a newer target profile.",
    ),
    "cxxabi.too_new": (
        "CL_SYMBOL_CXXABI_TOO_NEW",
        DiagnosticSeverity.ERROR,
        DiagnosticCategory.SYMBOLS,
        "Bundle a compatible C++ runtime or choose a newer target profile.",
    ),
    "bad.rpath.absolute": (
        "CL_RPATH_ABSOLUTE",
        DiagnosticSeverity.WARNING,
        DiagnosticCategory.RPATH,
        "Prefer $ORIGIN-relative runtime paths for portable bundles.",
    ),
    "bad.runpath.absolute": (
        "CL_RPATH_ABSOLUTE",
        DiagnosticSeverity.WARNING,
        DiagnosticCategory.RPATH,
        "Prefer $ORIGIN-relative runtime paths for portable bundles.",
    ),
    "scan.failed": (
        "CL_ELF_SCAN_FAILED",
        DiagnosticSeverity.ERROR,
        DiagnosticCategory.ARTIFACT,
        "Check that the main artifact is a readable ELF file.",
    ),
}


WARNING_CODE_MAP = {
    "bad.rpath.absolute": (
        "CL_RPATH_ABSOLUTE",
        DiagnosticSeverity.WARNING,
        DiagnosticCategory.RPATH,
        "Prefer $ORIGIN-relative runtime paths for portable bundles.",
    ),
    "bad.runpath.absolute": (
        "CL_RPATH_ABSOLUTE",
        DiagnosticSeverity.WARNING,
        DiagnosticCategory.RPATH,
        "Prefer $ORIGIN-relative runtime paths for portable bundles.",
    ),
    "bundle.max_depth_reached": (
        "CL_BUNDLE_MAX_DEPTH_REACHED",
        DiagnosticSeverity.WARNING,
        DiagnosticCategory.LIMITS,
        "Increase --max-depth if deeper dependency traversal is intended.",
    ),
    "bundle.max_files_reached": (
        "CL_BUNDLE_MAX_FILES_REACHED",
        DiagnosticSeverity.WARNING,
        DiagnosticCategory.LIMITS,
        "Increase --max-files or point --bundle-root at a smaller directory.",
    ),
    "bundle.rpath_escapes_bundle": (
        "CL_RPATH_ESCAPES_BUNDLE",
        DiagnosticSeverity.WARNING,
        DiagnosticCategory.RPATH,
        "Keep $ORIGIN-based runtime paths inside the shipped bundle root.",
    ),
    "bundle.rpath_unresolved_token": (
        "CL_RPATH_UNRESOLVED_TOKEN",
        DiagnosticSeverity.WARNING,
        DiagnosticCategory.RPATH,
        "Use $ORIGIN-relative paths or verify this runtime token manually.",
    ),
    "scan.warning": (
        "CL_ELF_SCAN_FAILED",
        DiagnosticSeverity.WARNING,
        DiagnosticCategory.ARTIFACT,
        "Install readelf and check that the artifact is a readable ELF file.",
    ),
}


def summarize_diagnostics(issues: Sequence[DiagnosticIssue]) -> DiagnosticSummary:
    summary = DiagnosticSummary()
    for issue in issues:
        if issue.severity == DiagnosticSeverity.ERROR:
            summary.errors += 1
        elif issue.severity == DiagnosticSeverity.WARNING:
            summary.warnings += 1
        else:
            summary.infos += 1
        summary.issue_codes[issue.code] = summary.issue_codes.get(issue.code, 0) + 1
    if summary.errors:
        summary.status = "failed"
    elif summary.warnings:
        summary.status = "warning"
    return summary


def should_fail_for_diagnostics(issues: Sequence[DiagnosticIssue], fail_on: FailOn) -> bool:
    if fail_on == FailOn.NEVER:
        return False
    summary = summarize_diagnostics(issues)
    if fail_on == FailOn.WARNING:
        return bool(summary.errors or summary.warnings)
    return bool(summary.errors)


def diagnostics_from_report_parts(
    *,
    problems: Sequence[Problem],
    warnings: Sequence[Problem],
    graph: DependencyGraph | None = None,
) -> list[DiagnosticIssue]:
    issues: list[DiagnosticIssue] = []
    issues.extend(_issues_from_problems(problems, use_warning_map=False))
    issues.extend(_issues_from_problems(warnings, use_warning_map=True))
    if graph is not None:
        issues.extend(_issues_from_graph(graph))
    return issues


def _issues_from_problems(
    problems: Sequence[Problem], *, use_warning_map: bool
) -> list[DiagnosticIssue]:
    issues: list[DiagnosticIssue] = []
    code_map = WARNING_CODE_MAP if use_warning_map else PROBLEM_CODE_MAP
    for problem in problems:
        mapped = code_map.get(problem.id)
        if mapped is None and use_warning_map:
            mapped = _map_rpath_warning(problem)
        if mapped is None:
            continue
        code, severity, category, fallback_hint = mapped
        issues.append(
            DiagnosticIssue(
                code=code,
                severity=severity,
                category=category,
                title=problem.title,
                message=problem.details,
                affected_path=problem.artifact_path,
                dependency_name=problem.evidence.get("library") or problem.evidence.get("needed"),
                required=problem.evidence.get("required")
                or problem.evidence.get("library")
                or problem.evidence.get("interpreter"),
                provided=problem.evidence.get("provided"),
                hint=problem.suggestions[0] if problem.suggestions else fallback_hint,
            )
        )
    return issues


def _map_rpath_warning(problem: Problem):
    if problem.id in {"bad.rpath.build_path", "bad.runpath.build_path"}:
        return (
            "CL_RPATH_ABSOLUTE",
            DiagnosticSeverity.WARNING,
            DiagnosticCategory.RPATH,
            "Prefer $ORIGIN-relative runtime paths for portable bundles.",
        )
    return None


def _issues_from_graph(graph: DependencyGraph) -> list[DiagnosticIssue]:
    issues: list[DiagnosticIssue] = []
    for edge in graph.unresolved_dependencies:
        if edge.resolution_kind == DependencyResolutionKind.MISSING:
            issues.append(_missing_dependency_issue(graph, edge))
        elif edge.resolution_kind == DependencyResolutionKind.AMBIGUOUS:
            issues.append(_ambiguous_dependency_issue(graph, edge))
    return issues


def _missing_dependency_issue(graph: DependencyGraph, edge: DependencyEdge) -> DiagnosticIssue:
    return DiagnosticIssue(
        code="CL_LIB_MISSING",
        severity=DiagnosticSeverity.ERROR,
        category=DiagnosticCategory.BUNDLE,
        title="Missing shared library",
        message=(
            f"{edge.needed_name} is required by {edge.from_artifact_id} but was not "
            "found in the bundle or target profile."
        ),
        affected_path=edge.from_artifact_id,
        dependency_name=edge.needed_name,
        dependency_chain=_dependency_chain(graph, edge),
        required=edge.needed_name,
        hint=(
            "Install the runtime library on the target image or include a compatible "
            f"{edge.needed_name} in the bundle."
        ),
    )


def _ambiguous_dependency_issue(graph: DependencyGraph, edge: DependencyEdge) -> DiagnosticIssue:
    candidates = ", ".join(edge.candidates)
    return DiagnosticIssue(
        code="CL_BUNDLE_AMBIGUOUS_LIB",
        severity=DiagnosticSeverity.WARNING,
        category=DiagnosticCategory.BUNDLE,
        title="Ambiguous bundled shared library",
        message=f"{edge.needed_name} has multiple candidates inside the bundle: {candidates}.",
        affected_path=edge.from_artifact_id,
        dependency_name=edge.needed_name,
        dependency_chain=_dependency_chain(graph, edge),
        required=edge.needed_name,
        hint="Prefer a single runtime library location or adjust RUNPATH.",
    )


def _dependency_chain(graph: DependencyGraph, edge: DependencyEdge) -> list[str]:
    parent: dict[str, str] = {}
    queue = [graph.entrypoint_artifact_id]
    seen = {graph.entrypoint_artifact_id}
    while queue:
        current = queue.pop(0)
        if current == edge.from_artifact_id:
            break
        for candidate in graph.edges:
            if candidate.from_artifact_id != current or candidate.resolved_artifact_id is None:
                continue
            if candidate.resolved_artifact_id in seen:
                continue
            seen.add(candidate.resolved_artifact_id)
            parent[candidate.resolved_artifact_id] = current
            queue.append(candidate.resolved_artifact_id)

    if edge.from_artifact_id not in seen:
        return [edge.from_artifact_id, edge.needed_name]

    chain = [edge.from_artifact_id]
    while chain[-1] != graph.entrypoint_artifact_id:
        chain.append(parent[chain[-1]])
    chain.reverse()
    chain.append(edge.needed_name)
    return chain
