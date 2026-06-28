from compatlab.src.compare.engine import (
    compare_report,
    is_version_newer,
    max_required_version,
    normalize_architecture,
    parse_version_tuple,
)
from compatlab.src.elfscan.models import ElfInfo, SymbolVersion
from compatlab.src.profile.models import (
    LibcProfile,
    LibstdcxxProfile,
    ProvidedLibrary,
    TargetProfile,
)
from compatlab.src.report.models import ArtifactInfo, ArtifactReport


def _version(namespace: str, version: str) -> SymbolVersion:
    return SymbolVersion(namespace=namespace, version=version, raw=f"{namespace}_{version}")


def _profile() -> TargetProfile:
    return TargetProfile(
        id="test-target",
        name="Test Target",
        arch="x86_64",
        libc=LibcProfile(family="glibc", version="2.27"),
        libstdcxx=LibstdcxxProfile(max_glibcxx="3.4.25", max_cxxabi="1.3.11"),
        interpreters=["/lib64/ld-linux-x86-64.so.2"],
        provided_libraries=[
            ProvidedLibrary(soname="libc.so.6"),
            ProvidedLibrary(soname="libstdc++.so.6"),
        ],
    )


def _report(elf: ElfInfo) -> ArtifactReport:
    return ArtifactReport(
        artifact=ArtifactInfo(path="/tmp/demo", kind="ELF", size_bytes=123),
        elf=elf,
    )


def _problem_ids(report: ArtifactReport) -> list[str]:
    return [problem.id for problem in report.problems]


def _warning_ids(report: ArtifactReport) -> list[str]:
    return [warning.id for warning in report.warnings]


def test_parse_version_tuple_compares_numerically() -> None:
    assert parse_version_tuple("2.38") == (2, 38)
    assert parse_version_tuple("GLIBCXX_3.4.29") == (3, 4, 29)
    assert is_version_newer("2.38", "2.9")
    assert not is_version_newer("2.9", "2.38")


def test_max_required_version_selects_highest_numeric_version() -> None:
    versions = [_version("GLIBC", "2.9"), _version("GLIBC", "2.38")]

    assert max_required_version(versions, "GLIBC") == _version("GLIBC", "2.38")


def test_normalize_architecture_maps_readelf_names() -> None:
    assert normalize_architecture("Advanced Micro Devices X86-64") == "x86_64"
    assert normalize_architecture("Intel 80386") == "x86"
    assert normalize_architecture("ARM aarch64") == "aarch64"


def test_wrong_architecture_rule() -> None:
    report = _report(ElfInfo(machine="AArch64"))

    compared = compare_report(report, _profile())

    assert _problem_ids(compared) == ["wrong.architecture"]
    assert not compared.is_compatible


def test_glibc_too_new_rule() -> None:
    report = _report(
        ElfInfo(
            machine="Advanced Micro Devices X86-64",
            required_versions=[_version("GLIBC", "2.28")],
        )
    )

    compared = compare_report(report, _profile())

    assert "glibc.too_new" in _problem_ids(compared)


def test_glibcxx_too_new_rule() -> None:
    report = _report(
        ElfInfo(
            machine="Advanced Micro Devices X86-64",
            required_versions=[_version("GLIBCXX", "3.4.26")],
        )
    )

    compared = compare_report(report, _profile())

    assert "glibcxx.too_new" in _problem_ids(compared)


def test_cxxabi_too_new_rule() -> None:
    report = _report(
        ElfInfo(
            machine="Advanced Micro Devices X86-64",
            required_versions=[_version("CXXABI", "1.3.12")],
        )
    )

    compared = compare_report(report, _profile())

    assert "cxxabi.too_new" in _problem_ids(compared)


def test_missing_interpreter_rule() -> None:
    report = _report(ElfInfo(machine="Advanced Micro Devices X86-64", is_dynamic=True))

    compared = compare_report(report, _profile())

    assert "missing.interpreter" in _problem_ids(compared)


def test_interpreter_not_provided_rule() -> None:
    report = _report(
        ElfInfo(
            machine="Advanced Micro Devices X86-64",
            is_dynamic=True,
            interpreter="/custom/ld-linux-x86-64.so.2",
        )
    )

    compared = compare_report(report, _profile())

    assert "profile.interpreter_not_provided" in _problem_ids(compared)


def test_library_not_provided_rule() -> None:
    report = _report(
        ElfInfo(
            machine="Advanced Micro Devices X86-64",
            needed=["libc.so.6", "libmissing.so.1"],
        )
    )

    compared = compare_report(report, _profile())

    assert "profile.library_not_provided" in _problem_ids(compared)


def test_suspicious_rpath_and_runpath_rules_are_warnings() -> None:
    report = _report(
        ElfInfo(
            machine="Advanced Micro Devices X86-64",
            rpath=["/home/build/lib"],
            runpath=["/tmp/package/lib"],
        )
    )

    compared = compare_report(report, _profile())

    assert _problem_ids(compared) == []
    assert _warning_ids(compared) == [
        "bad.rpath.absolute",
        "bad.rpath.build_path",
        "bad.runpath.absolute",
        "bad.runpath.build_path",
    ]
    assert compared.is_compatible
