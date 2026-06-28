import re

from compatlab.src.elfscan.models import SymbolVersion


_DYNAMIC_VALUE_RE = re.compile(r"\[(?P<value>[^\]]+)\]")
_VERSION_RE = re.compile(
    r"\b(?P<namespace>GLIBCXX|GLIBC|CXXABI)_(?P<version>[0-9][A-Za-z0-9_.]*)\b"
)


def _field_value(line: str) -> tuple[str, str] | None:
    if ":" not in line:
        return None
    key, value = line.split(":", 1)
    return key.strip(), value.strip()


def _elf_type(value: str) -> str:
    return value.split(maxsplit=1)[0]


def _endianness(value: str) -> str | None:
    lowered = value.lower()
    if "little endian" in lowered:
        return "little"
    if "big endian" in lowered:
        return "big"
    return None


def parse_elf_header(output: str) -> dict[str, str | None]:
    fields: dict[str, str | None] = {}
    for line in output.splitlines():
        parsed = _field_value(line)
        if parsed is None:
            continue
        key, value = parsed
        if key == "Class":
            fields["elf_class"] = value
        elif key == "Data":
            fields["endianness"] = _endianness(value)
        elif key == "OS/ABI":
            fields["os_abi"] = value
        elif key == "Type":
            fields["elf_type"] = _elf_type(value)
        elif key == "Machine":
            fields["machine"] = value
        elif key == "Entry point address":
            fields["entry_point"] = value
    return fields


def parse_program_headers(output: str) -> dict[str, str]:
    for line in output.splitlines():
        marker = "[Requesting program interpreter:"
        if marker not in line:
            continue
        _, value = line.split(marker, 1)
        return {"interpreter": value.rstrip("]").strip()}
    return {}


def parse_dynamic_section(output: str) -> dict[str, list[str] | bool]:
    needed: list[str] = []
    rpath: list[str] = []
    runpath: list[str] = []

    for line in output.splitlines():
        value_match = _DYNAMIC_VALUE_RE.search(line)
        if value_match is None:
            continue
        value = value_match.group("value")
        if "(NEEDED)" in line:
            needed.append(value)
        elif "(RPATH)" in line:
            rpath.append(value)
        elif "(RUNPATH)" in line:
            runpath.append(value)

    return {
        "is_dynamic": bool(needed or rpath or runpath or "Dynamic section at offset" in output),
        "needed": needed,
        "rpath": rpath,
        "runpath": runpath,
    }


def _version_sort_key(version: SymbolVersion) -> tuple[str, tuple[int | str, ...], str]:
    parts: list[int | str] = []
    for part in version.version.split("."):
        parts.append(int(part) if part.isdigit() else part)
    return version.namespace, tuple(parts), version.raw


def parse_version_info(output: str) -> list[SymbolVersion]:
    versions: dict[str, SymbolVersion] = {}
    for match in _VERSION_RE.finditer(output):
        namespace = match.group("namespace")
        version = match.group("version")
        raw = f"{namespace}_{version}"
        versions[raw] = SymbolVersion(namespace=namespace, version=version, raw=raw)
    return sorted(versions.values(), key=_version_sort_key)
