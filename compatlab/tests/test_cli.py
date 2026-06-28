from pathlib import Path
import shutil

import pytest
from typer.testing import CliRunner

from compatlab.src.cli import app


runner = CliRunner()


def test_scan_command_outputs_scan_status(tmp_path: Path) -> None:
    artifact = tmp_path / "demo-app"
    artifact.write_bytes(b"not really elf yet")

    result = runner.invoke(app, ["scan", str(artifact)])

    assert result.exit_code == 0
    assert "Artifact:" in result.output
    assert "Scan:" in result.output
    assert "Problems:" in result.output
    assert "Warnings:" in result.output
    assert "Compatibility:" not in result.output


def test_scan_command_writes_json_report(tmp_path: Path) -> None:
    artifact = tmp_path / "demo-app"
    artifact.write_bytes(b"not really elf yet")
    report = tmp_path / "report.json"

    result = runner.invoke(app, ["scan", str(artifact), "--json", str(report)])

    assert result.exit_code == 0
    assert report.exists()
    assert '"tool": "compatlab"' in report.read_text(encoding="utf-8")


def test_scan_command_smoke_scans_bin_bash() -> None:
    bash = Path("/bin/bash")
    if not bash.exists() or shutil.which("readelf") is None:
        pytest.skip("/bin/bash or readelf is not available")

    result = runner.invoke(app, ["scan", str(bash)])

    assert result.exit_code == 0
    assert "Artifact:" in result.output
    assert "ELF" in result.output
    assert "Compatibility:" not in result.output


def test_compare_command_returns_scan_error_for_non_elf(tmp_path: Path) -> None:
    artifact = tmp_path / "demo-app"
    artifact.write_bytes(b"not really elf yet")

    result = runner.invoke(app, ["compare", str(artifact), "--target", "ubuntu-1804"])

    assert result.exit_code == 2
    assert "Target:" in result.output
    assert "Ubuntu 18.04" in result.output
    assert "scan.failed" in result.output


def test_profiles_list_outputs_builtin_profiles() -> None:
    result = runner.invoke(app, ["profiles", "list"])

    assert result.exit_code == 0
    assert "ubuntu-1804" in result.output
    assert "rocky-9" in result.output


def test_profiles_show_outputs_profile_json() -> None:
    result = runner.invoke(app, ["profiles", "show", "ubuntu-2204"])

    assert result.exit_code == 0
    assert '"id": "ubuntu-2204"' in result.output
    assert '"name": "Ubuntu 22.04"' in result.output
