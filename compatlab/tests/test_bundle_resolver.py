from pathlib import Path

from compatlab.src.bundle.models import DependencyResolutionKind
from compatlab.src.bundle.resolver import resolve_bundle_dependencies
from compatlab.src.elfscan.models import ElfInfo, SymbolVersion
from compatlab.src.profile.models import LibcProfile, ProvidedLibrary, TargetProfile
from compatlab.src.report.models import ArtifactInfo, ArtifactReport


def _report(path: Path, elf: ElfInfo) -> ArtifactReport:
    return ArtifactReport(artifact=ArtifactInfo(path=str(path), kind="ELF"), elf=elf)


def _profile() -> TargetProfile:
    return TargetProfile(
        id="test-target",
        name="Test Target",
        arch="x86_64",
        libc=LibcProfile(family="glibc", version="2.39"),
        provided_libraries=[ProvidedLibrary(soname="libc.so.6")],
    )


def test_resolves_origin_runpath_and_recursive_dependencies(tmp_path: Path, monkeypatch) -> None:
    bundle = tmp_path / "dist"
    app = bundle / "bin" / "app"
    libfoo = bundle / "lib" / "libfoo.so"
    app.parent.mkdir(parents=True)
    libfoo.parent.mkdir()
    app.write_bytes(b"app")
    libfoo.write_bytes(b"foo")

    def fake_scan(path: Path) -> ArtifactReport:
        if path == app:
            return _report(
                path,
                ElfInfo(
                    machine="Advanced Micro Devices X86-64",
                    needed=["libfoo.so"],
                    runpath=["$ORIGIN/../lib"],
                ),
            )
        return _report(
            path,
            ElfInfo(
                machine="Advanced Micro Devices X86-64",
                needed=["libc.so.6"],
                required_versions=[
                    SymbolVersion(namespace="GLIBC", version="2.28", raw="GLIBC_2.28")
                ],
            ),
        )

    monkeypatch.setattr("compatlab.src.bundle.resolver.scan_path", fake_scan)

    result = resolve_bundle_dependencies(app, bundle, target=_profile(), recursive=True)

    kinds = [edge.resolution_kind for edge in result.graph.edges]
    assert kinds == [DependencyResolutionKind.BUNDLED, DependencyResolutionKind.TARGET]
    assert {node.artifact_id for node in result.graph.nodes} == {"bin/app", "lib/libfoo.so"}
    assert result.graph.unresolved_dependencies == []


def test_non_recursive_scan_includes_direct_bundled_nodes(tmp_path: Path, monkeypatch) -> None:
    bundle = tmp_path / "dist"
    app = bundle / "app"
    libfoo = bundle / "lib" / "libfoo.so"
    libfoo.parent.mkdir(parents=True)
    app.write_bytes(b"app")
    libfoo.write_bytes(b"foo")

    def fake_scan(path: Path) -> ArtifactReport:
        if path == app:
            return _report(path, ElfInfo(needed=["libfoo.so"]))
        return _report(path, ElfInfo(needed=["libtransitive.so"]))

    monkeypatch.setattr("compatlab.src.bundle.resolver.scan_path", fake_scan)

    result = resolve_bundle_dependencies(app, bundle, target=_profile(), recursive=False)

    assert {node.artifact_id for node in result.graph.nodes} == {"app", "lib/libfoo.so"}
    assert [edge.needed_name for edge in result.graph.edges] == ["libfoo.so"]


def test_marks_ambiguous_and_missing_dependencies(tmp_path: Path, monkeypatch) -> None:
    bundle = tmp_path / "dist"
    app = bundle / "app"
    first = bundle / "lib" / "libdup.so"
    second = bundle / "alt" / "libdup.so"
    first.parent.mkdir(parents=True)
    second.parent.mkdir()
    app.write_bytes(b"app")
    first.write_bytes(b"dup1")
    second.write_bytes(b"dup2")

    monkeypatch.setattr(
        "compatlab.src.bundle.resolver.scan_path",
        lambda path: _report(path, ElfInfo(needed=["libdup.so", "libmissing.so"])),
    )

    result = resolve_bundle_dependencies(app, bundle, target=_profile())

    assert [edge.resolution_kind for edge in result.graph.edges] == [
        DependencyResolutionKind.AMBIGUOUS,
        DependencyResolutionKind.MISSING,
    ]
    assert len(result.graph.unresolved_dependencies) == 2


def test_warns_for_runtime_paths_that_escape_bundle_or_use_unknown_tokens(
    tmp_path: Path, monkeypatch
) -> None:
    bundle = tmp_path / "dist"
    app = bundle / "bin" / "app"
    app.parent.mkdir(parents=True)
    app.write_bytes(b"app")

    monkeypatch.setattr(
        "compatlab.src.bundle.resolver.scan_path",
        lambda path: _report(
            path,
            ElfInfo(runpath=["$ORIGIN/../../outside:$LIB"]),
        ),
    )

    result = resolve_bundle_dependencies(app, bundle, target=_profile())

    assert [warning.id for warning in result.warnings] == [
        "bundle.rpath_escapes_bundle",
        "bundle.rpath_unresolved_token",
    ]
