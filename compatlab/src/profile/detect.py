from pathlib import Path
import platform

from compatlab.src.compare.engine import parse_version_tuple
from compatlab.src.elfscan.command import CommandResult, run_command, run_readelf
from compatlab.src.elfscan.parsers import parse_version_info
from compatlab.src.profile.ldconfig import parse_ldconfig_cache
from compatlab.src.profile.ldd import parse_ldd_glibc_version
from compatlab.src.profile.linkers import detect_dynamic_linkers
from compatlab.src.profile.models import FactWarning, LibraryFact, SymbolVersionFacts, SystemFacts
from compatlab.src.profile.os_release import parse_os_release


def detect_current_system() -> SystemFacts:
    warnings: list[FactWarning] = []
    detected_by: list[str] = ["platform.machine"]

    os_release = _detect_os_release(warnings, detected_by)
    glibc_version = _detect_glibc_version(warnings, detected_by)
    libraries = _detect_libraries(warnings, detected_by)
    dynamic_linkers = detect_dynamic_linkers()
    if dynamic_linkers:
        detected_by.append("known-dynamic-linker-paths")

    symbol_versions = _detect_symbol_versions(libraries, warnings, detected_by)

    return SystemFacts(
        os_release=os_release,
        architecture=platform.machine() or None,
        glibc_version=glibc_version,
        dynamic_linkers=dynamic_linkers,
        library_paths=sorted({library.path for library in libraries if library.path is not None}),
        libraries=libraries,
        symbol_versions=symbol_versions,
        detected_by=detected_by,
        warnings=warnings,
    )


def _detect_os_release(warnings: list[FactWarning], detected_by: list[str]):
    path = Path("/etc/os-release")
    if not path.exists():
        warnings.append(
            FactWarning(
                code="os_release.missing",
                message="/etc/os-release was not found.",
                source=str(path),
            )
        )
        return parse_os_release("")
    detected_by.append("/etc/os-release")
    return parse_os_release(path.read_text(encoding="utf-8", errors="replace"))


def _detect_glibc_version(warnings: list[FactWarning], detected_by: list[str]) -> str | None:
    result = run_command(["ldd", "--version"])
    if result.returncode != 0:
        warnings.append(_command_warning("ldd.version_failed", "ldd --version failed.", result))
        return None
    detected_by.append("ldd --version")
    version = parse_ldd_glibc_version(result.stdout)
    if version is None:
        warnings.append(
            FactWarning(
                code="glibc.version_not_detected",
                message="Could not detect glibc version from ldd --version.",
                source="ldd --version",
            )
        )
    return version


def _detect_libraries(warnings: list[FactWarning], detected_by: list[str]) -> list[LibraryFact]:
    result = run_command(["ldconfig", "-p"])
    if result.returncode != 0:
        warnings.append(_command_warning("ldconfig.failed", "ldconfig -p failed.", result))
        return []
    detected_by.append("ldconfig -p")
    return parse_ldconfig_cache(result.stdout)


def _detect_symbol_versions(
    libraries: list[LibraryFact],
    warnings: list[FactWarning],
    detected_by: list[str],
) -> SymbolVersionFacts:
    libc = _first_library_path(libraries, "libc.so.6")
    libstdcxx = _first_library_path(libraries, "libstdc++.so.6")

    glibc = _read_symbol_versions(libc, {"GLIBC"}, warnings)
    libstdcxx_versions = _read_symbol_versions(libstdcxx, {"GLIBCXX", "CXXABI"}, warnings)
    if glibc or libstdcxx_versions:
        detected_by.append("readelf --version-info")

    return SymbolVersionFacts(
        glibc=glibc.get("GLIBC", []),
        glibcxx=libstdcxx_versions.get("GLIBCXX", []),
        cxxabi=libstdcxx_versions.get("CXXABI", []),
    )


def _read_symbol_versions(
    path: str | None,
    namespaces: set[str],
    warnings: list[FactWarning],
) -> dict[str, list[str]]:
    if path is None:
        warnings.append(
            FactWarning(
                code="symbol.library_missing",
                message=f"Could not find library for {', '.join(sorted(namespaces))}.",
                source="ldconfig -p",
            )
        )
        return {}
    result = run_readelf(["--version-info"], Path(path))
    if result.returncode != 0:
        warnings.append(
            _command_warning(
                "symbol.readelf_failed",
                f"readelf --version-info failed for {path}.",
                result,
            )
        )
        return {}
    parsed = parse_version_info(result.stdout)
    grouped: dict[str, set[str]] = {namespace: set() for namespace in namespaces}
    for version in parsed:
        if version.namespace in grouped:
            grouped[version.namespace].add(version.version)
    return {
        namespace: sorted(values, key=parse_version_tuple)
        for namespace, values in grouped.items()
        if values
    }


def _first_library_path(libraries: list[LibraryFact], soname: str) -> str | None:
    for library in libraries:
        if library.soname == soname and library.path is not None:
            return library.path
    return None


def _command_warning(code: str, message: str, result: CommandResult) -> FactWarning:
    details = result.stderr.strip() or f"exit code {result.returncode}"
    return FactWarning(code=code, message=f"{message} {details}", source=" ".join(result.args))
