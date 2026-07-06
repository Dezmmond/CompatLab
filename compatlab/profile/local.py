"""Detect system facts from the current host."""

import platform

from pathlib import Path

from compatlab.compare import parse_version_tuple
from compatlab.elfscan.command import CommandResult, run_command, run_readelf
from compatlab.elfscan.parsers import parse_version_info
from compatlab.models import FactWarning, LibraryFact, SymbolVersionFacts, SystemFacts
from compatlab.profile.parsers import (
    detect_dynamic_linkers,
    parse_ldconfig_cache,
    parse_ldd_glibc_version,
    parse_os_release,
)


class CurrentSystemDetector:
    def __init__(self) -> None:
        self.warnings: list[FactWarning] = []
        self.detected_by: list[str] = ["platform.machine"]

    def detect(self) -> SystemFacts:
        os_release = self._detect_os_release()
        glibc_version = self._detect_glibc_version()
        libraries = self._detect_libraries()
        dynamic_linkers = detect_dynamic_linkers()
        if dynamic_linkers:
            self.detected_by.append("known-dynamic-linker-paths")

        symbol_versions = self._detect_symbol_versions(libraries)

        return SystemFacts(
            os_release=os_release,
            architecture=platform.machine() or None,
            glibc_version=glibc_version,
            dynamic_linkers=dynamic_linkers,
            library_paths=sorted(
                {library.path for library in libraries if library.path is not None}
            ),
            libraries=libraries,
            symbol_versions=symbol_versions,
            detected_by=self.detected_by,
            warnings=self.warnings,
        )

    def _detect_os_release(self):
        path = Path("/etc/os-release")
        if not path.exists():
            self.warnings.append(
                FactWarning(
                    code="os_release.missing",
                    message="/etc/os-release was not found.",
                    source=str(path),
                )
            )
            return parse_os_release("")
        self.detected_by.append("/etc/os-release")
        return parse_os_release(path.read_text(encoding="utf-8", errors="replace"))

    def _detect_glibc_version(self) -> str | None:
        result = run_command(["ldd", "--version"])
        if result.returncode != 0:
            self.warnings.append(
                _command_warning("ldd.version_failed", "ldd --version failed.", result)
            )
            return None
        self.detected_by.append("ldd --version")
        version = parse_ldd_glibc_version(result.stdout)
        if version is None:
            self.warnings.append(
                FactWarning(
                    code="glibc.version_not_detected",
                    message="Could not detect glibc version from ldd --version.",
                    source="ldd --version",
                )
            )
        return version

    def _detect_libraries(self) -> list[LibraryFact]:
        result = run_command(["ldconfig", "-p"])
        if result.returncode != 0:
            self.warnings.append(_command_warning("ldconfig.failed", "ldconfig -p failed.", result))
            return []
        self.detected_by.append("ldconfig -p")
        return parse_ldconfig_cache(result.stdout)

    def _detect_symbol_versions(self, libraries: list[LibraryFact]) -> SymbolVersionFacts:
        libc = _first_library_path(libraries, "libc.so.6")
        libstdcxx = _first_library_path(libraries, "libstdc++.so.6")

        glibc = self._read_symbol_versions(libc, {"GLIBC"})
        libstdcxx_versions = self._read_symbol_versions(libstdcxx, {"GLIBCXX", "CXXABI"})
        if glibc or libstdcxx_versions:
            self.detected_by.append("readelf --version-info")

        return SymbolVersionFacts(
            glibc=glibc.get("GLIBC", []),
            glibcxx=libstdcxx_versions.get("GLIBCXX", []),
            cxxabi=libstdcxx_versions.get("CXXABI", []),
        )

    def _read_symbol_versions(
        self,
        path: str | None,
        namespaces: set[str],
    ) -> dict[str, list[str]]:
        if path is None:
            self.warnings.append(
                FactWarning(
                    code="symbol.library_missing",
                    message=f"Could not find library for {', '.join(sorted(namespaces))}.",
                    source="ldconfig -p",
                )
            )
            return {}
        result = run_readelf(["--version-info"], Path(path))
        if result.returncode != 0:
            self.warnings.append(
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


def detect_current_system() -> SystemFacts:
    return CurrentSystemDetector().detect()


def _first_library_path(libraries: list[LibraryFact], soname: str) -> str | None:
    for library in libraries:
        if library.soname == soname and library.path is not None:
            return library.path
    return None


def _command_warning(code: str, message: str, result: CommandResult) -> FactWarning:
    details = result.stderr.strip() or f"exit code {result.returncode}"
    return FactWarning(code=code, message=f"{message} {details}", source=" ".join(result.args))
