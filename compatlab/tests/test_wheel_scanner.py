from pathlib import Path
import zipfile

from compatlab.artifact.detect import ArtifactKind, detect_artifact_kind
from compatlab.diagnostics import summarize_diagnostics
from compatlab.models import ArtifactInfo, ArtifactReport, ElfInfo, Problem
from compatlab.wheels.scanner import scan_wheel


def _write_wheel(
    path: Path,
    *,
    wheel_metadata: str | None = None,
    metadata: str | None = None,
    record: bool = True,
    files: dict[str, bytes] | None = None,
) -> None:
    with zipfile.ZipFile(path, "w") as wheel:
        if wheel_metadata is not None:
            wheel.writestr("demo-1.0.0.dist-info/WHEEL", wheel_metadata)
        if metadata is not None:
            wheel.writestr("demo-1.0.0.dist-info/METADATA", metadata)
        if record:
            wheel.writestr("demo-1.0.0.dist-info/RECORD", "")
        for name, data in (files or {}).items():
            wheel.writestr(name, data)


def _valid_wheel_metadata(*, purelib: bool = True) -> str:
    return "\n".join(
        [
            "Wheel-Version: 1.0",
            "Generator: compatlab-test",
            f"Root-Is-Purelib: {str(purelib).lower()}",
            "Tag: py3-none-any",
            "",
        ]
    )


def _valid_metadata() -> str:
    return "Metadata-Version: 2.1\nName: demo\nVersion: 1.0.0\n"


def test_artifact_kind_detection_for_wheel_elf_and_unknown(tmp_path: Path) -> None:
    wheel_path = tmp_path / "demo-1.0.0-py3-none-any.whl"
    elf_path = tmp_path / "libdemo.so"
    unknown_path = tmp_path / "plain.txt"
    _write_wheel(wheel_path, wheel_metadata=_valid_wheel_metadata(), metadata=_valid_metadata())
    elf_path.write_bytes(b"\x7fELFdemo")
    unknown_path.write_text("hello", encoding="utf-8")

    assert detect_artifact_kind(wheel_path) == ArtifactKind.WHEEL
    assert detect_artifact_kind(elf_path) == ArtifactKind.ELF
    assert detect_artifact_kind(unknown_path) == ArtifactKind.UNKNOWN


def test_scan_wheel_reads_metadata_and_reports_pure_python_wheel(tmp_path: Path) -> None:
    wheel_path = tmp_path / "demo-1.0.0-py3-none-any.whl"
    _write_wheel(
        wheel_path,
        wheel_metadata=_valid_wheel_metadata(),
        metadata=_valid_metadata(),
        files={"demo/__init__.py": b""},
    )

    report = scan_wheel(wheel_path)

    assert report.artifact.kind == "wheel"
    assert report.package is not None
    assert report.package.name == "demo"
    assert report.package.version == "1.0.0"
    assert report.package.tags == ["py3-none-any"]
    assert report.native_entries == []
    assert [issue.code for issue in report.diagnostics] == ["CL_WHEEL_NO_NATIVE_EXTENSIONS"]


def test_scan_wheel_reports_missing_metadata_files(tmp_path: Path) -> None:
    wheel_path = tmp_path / "demo-1.0.0-py3-none-any.whl"
    _write_wheel(
        wheel_path,
        wheel_metadata=None,
        metadata=None,
        record=False,
        files={"demo-1.0.0.dist-info/INSTALLER": b"compatlab"},
    )

    report = scan_wheel(wheel_path)

    assert {issue.code for issue in report.diagnostics} >= {
        "CL_WHEEL_WHEEL_METADATA_MISSING",
        "CL_WHEEL_METADATA_MISSING",
        "CL_WHEEL_RECORD_MISSING",
    }


def test_scan_wheel_scans_native_entries(tmp_path: Path, monkeypatch) -> None:
    wheel_path = tmp_path / "demo-1.0.0-cp311-cp311-linux_x86_64.whl"
    _write_wheel(
        wheel_path,
        wheel_metadata=_valid_wheel_metadata(purelib=False),
        metadata=_valid_metadata(),
        files={
            "demo/_native.cpython-311-x86_64-linux-gnu.so": b"\x7fELFfake",
            "demo/libextra.so.1": b"not magic but native by name",
        },
    )
    monkeypatch.setattr(
        "compatlab.wheels.scanner.scan_elf_path",
        lambda path: ArtifactReport(
            artifact=ArtifactInfo(path=str(path), kind="ELF"),
            elf=ElfInfo(elf_class="ELF64", machine="Advanced Micro Devices X86-64"),
        ),
    )

    report = scan_wheel(wheel_path)

    assert [entry.path for entry in report.native_entries] == [
        "demo/_native.cpython-311-x86_64-linux-gnu.so",
        "demo/libextra.so.1",
    ]
    assert all(entry.elf is not None for entry in report.native_entries)


def test_scan_wheel_reports_purelib_with_native_code(tmp_path: Path, monkeypatch) -> None:
    wheel_path = tmp_path / "demo-1.0.0-py3-none-any.whl"
    _write_wheel(
        wheel_path,
        wheel_metadata=_valid_wheel_metadata(purelib=True),
        metadata=_valid_metadata(),
        files={"demo/_native.abi3.so": b"\x7fELFfake"},
    )
    monkeypatch.setattr(
        "compatlab.wheels.scanner.scan_elf_path",
        lambda path: ArtifactReport(
            artifact=ArtifactInfo(path=str(path), kind="ELF"),
            elf=ElfInfo(elf_class="ELF64"),
        ),
    )

    report = scan_wheel(wheel_path)

    assert "CL_WHEEL_PURELIB_WITH_NATIVE_CODE" in {issue.code for issue in report.diagnostics}


def test_scan_wheel_rejects_unsafe_paths(tmp_path: Path) -> None:
    wheel_path = tmp_path / "demo-1.0.0-py3-none-any.whl"
    _write_wheel(
        wheel_path,
        wheel_metadata=_valid_wheel_metadata(),
        metadata=_valid_metadata(),
        files={"../evil.so": b"\x7fELF", "/abs.so": b"\x7fELF"},
    )

    report = scan_wheel(wheel_path)

    codes = [issue.code for issue in report.diagnostics]
    assert codes.count("CL_WHEEL_UNSAFE_PATH") == 2
    assert report.native_entries == []


def test_scan_wheel_reports_too_many_files(tmp_path: Path) -> None:
    wheel_path = tmp_path / "demo-1.0.0-py3-none-any.whl"
    _write_wheel(
        wheel_path,
        wheel_metadata=_valid_wheel_metadata(),
        metadata=_valid_metadata(),
        files={"demo/a.py": b"", "demo/b.py": b""},
    )

    report = scan_wheel(wheel_path, max_files=2)

    assert "CL_WHEEL_TOO_MANY_FILES" in {issue.code for issue in report.diagnostics}


def test_scan_wheel_reports_malformed_zip(tmp_path: Path) -> None:
    wheel_path = tmp_path / "broken.whl"
    wheel_path.write_bytes(b"not a zip")

    report = scan_wheel(wheel_path)

    assert [issue.code for issue in report.diagnostics] == ["CL_WHEEL_INVALID_ARCHIVE"]


def test_native_entry_scan_warnings_are_retargeted(tmp_path: Path, monkeypatch) -> None:
    wheel_path = tmp_path / "demo-1.0.0-cp311-cp311-linux_x86_64.whl"
    _write_wheel(
        wheel_path,
        wheel_metadata=_valid_wheel_metadata(purelib=False),
        metadata=_valid_metadata(),
        files={"demo/_native.so": b"\x7fELFfake"},
    )
    monkeypatch.setattr(
        "compatlab.wheels.scanner.scan_elf_path",
        lambda path: ArtifactReport(
            artifact=ArtifactInfo(path=str(path), kind="ELF"),
            elf=ElfInfo(elf_class="ELF64"),
            warnings=[
                Problem(
                    id="scan.warning",
                    severity="INFO",
                    title="readelf command failed",
                    details="failed",
                    artifact_path=str(path),
                )
            ],
        ),
    )

    report = scan_wheel(wheel_path)
    entry = report.native_entries[0]
    entry = entry.model_copy(update={"summary": summarize_diagnostics(entry.diagnostics)})

    assert entry.warnings[0].artifact_path == "demo/_native.so"


def test_native_entry_scan_failure_gets_wheel_error(tmp_path: Path, monkeypatch) -> None:
    wheel_path = tmp_path / "demo-1.0.0-cp311-cp311-linux_x86_64.whl"
    _write_wheel(
        wheel_path,
        wheel_metadata=_valid_wheel_metadata(purelib=False),
        metadata=_valid_metadata(),
        files={"demo/_native.so": b"\x7fELFfake"},
    )
    monkeypatch.setattr(
        "compatlab.wheels.scanner.scan_elf_path",
        lambda path: ArtifactReport(
            artifact=ArtifactInfo(path=str(path), kind="ELF"),
            elf=ElfInfo(),
        ),
    )

    report = scan_wheel(wheel_path)

    assert report.native_entries[0].diagnostics[0].code == "CL_WHEEL_NATIVE_ENTRY_SCAN_FAILED"
