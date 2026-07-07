from pathlib import Path

from compatlab.models import ArtifactInfo, ArtifactReport, ElfInfo
from compatlab.tests.wheel_fixtures import write_test_wheel
from compatlab.wheel.scanner import scan_wheel


def test_scan_wheel_reads_metadata_and_reports_no_native_entries(tmp_path: Path) -> None:
    wheel = tmp_path / "demo-1.0.0-py3-none-any.whl"
    write_test_wheel(wheel)

    report = scan_wheel(wheel)

    assert report.artifact.kind == "wheel"
    assert report.package is not None
    assert report.package.name == "demo"
    assert report.package.version == "1.0.0"
    assert report.package.tags == ["py3-none-any"]
    assert report.entries == []
    assert [issue.code for issue in report.diagnostics] == ["CL_WHEEL_NO_NATIVE_EXTENSIONS"]


def test_scan_wheel_scans_native_entries(tmp_path: Path, monkeypatch) -> None:
    wheel = tmp_path / "demo-1.0.0-cp311-cp311-linux_x86_64.whl"
    write_test_wheel(wheel, native=True, purelib=False)
    monkeypatch.setattr(
        "compatlab.wheel.scanner.scan_elf_path",
        lambda path: ArtifactReport(
            artifact=ArtifactInfo(path=str(path), kind="ELF"),
            elf=ElfInfo(elf_class="ELF64", machine="Advanced Micro Devices X86-64"),
        ),
    )

    report = scan_wheel(wheel)

    assert [entry.path for entry in report.entries] == [
        "demo/_native.cpython-311-x86_64-linux-gnu.so"
    ]
    assert report.package is not None
    assert report.package.native_entry_count == 1
