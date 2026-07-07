from pathlib import Path

from compatlab.artifact.detect import ArtifactKind, detect_artifact_kind
from compatlab.models import ArtifactInfo, ArtifactReport, ElfInfo, Problem
from compatlab.scanners.rpm_scanner import scan_rpm
from compatlab.tests.rpm_fixtures import write_test_rpm


def test_detects_rpm_artifact_kind(tmp_path: Path) -> None:
    rpm = tmp_path / "demo-1.0.0-1.x86_64.rpm"
    write_test_rpm(rpm)

    assert detect_artifact_kind(rpm) == ArtifactKind.RPM


def test_scan_rpm_reads_metadata_and_reports_no_native_entries(tmp_path: Path) -> None:
    rpm = tmp_path / "demo-1.0.0-1.x86_64.rpm"
    write_test_rpm(
        rpm,
        name="demo",
        version="1.0.0",
        release="1",
        arch="x86_64",
        files={"usr/share/doc/demo.txt": b"hello"},
    )

    report = scan_rpm(rpm)

    assert report.artifact.kind == "rpm"
    assert report.package is not None
    assert report.package.name == "demo"
    assert report.package.version == "1.0.0"
    assert report.package.release == "1"
    assert report.package.architecture == "x86_64"
    assert report.package.payload_file_count == 1
    assert report.package.native_entry_count == 0
    assert report.entries == []
    assert [issue.code for issue in report.diagnostics] == ["CL_RPM_NO_ELF_ENTRIES"]


def test_scan_rpm_scans_native_elf_entries(tmp_path: Path, monkeypatch) -> None:
    rpm = tmp_path / "demo-1.0.0-1.x86_64.rpm"
    write_test_rpm(
        rpm,
        files={
            "usr/bin/demo": b"\x7fELFfake",
            "usr/lib64/libdemo.so.1": b"\x7fELFfake",
            "usr/share/not-elf.so": b"not elf",
        },
    )
    monkeypatch.setattr(
        "compatlab.scanners.rpm_scanner.scan_elf_path",
        lambda path: ArtifactReport(
            artifact=ArtifactInfo(path=str(path), kind="ELF"),
            elf=ElfInfo(elf_class="ELF64", machine="Advanced Micro Devices X86-64"),
        ),
    )

    report = scan_rpm(rpm)

    assert [entry.path for entry in report.entries] == [
        "/usr/bin/demo",
        "/usr/lib64/libdemo.so.1",
    ]
    assert report.package is not None
    assert report.package.native_entry_count == 2
    assert all(entry.elf is not None for entry in report.entries)


def test_scan_rpm_rejects_invalid_archive(tmp_path: Path) -> None:
    rpm = tmp_path / "broken.rpm"
    rpm.write_bytes(b"not rpm")

    report = scan_rpm(rpm)

    assert [issue.code for issue in report.diagnostics] == ["CL_RPM_INVALID_ARCHIVE"]


def test_scan_rpm_reports_unsupported_payload_format(tmp_path: Path) -> None:
    rpm = tmp_path / "demo-1.0.0-1.x86_64.rpm"
    write_test_rpm(rpm, payload_format="tar")

    report = scan_rpm(rpm)

    assert [issue.code for issue in report.diagnostics] == ["CL_RPM_PAYLOAD_UNSUPPORTED"]


def test_scan_rpm_rejects_unsafe_payload_path(tmp_path: Path) -> None:
    rpm = tmp_path / "demo-1.0.0-1.x86_64.rpm"
    write_test_rpm(rpm, files={"../evil": b"\x7fELFfake"})

    report = scan_rpm(rpm)

    assert [issue.code for issue in report.diagnostics] == ["CL_RPM_UNSAFE_PATH"]
    assert report.entries == []


def test_scan_rpm_reports_payload_file_limit(tmp_path: Path) -> None:
    rpm = tmp_path / "demo-1.0.0-1.x86_64.rpm"
    write_test_rpm(rpm, files={"usr/bin/a": b"\x7fELFfake", "usr/bin/b": b"\x7fELFfake"})

    report = scan_rpm(rpm, max_files=1)

    assert "CL_RPM_TOO_MANY_FILES" in {issue.code for issue in report.diagnostics}


def test_scan_rpm_reports_extracted_size_limit(tmp_path: Path) -> None:
    rpm = tmp_path / "demo-1.0.0-1.x86_64.rpm"
    write_test_rpm(rpm, files={"usr/bin/demo": b"\x7fELFfake"})

    report = scan_rpm(rpm, max_extracted_size_bytes=1)

    assert [issue.code for issue in report.diagnostics] == ["CL_RPM_EXTRACTED_TOO_LARGE"]


def test_scan_rpm_reports_entry_scan_failure(tmp_path: Path, monkeypatch) -> None:
    rpm = tmp_path / "demo-1.0.0-1.x86_64.rpm"
    write_test_rpm(rpm, files={"usr/bin/demo": b"\x7fELFfake"})
    monkeypatch.setattr(
        "compatlab.scanners.rpm_scanner.scan_elf_path",
        lambda path: ArtifactReport(
            artifact=ArtifactInfo(path=str(path), kind="ELF"),
            elf=ElfInfo(),
            warnings=[
                Problem(
                    id="scan.warning",
                    severity="INFO",
                    title="readelf failed",
                    details="failed",
                    artifact_path=str(path),
                )
            ],
        ),
    )

    report = scan_rpm(rpm)

    assert report.entries[0].diagnostics[0].code == "CL_RPM_ELF_ENTRY_SCAN_FAILED"
    assert report.entries[0].warnings[0].artifact_path == "/usr/bin/demo"
