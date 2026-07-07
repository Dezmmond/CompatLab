from email.parser import Parser
from pathlib import Path, PurePosixPath
import tempfile
import zipfile

from compatlab.artifact.detect import detect_artifact
from compatlab.elfscan.scanner import scan_path as scan_elf_path
from compatlab.models import (
    ArtifactReport,
    DiagnosticCategory,
    DiagnosticIssue,
    DiagnosticSeverity,
    Problem,
    PackageEntry,
    PackageMetadata
)

DEFAULT_MAX_WHEEL_FILES = 1000
DEFAULT_MAX_WHEEL_SIZE_BYTES = 200 * 1024 * 1024
DEFAULT_MAX_WHEEL_EXTRACTED_SIZE_BYTES = 500 * 1024 * 1024


def is_safe_archive_path(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts and "" not in path.parts


def scan_wheel(
    path: Path,
    *,
    max_files: int = DEFAULT_MAX_WHEEL_FILES,
    max_wheel_size_bytes: int = DEFAULT_MAX_WHEEL_SIZE_BYTES,
    max_extracted_size_bytes: int = DEFAULT_MAX_WHEEL_EXTRACTED_SIZE_BYTES,
) -> ArtifactReport:
    artifact = detect_artifact(path).model_copy(update={"kind": "wheel"})
    diagnostics: list[DiagnosticIssue] = []
    package = PackageMetadata()
    native_entries: list[PackageEntry] = []

    if artifact.size_bytes is not None and artifact.size_bytes > max_wheel_size_bytes:
        diagnostics.append(
            _issue(
                "CL_WHEEL_TOO_LARGE",
                DiagnosticSeverity.ERROR,
                "Wheel archive is too large",
                f"Wheel size is {artifact.size_bytes} bytes, limit is {max_wheel_size_bytes}.",
            )
        )
        return ArtifactReport(artifact=artifact, package=package, diagnostics=diagnostics)

    try:
        with zipfile.ZipFile(path) as wheel:
            infos = wheel.infolist()
            if len(infos) > max_files:
                diagnostics.append(
                    _issue(
                        "CL_WHEEL_TOO_MANY_FILES",
                        DiagnosticSeverity.ERROR,
                        "Wheel contains too many files",
                        f"Wheel contains {len(infos)} files, limit is {max_files}.",
                    )
                )

            unsafe = [info.filename for info in infos if not is_safe_archive_path(info.filename)]
            diagnostics.extend(
                _issue(
                    "CL_WHEEL_UNSAFE_PATH",
                    DiagnosticSeverity.ERROR,
                    "Wheel contains an unsafe archive path",
                    f"Archive entry {name} is absolute or contains parent traversal.",
                    affected_path=name,
                )
                for name in unsafe
            )
            if unsafe:
                return ArtifactReport(artifact=artifact, package=package, diagnostics=diagnostics)

            package, metadata_diagnostics = _read_package_metadata(wheel, infos)
            diagnostics.extend(metadata_diagnostics)
            native_infos = _native_infos(wheel, infos)
            extracted_size = sum(info.file_size for info in native_infos)
            if extracted_size > max_extracted_size_bytes:
                diagnostics.append(
                    _issue(
                        "CL_WHEEL_EXTRACTED_TOO_LARGE",
                        DiagnosticSeverity.ERROR,
                        "Native wheel entries are too large",
                        (
                            f"Native entries total {extracted_size} bytes, limit is "
                            f"{max_extracted_size_bytes}."
                        ),
                    )
                )
                return ArtifactReport(artifact=artifact, package=package, diagnostics=diagnostics)

            native_entries = _scan_native_entries(wheel, native_infos)
            diagnostics.extend(_package_consistency_diagnostics(package, native_entries))
            if not native_entries:
                diagnostics.append(
                    _issue(
                        "CL_WHEEL_NO_NATIVE_EXTENSIONS",
                        DiagnosticSeverity.INFO,
                        "Wheel does not contain native ELF entries",
                        "Wheel does not contain native ELF entries.",
                    )
                )
    except zipfile.BadZipFile:
        diagnostics.append(
            _issue(
                "CL_WHEEL_INVALID_ARCHIVE",
                DiagnosticSeverity.ERROR,
                "Wheel is not a valid zip archive",
                "The wheel file could not be opened as a zip archive.",
            )
        )

    return ArtifactReport(
        artifact=artifact,
        package=package,
        native_entries=native_entries,
        diagnostics=diagnostics,
    )


def _read_package_metadata(
    wheel: zipfile.ZipFile,
    infos: list[zipfile.ZipInfo],
) -> tuple[PackageMetadata, list[DiagnosticIssue]]:
    diagnostics: list[DiagnosticIssue] = []
    dist_info_dirs = sorted(
        {
            str(PurePosixPath(info.filename).parent)
            for info in infos
            if PurePosixPath(info.filename).parent.name.endswith(".dist-info")
        }
    )
    if not dist_info_dirs:
        diagnostics.append(
            _issue(
                "CL_WHEEL_NO_DIST_INFO",
                DiagnosticSeverity.WARNING,
                "Wheel has no dist-info directory",
                "No .dist-info directory was found in the wheel.",
            )
        )
    elif len(dist_info_dirs) > 1:
        diagnostics.append(
            _issue(
                "CL_WHEEL_MULTIPLE_DIST_INFO",
                DiagnosticSeverity.WARNING,
                "Wheel has multiple dist-info directories",
                "Multiple .dist-info directories were found in the wheel.",
            )
        )

    dist_info_dir = dist_info_dirs[0] if dist_info_dirs else None
    package = PackageMetadata(dist_info_dir=dist_info_dir)
    if dist_info_dir is None:
        return package, diagnostics

    wheel_metadata_path = f"{dist_info_dir}/WHEEL"
    metadata_path = f"{dist_info_dir}/METADATA"
    record_path = f"{dist_info_dir}/RECORD"
    names = {info.filename for info in infos}

    if wheel_metadata_path in names:
        message = Parser().parsestr(_read_text(wheel, wheel_metadata_path))
        root_is_purelib = _parse_bool(message.get("Root-Is-Purelib"))
        tags = message.get_all("Tag", [])
        package = package.model_copy(
            update={
                "root_is_purelib": root_is_purelib,
                "generator": message.get("Generator"),
                "build": message.get("Build"),
                "tags": tags,
            }
        )
    else:
        diagnostics.append(
            _issue(
                "CL_WHEEL_WHEEL_METADATA_MISSING",
                DiagnosticSeverity.WARNING,
                "Wheel metadata file is missing",
                f"{wheel_metadata_path} was not found.",
            )
        )

    if metadata_path in names:
        message = Parser().parsestr(_read_text(wheel, metadata_path))
        package = package.model_copy(
            update={"name": message.get("Name"), "version": message.get("Version")}
        )
    else:
        diagnostics.append(
            _issue(
                "CL_WHEEL_METADATA_MISSING",
                DiagnosticSeverity.WARNING,
                "Package metadata file is missing",
                f"{metadata_path} was not found.",
            )
        )

    if record_path not in names:
        diagnostics.append(
            _issue(
                "CL_WHEEL_RECORD_MISSING",
                DiagnosticSeverity.WARNING,
                "Wheel RECORD file is missing",
                f"{record_path} was not found.",
            )
        )
    return package, diagnostics


def _native_infos(wheel: zipfile.ZipFile, infos: list[zipfile.ZipInfo]) -> list[zipfile.ZipInfo]:
    native = []
    for info in infos:
        if info.is_dir():
            continue
        name = info.filename
        if name.endswith(".so") or ".so." in name:
            native.append(info)
            continue
        with wheel.open(info) as handle:
            if handle.read(4) == b"\x7fELF":
                native.append(info)
    return native


def _scan_native_entries(
    wheel: zipfile.ZipFile,
    infos: list[zipfile.ZipInfo],
) -> list[PackageEntry]:
    entries: list[PackageEntry] = []
    with tempfile.TemporaryDirectory(prefix="compatlab-wheel-") as tmp:
        tmp_path = Path(tmp)
        for index, info in enumerate(infos):
            extracted = tmp_path / f"{index}-{PurePosixPath(info.filename).name}"
            extracted.write_bytes(wheel.read(info))
            report = scan_elf_path(extracted)
            diagnostics = []
            if report.elf is None or report.elf.elf_class is None:
                diagnostics.append(
                    _issue(
                        "CL_WHEEL_NATIVE_ENTRY_SCAN_FAILED",
                        DiagnosticSeverity.ERROR,
                        "Native wheel entry could not be scanned as ELF",
                        "The native wheel entry did not produce parseable ELF metadata.",
                        affected_path=info.filename,
                    )
                )
            entries.append(
                PackageEntry(
                    path=info.filename,
                    size=info.file_size,
                    elf=report.elf,
                    diagnostics=diagnostics,
                    problems=[
                        _retarget_problem(problem, info.filename) for problem in report.problems
                    ],
                    warnings=[
                        _retarget_problem(warning, info.filename) for warning in report.warnings
                    ],
                )
            )
    return entries


def _package_consistency_diagnostics(
    package: PackageMetadata,
    native_entries: list[PackageEntry],
) -> list[DiagnosticIssue]:
    if package.root_is_purelib is not True or not native_entries:
        return []
    return [
        _issue(
            "CL_WHEEL_PURELIB_WITH_NATIVE_CODE",
            DiagnosticSeverity.WARNING,
            "Purelib wheel contains native code",
            "Wheel declares Root-Is-Purelib=true but contains native ELF entries.",
            affected_path=entry.path,
        )
        for entry in native_entries
    ]


def _read_text(wheel: zipfile.ZipFile, name: str) -> str:
    return wheel.read(name).decode("utf-8", errors="replace")


def _parse_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    return None


def _retarget_problem(problem: Problem, wheel_path: str) -> Problem:
    return problem.model_copy(update={"artifact_path": wheel_path})


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
