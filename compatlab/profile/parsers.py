"""Parse host profile command output and release metadata."""

import re

from pathlib import Path

from compatlab.models import LibraryFact, OsReleaseFacts


KNOWN_DYNAMIC_LINKERS = (
    "/lib64/ld-linux-x86-64.so.2",
    "/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2",
    "/lib/ld-linux.so.2",
    "/lib/ld-linux-aarch64.so.1",
    "/lib/aarch64-linux-gnu/ld-linux-aarch64.so.1",
)

_LDCONFIG_LINE_RE = re.compile(
    r"^\s*(?P<soname>\S+)\s+\((?P<arch>[^)]*)\)\s+=>\s+(?P<path>\S+)\s*$"
)
_LDD_VERSION_RE = re.compile(r"\b(?P<version>[0-9]+(?:\.[0-9]+)+)\b")


class LdconfigCacheParser:
    @staticmethod
    def parse(output: str) -> list[LibraryFact]:
        libraries: dict[str, LibraryFact] = {}
        for line in output.splitlines():
            match = _LDCONFIG_LINE_RE.match(line)
            if match is None:
                continue
            soname = match.group("soname")
            libraries.setdefault(
                soname,
                LibraryFact(
                    soname=soname,
                    path=match.group("path"),
                    arch=match.group("arch") or None,
                ),
            )
        return [libraries[soname] for soname in sorted(libraries)]


class LddVersionParser:
    @staticmethod
    def parse_glibc_version(output: str) -> str | None:
        first_line = next((line.strip() for line in output.splitlines() if line.strip()), "")
        if not first_line:
            return None
        match = _LDD_VERSION_RE.search(first_line)
        if match is None:
            return None
        return match.group("version")


class OsReleaseParser:
    def parse(self, content: str) -> OsReleaseFacts:
        fields: dict[str, str] = {}
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if not key:
                continue
            fields[key] = self._strip_value(value.strip())

        return OsReleaseFacts(
            id=fields.get("ID"),
            name=fields.get("NAME"),
            version_id=fields.get("VERSION_ID"),
            pretty_name=fields.get("PRETTY_NAME"),
        )

    @staticmethod
    def _strip_value(value: str) -> str:
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            return value[1:-1]
        return value


def parse_os_release(content: str) -> OsReleaseFacts:
    return OsReleaseParser().parse(content)


def parse_ldconfig_cache(output: str) -> list[LibraryFact]:
    return LdconfigCacheParser().parse(output)


def parse_ldd_glibc_version(output: str) -> str | None:
    return LddVersionParser().parse_glibc_version(output)


def detect_dynamic_linkers(candidates: tuple[str, ...] = KNOWN_DYNAMIC_LINKERS) -> list[str]:
    return [candidate for candidate in candidates if Path(candidate).exists()]
