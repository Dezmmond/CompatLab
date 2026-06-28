from collections import deque
from pathlib import Path

from compatlab.src.bundle.models import (
    DependencyEdge,
    DependencyGraph,
    DependencyNode,
    DependencyResolutionKind,
)
from compatlab.src.elfscan.models import SymbolVersion
from compatlab.src.elfscan.scanner import scan_path
from compatlab.src.problem.models import Problem
from compatlab.src.profile.models import TargetProfile
from compatlab.src.report.models import ArtifactReport


DEFAULT_MAX_DEPTH = 10
DEFAULT_MAX_FILES = 500


class BundleResolutionError(ValueError):
    """Raised when bundle input paths are invalid."""


class BundleResolutionResult:
    def __init__(
        self,
        *,
        graph: DependencyGraph,
        reports: dict[str, ArtifactReport],
        warnings: list[Problem],
    ) -> None:
        self.graph = graph
        self.reports = reports
        self.warnings = warnings

    @property
    def bundled_library_names(self) -> set[str]:
        names: set[str] = set()
        for node in self.graph.nodes:
            if node.path is not None:
                names.add(Path(node.path).name)
            if node.soname is not None:
                names.add(node.soname)
        return names


def resolve_bundle_dependencies(
    entrypoint: Path,
    bundle_root: Path,
    *,
    target: TargetProfile | None = None,
    recursive: bool = False,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_files: int = DEFAULT_MAX_FILES,
) -> BundleResolutionResult:
    entrypoint = entrypoint.resolve()
    bundle_root = bundle_root.resolve()
    if not bundle_root.is_dir():
        raise BundleResolutionError(f"Bundle root is not a directory: {bundle_root}")
    try:
        entrypoint.relative_to(bundle_root)
    except ValueError as exc:
        raise BundleResolutionError(
            f"Entrypoint must be inside bundle root: {entrypoint} is not under {bundle_root}"
        ) from exc

    index, warnings = _build_bundle_index(bundle_root, max_files=max_files)
    target_libraries = (
        {library.soname for library in target.provided_libraries} if target is not None else set()
    )

    reports: dict[str, ArtifactReport] = {}
    path_to_id: dict[Path, str] = {}
    nodes: dict[str, DependencyNode] = {}
    edges: list[DependencyEdge] = []
    unresolved: list[DependencyEdge] = []
    queue: deque[tuple[Path, int]] = deque([(entrypoint, 0)])
    expanded: set[Path] = set()

    while queue:
        artifact_path, depth = queue.popleft()
        artifact_path = artifact_path.resolve()
        artifact_id = _artifact_id(bundle_root, artifact_path)
        if artifact_path not in path_to_id:
            path_to_id[artifact_path] = artifact_id
        if artifact_id not in reports:
            report = scan_path(artifact_path)
            reports[artifact_id] = report
            nodes[artifact_id] = _node_from_report(artifact_id, report)
            warnings.extend(_runtime_path_warnings(artifact_path, bundle_root, report))
        report = reports[artifact_id]
        if report.elf is None:
            continue
        if artifact_path in expanded:
            continue
        expanded.add(artifact_path)
        if not recursive and depth > 0:
            continue
        if recursive and depth >= max_depth and report.elf.needed:
            warnings.append(
                _resolver_warning(
                    artifact_path,
                    "bundle.max_depth_reached",
                    f"Dependency expansion stopped at depth {max_depth}.",
                )
            )
            continue

        for needed in report.elf.needed:
            edge = _resolve_needed(
                needed,
                requester_id=artifact_id,
                requester_path=artifact_path,
                bundle_root=bundle_root,
                report=report,
                index=index,
                target_libraries=target_libraries,
            )
            edges.append(edge)
            if edge.resolution_kind in {
                DependencyResolutionKind.MISSING,
                DependencyResolutionKind.AMBIGUOUS,
                DependencyResolutionKind.INCOMPATIBLE,
            }:
                unresolved.append(edge)
            if edge.resolution_kind == DependencyResolutionKind.BUNDLED and edge.resolved_path:
                resolved_path = Path(edge.resolved_path).resolve()
                if resolved_path not in path_to_id:
                    queue.append((resolved_path, depth + 1))

    graph = DependencyGraph(
        entrypoint_artifact_id=_artifact_id(bundle_root, entrypoint),
        nodes=list(nodes.values()),
        edges=edges,
        unresolved_dependencies=unresolved,
    )
    return BundleResolutionResult(graph=graph, reports=reports, warnings=warnings)


def _build_bundle_index(
    bundle_root: Path, *, max_files: int
) -> tuple[dict[str, list[Path]], list[Problem]]:
    index: dict[str, list[Path]] = {}
    warnings: list[Problem] = []
    scanned = 0
    for path in bundle_root.rglob("*"):
        if not path.is_file():
            continue
        scanned += 1
        if scanned > max_files:
            warnings.append(
                _resolver_warning(
                    bundle_root,
                    "bundle.max_files_reached",
                    f"Bundle indexing stopped after {max_files} files.",
                )
            )
            break
        index.setdefault(path.name, []).append(path.resolve())
    return index, warnings


def _resolve_needed(
    needed: str,
    *,
    requester_id: str,
    requester_path: Path,
    bundle_root: Path,
    report: ArtifactReport,
    index: dict[str, list[Path]],
    target_libraries: set[str],
) -> DependencyEdge:
    candidates = _candidate_paths(
        needed,
        requester_path=requester_path,
        bundle_root=bundle_root,
        report=report,
        index=index,
    )
    if len(candidates) == 1:
        resolved = candidates[0]
        return DependencyEdge(
            from_artifact_id=requester_id,
            needed_name=needed,
            resolution_kind=DependencyResolutionKind.BUNDLED,
            resolved_artifact_id=_artifact_id(bundle_root, resolved),
            resolved_path=str(resolved),
            candidates=[str(resolved)],
            message=f"{needed} resolved from bundle.",
        )
    if len(candidates) > 1:
        return DependencyEdge(
            from_artifact_id=requester_id,
            needed_name=needed,
            resolution_kind=DependencyResolutionKind.AMBIGUOUS,
            candidates=[str(path) for path in candidates],
            message=f"{needed} matched multiple bundled files.",
        )
    if needed in target_libraries:
        return DependencyEdge(
            from_artifact_id=requester_id,
            needed_name=needed,
            resolution_kind=DependencyResolutionKind.TARGET,
            message=f"{needed} is provided by the target profile.",
        )
    return DependencyEdge(
        from_artifact_id=requester_id,
        needed_name=needed,
        resolution_kind=DependencyResolutionKind.MISSING,
        message=f"{needed} was not found in the bundle or target profile.",
    )


def _candidate_paths(
    needed: str,
    *,
    requester_path: Path,
    bundle_root: Path,
    report: ArtifactReport,
    index: dict[str, list[Path]],
) -> list[Path]:
    ordered_dirs = [
        *_expanded_search_dirs(
            report.elf.runpath if report.elf is not None else [], requester_path
        ),
        *_expanded_search_dirs(report.elf.rpath if report.elf is not None else [], requester_path),
        requester_path.parent,
        bundle_root / "lib",
        bundle_root / "lib64",
        bundle_root / "usr" / "lib",
        bundle_root / "usr" / "lib64",
    ]
    candidates: list[Path] = []
    for directory in ordered_dirs:
        path = (directory / needed).resolve()
        if _is_inside(path, bundle_root) and path.is_file():
            candidates.append(path)
    candidates.extend(index.get(needed, []))
    return sorted(set(candidates), key=lambda path: str(path))


def _expanded_search_dirs(values: list[str], requester_path: Path) -> list[Path]:
    dirs: list[Path] = []
    origin = requester_path.parent
    for value in values:
        for part in value.split(":"):
            if not part:
                continue
            expanded = part.replace("$ORIGIN", str(origin)).replace("${ORIGIN}", str(origin))
            dirs.append(Path(expanded).resolve())
    return dirs


def _runtime_path_warnings(
    artifact_path: Path, bundle_root: Path, report: ArtifactReport
) -> list[Problem]:
    if report.elf is None:
        return []
    warnings: list[Problem] = []
    for field in ("rpath", "runpath"):
        for value in getattr(report.elf, field):
            for part in value.split(":"):
                if not part:
                    continue
                if "$" in part and "$ORIGIN" not in part and "${ORIGIN}" not in part:
                    warnings.append(
                        _resolver_warning(
                            artifact_path,
                            "bundle.rpath_unresolved_token",
                            f"{field.upper()} entry {part} contains an unsupported token.",
                        )
                    )
                if "$ORIGIN" in part or "${ORIGIN}" in part:
                    expanded = part.replace("$ORIGIN", str(artifact_path.parent)).replace(
                        "${ORIGIN}", str(artifact_path.parent)
                    )
                    if not _is_inside(Path(expanded).resolve(), bundle_root):
                        warnings.append(
                            _resolver_warning(
                                artifact_path,
                                "bundle.rpath_escapes_bundle",
                                f"{field.upper()} entry {part} escapes the bundle root.",
                            )
                        )
    return warnings


def _node_from_report(artifact_id: str, report: ArtifactReport) -> DependencyNode:
    elf = report.elf
    versions = elf.required_versions if elf is not None else []
    return DependencyNode(
        artifact_id=artifact_id,
        path=report.artifact.path,
        soname=Path(report.artifact.path).name,
        needed_libraries=elf.needed if elf is not None else [],
        rpath=elf.rpath if elf is not None else [],
        runpath=elf.runpath if elf is not None else [],
        required_glibc_versions=_versions(versions, "GLIBC"),
        required_glibcxx_versions=_versions(versions, "GLIBCXX"),
        required_cxxabi_versions=_versions(versions, "CXXABI"),
    )


def _versions(versions: list[SymbolVersion], namespace: str) -> list[str]:
    return [version.raw for version in versions if version.namespace == namespace]


def _artifact_id(bundle_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(bundle_root.resolve()))
    except ValueError:
        return str(path.resolve())


def _is_inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _resolver_warning(path: Path, problem_id: str, details: str) -> Problem:
    return Problem(
        id=problem_id,
        severity="LOW",
        title="Bundle dependency resolution warning",
        details=details,
        artifact_path=str(path),
    )
