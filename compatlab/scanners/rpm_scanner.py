from dataclasses import dataclass
import gzip
from pathlib import Path, PurePosixPath
import stat
import struct
import tempfile
import zlib

from compatlab.artifact.detect import detect_artifact
from compatlab.scanners.elf_scanner import scan_path as scan_elf_path
from compatlab.models import (
    ArtifactReport,
    DiagnosticCategory,
    DiagnosticIssue,
    DiagnosticSeverity,
    PackageEntry,
    PackageMetadata,
    Problem,
)

RPM_MAGIC = b"\xed\xab\xee\xdb"
HEADER_MAGIC = b"\x8e\xad\xe8\x01"

DEFAULT_MAX_RPM_FILES = 5000
DEFAULT_MAX_RPM_SIZE_BYTES = 500 * 1024 * 1024
DEFAULT_MAX_RPM_EXTRACTED_SIZE_BYTES = 1024 * 1024 * 1024

RPM_TAG_NAME = 1000
RPM_TAG_VERSION = 1001
RPM_TAG_RELEASE = 1002
RPM_TAG_EPOCH = 1003
RPM_TAG_SUMMARY = 1004
RPM_TAG_BUILD_TIME = 1006
RPM_TAG_GROUP = 1016
RPM_TAG_LICENSE = 1014
RPM_TAG_VENDOR = 1011
RPM_TAG_ARCH = 1022
RPM_TAG_SOURCE_RPM = 1044
RPM_TAG_PAYLOAD_FORMAT = 1124
RPM_TAG_PAYLOAD_COMPRESSOR = 1125

RPM_TYPE_INT32 = 4
RPM_TYPE_STRING = 6
RPM_TYPE_STRING_ARRAY = 8
RPM_TYPE_I18NSTRING = 9


class RpmReadError(Exception):
    def __init__(self, message: str, code: str = "CL_RPM_INVALID_ARCHIVE") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class PayloadEntry:
    path: str
    mode: int
    size: int
    data: bytes

    @property
    def is_regular(self) -> bool:
        return stat.S_ISREG(self.mode)


def scan_rpm(
    path: Path,
    *,
    max_files: int = DEFAULT_MAX_RPM_FILES,
    max_rpm_size_bytes: int = DEFAULT_MAX_RPM_SIZE_BYTES,
    max_extracted_size_bytes: int = DEFAULT_MAX_RPM_EXTRACTED_SIZE_BYTES,
) -> ArtifactReport:
    artifact = detect_artifact(path).model_copy(update={"kind": "rpm"})
    diagnostics: list[DiagnosticIssue] = []
    package = PackageMetadata(type="rpm")

    if artifact.size_bytes is not None and artifact.size_bytes > max_rpm_size_bytes:
        diagnostics.append(
            _issue(
                "CL_RPM_TOO_LARGE",
                DiagnosticSeverity.ERROR,
                "RPM package is too large",
                f"RPM size is {artifact.size_bytes} bytes, limit is {max_rpm_size_bytes}.",
            )
        )
        return ArtifactReport(artifact=artifact, package=package, diagnostics=diagnostics)

    try:
        metadata, payload = _read_rpm(path)
        package = metadata
        payload_entries = _read_payload(payload, package)
    except RpmReadError as exc:
        diagnostics.append(
            _issue(
                exc.code,
                DiagnosticSeverity.ERROR,
                "RPM package could not be read",
                str(exc),
            )
        )
        return ArtifactReport(artifact=artifact, package=package, diagnostics=diagnostics)
    if not package.name or not package.version:
        diagnostics.append(
            _issue(
                "CL_RPM_METADATA_MISSING",
                DiagnosticSeverity.WARNING,
                "RPM metadata is incomplete",
                "RPM name or version metadata is missing.",
            )
        )

    package = package.model_copy(update={"payload_file_count": len(payload_entries)})
    if len(payload_entries) > max_files:
        diagnostics.append(
            _issue(
                "CL_RPM_TOO_MANY_FILES",
                DiagnosticSeverity.ERROR,
                "RPM payload contains too many files",
                f"RPM payload contains {len(payload_entries)} files, limit is {max_files}.",
            )
        )

    unsafe = [entry.path for entry in payload_entries if not is_safe_payload_path(entry.path)]
    diagnostics.extend(
        _issue(
            "CL_RPM_UNSAFE_PATH",
            DiagnosticSeverity.ERROR,
            "RPM payload contains an unsafe path",
            f"Payload entry {name} is absolute, empty, or contains parent traversal.",
            affected_path=name,
        )
        for name in unsafe
    )
    if unsafe:
        return ArtifactReport(artifact=artifact, package=package, diagnostics=diagnostics)

    native_payload_entries = [entry for entry in payload_entries if _is_native_candidate(entry)]
    extracted_size = sum(entry.size for entry in native_payload_entries)
    if extracted_size > max_extracted_size_bytes:
        diagnostics.append(
            _issue(
                "CL_RPM_EXTRACTED_TOO_LARGE",
                DiagnosticSeverity.ERROR,
                "RPM native entries are too large",
                (
                    f"Native entries total {extracted_size} bytes, limit is "
                    f"{max_extracted_size_bytes}."
                ),
            )
        )
        return ArtifactReport(artifact=artifact, package=package, diagnostics=diagnostics)

    entries = _scan_native_entries(native_payload_entries)
    package = package.model_copy(update={"native_entry_count": len(entries)})
    if not entries:
        diagnostics.append(
            _issue(
                "CL_RPM_NO_ELF_ENTRIES",
                DiagnosticSeverity.INFO,
                "RPM payload does not contain native ELF entries",
                "RPM payload does not contain native ELF entries.",
            )
        )
    return ArtifactReport(
        artifact=artifact, package=package, entries=entries, diagnostics=diagnostics
    )


def is_safe_payload_path(path: str) -> bool:
    normalized = _normalize_payload_path(path)
    pure = PurePosixPath(normalized.lstrip("/"))
    return bool(normalized) and not normalized.startswith("//") and ".." not in pure.parts


def _read_rpm(path: Path) -> tuple[PackageMetadata, bytes]:
    data = path.read_bytes()
    if len(data) < 96 or data[:4] != RPM_MAGIC:
        raise RpmReadError("File does not start with an RPM lead.")
    offset = 96
    _, offset = _read_header(data, offset)
    tags, offset = _read_header(data, offset)
    metadata = PackageMetadata(
        type="rpm",
        name=_string_tag(tags, RPM_TAG_NAME),
        epoch=_int_tag(tags, RPM_TAG_EPOCH),
        version=_string_tag(tags, RPM_TAG_VERSION),
        release=_string_tag(tags, RPM_TAG_RELEASE),
        architecture=_string_tag(tags, RPM_TAG_ARCH),
        summary=_string_tag(tags, RPM_TAG_SUMMARY),
        license=_string_tag(tags, RPM_TAG_LICENSE),
        vendor=_string_tag(tags, RPM_TAG_VENDOR),
        group=_string_tag(tags, RPM_TAG_GROUP),
        build_time=_int_tag(tags, RPM_TAG_BUILD_TIME),
        source_rpm=_string_tag(tags, RPM_TAG_SOURCE_RPM),
    )
    payload = data[offset:]
    if not payload:
        raise RpmReadError("RPM payload is empty.")
    payload_format = _string_tag(tags, RPM_TAG_PAYLOAD_FORMAT) or "cpio"
    if payload_format != "cpio":
        raise RpmReadError(
            f"Unsupported RPM payload format: {payload_format}.",
            code="CL_RPM_PAYLOAD_UNSUPPORTED",
        )
    return metadata, _decompress_payload(payload, _string_tag(tags, RPM_TAG_PAYLOAD_COMPRESSOR))


def _read_header(data: bytes, offset: int) -> tuple[dict[int, object], int]:
    offset = _align(offset, 8)
    if len(data) < offset + 16 or data[offset : offset + 4] != HEADER_MAGIC:
        raise RpmReadError("RPM header magic was not found.")
    index_count, store_size = struct.unpack(">II", data[offset + 8 : offset + 16])
    index_offset = offset + 16
    store_offset = index_offset + index_count * 16
    store_end = store_offset + store_size
    if len(data) < store_end:
        raise RpmReadError("RPM header is truncated.")

    raw_entries = []
    for index in range(index_count):
        start = index_offset + index * 16
        tag, value_type, value_offset, count = struct.unpack(">IIII", data[start : start + 16])
        raw_entries.append((tag, value_type, value_offset, count))

    tags: dict[int, object] = {}
    for index, (tag, value_type, value_offset, count) in enumerate(raw_entries):
        next_offsets = [
            candidate_offset
            for _, _, candidate_offset, _ in raw_entries[index + 1 :]
            if candidate_offset > value_offset
        ]
        value_end = min(next_offsets) if next_offsets else store_size
        raw = data[store_offset + value_offset : store_offset + value_end]
        tags[tag] = _parse_header_value(raw, value_type, count)
    return tags, _align(store_end, 8)


def _parse_header_value(raw: bytes, value_type: int, count: int) -> object:
    if value_type == RPM_TYPE_STRING:
        return raw.split(b"\0", 1)[0].decode("utf-8", errors="replace")
    if value_type in {RPM_TYPE_STRING_ARRAY, RPM_TYPE_I18NSTRING}:
        values = [part.decode("utf-8", errors="replace") for part in raw.split(b"\0") if part]
        return values[:count]
    if value_type == RPM_TYPE_INT32:
        values = [
            struct.unpack(">I", raw[index : index + 4])[0]
            for index in range(0, min(len(raw), count * 4), 4)
        ]
        return values[0] if count == 1 and values else values
    return raw


def _decompress_payload(payload: bytes, compressor: str | None) -> bytes:
    compressor = (compressor or "").strip().lower()
    try:
        if compressor in {"", "none"}:
            return payload
        if compressor == "gzip":
            return gzip.decompress(payload)
        if compressor == "zlib":
            return zlib.decompress(payload)
    except (OSError, zlib.error) as exc:
        raise RpmReadError(
            f"RPM payload could not be decompressed: {exc}",
            code="CL_RPM_PAYLOAD_READ_FAILED",
        ) from exc
    raise RpmReadError(
        f"Unsupported RPM payload compressor: {compressor}.",
        code="CL_RPM_PAYLOAD_UNSUPPORTED",
    )


def _read_payload(payload: bytes, package: PackageMetadata) -> list[PayloadEntry]:
    try:
        return _read_newc_payload(payload)
    except RpmReadError:
        raise
    except Exception as exc:
        label = package.name or "RPM"
        raise RpmReadError(
            f"{label} payload could not be parsed as newc cpio.",
            code="CL_RPM_PAYLOAD_READ_FAILED",
        ) from exc


def _read_newc_payload(payload: bytes) -> list[PayloadEntry]:
    offset = 0
    entries: list[PayloadEntry] = []
    while offset + 110 <= len(payload):
        header = payload[offset : offset + 110]
        if header[:6] not in {b"070701", b"070702"}:
            raise RpmReadError(
                "RPM payload is not a supported newc cpio archive.",
                code="CL_RPM_PAYLOAD_UNSUPPORTED",
            )
        mode = int(header[14:22], 16)
        file_size = int(header[54:62], 16)
        name_size = int(header[94:102], 16)
        offset += 110
        name_bytes = payload[offset : offset + name_size]
        if len(name_bytes) != name_size or not name_bytes.endswith(b"\0"):
            raise RpmReadError("RPM payload contains a truncated cpio filename.")
        name = name_bytes[:-1].decode("utf-8", errors="replace")
        offset = _align(offset + name_size, 4)
        if name == "TRAILER!!!":
            break
        data = payload[offset : offset + file_size]
        if len(data) != file_size:
            raise RpmReadError("RPM payload contains a truncated cpio file body.")
        offset = _align(offset + file_size, 4)
        entries.append(
            PayloadEntry(path=_normalize_payload_path(name), mode=mode, size=file_size, data=data)
        )
    return entries


def _scan_native_entries(payload_entries: list[PayloadEntry]) -> list[PackageEntry]:
    entries: list[PackageEntry] = []
    with tempfile.TemporaryDirectory(prefix="compatlab-rpm-") as tmp:
        tmp_path = Path(tmp)
        for index, entry in enumerate(payload_entries):
            extracted = tmp_path / f"{index}-{PurePosixPath(entry.path).name}"
            extracted.write_bytes(entry.data)
            report = scan_elf_path(extracted)
            diagnostics = []
            if report.elf is None or report.elf.elf_class is None:
                diagnostics.append(
                    _issue(
                        "CL_RPM_ELF_ENTRY_SCAN_FAILED",
                        DiagnosticSeverity.ERROR,
                        "RPM ELF entry could not be scanned",
                        "The RPM payload entry did not produce parseable ELF metadata.",
                        affected_path=entry.path,
                    )
                )
            entries.append(
                PackageEntry(
                    path=entry.path,
                    size=entry.size,
                    elf=report.elf,
                    diagnostics=diagnostics,
                    problems=[
                        _retarget_problem(problem, entry.path) for problem in report.problems
                    ],
                    warnings=[
                        _retarget_problem(warning, entry.path) for warning in report.warnings
                    ],
                )
            )
    return entries


def _is_native_candidate(entry: PayloadEntry) -> bool:
    if not entry.is_regular:
        return False
    if entry.data[:4] != b"\x7fELF":
        return False
    name = entry.path
    return (
        name.endswith(".so")
        or ".so." in name
        or (".cpython-" in name and name.endswith(".so"))
        or name.endswith(".abi3.so")
        or _is_common_native_path(name)
    )


def _is_common_native_path(path: str) -> bool:
    prefixes = (
        "/usr/bin/",
        "/usr/sbin/",
        "/bin/",
        "/sbin/",
        "/usr/lib/",
        "/usr/lib64/",
        "/lib/",
        "/lib64/",
        "/opt/",
    )
    return path.startswith(prefixes)


def _normalize_payload_path(path: str) -> str:
    while path.startswith("./"):
        path = path[2:]
    return "/" + path.lstrip("/")


def _string_tag(tags: dict[int, object], tag: int) -> str | None:
    value = tags.get(tag)
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value:
        return str(value[0])
    return None


def _int_tag(tags: dict[int, object], tag: int) -> int | None:
    value = tags.get(tag)
    if isinstance(value, int):
        return value
    if isinstance(value, list) and value and isinstance(value[0], int):
        return value[0]
    return None


def _retarget_problem(problem: Problem, path: str) -> Problem:
    return problem.model_copy(update={"artifact_path": path})


def _issue(
    code: str,
    severity: DiagnosticSeverity,
    title: str,
    message: str,
    *,
    affected_path: str | None = None,
) -> DiagnosticIssue:
    return DiagnosticIssue(
        code=code,
        severity=severity,
        category=DiagnosticCategory.PACKAGE,
        title=title,
        message=message,
        affected_path=affected_path,
    )


def _align(value: int, boundary: int) -> int:
    return value + (-value % boundary)
