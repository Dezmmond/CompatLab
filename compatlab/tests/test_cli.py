import json
import shutil
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

import pytest
from compatlab.models import (
    ArtifactInfo,
    ArtifactReport,
    DependencyEdge,
    DependencyGraph,
    DependencyResolutionKind,
    ElfInfo,
    LibraryFact,
    OsReleaseFacts,
    SystemFacts,
    SymbolVersionFacts,
)

from compatlab.bundle import BundleResolutionResult
from compatlab.cli import app
from compatlab.profile.docker import DockerError
from compatlab.profile.catalog import load_profile_file
from compatlab.tests.rpm_fixtures import write_test_rpm
from compatlab.tests.wheel_fixtures import write_test_wheel


@dataclass(frozen=True)
class CliResult:
    exit_code: int
    output: str


class CliRunner:
    @staticmethod
    def invoke(cli_app, args: list[str]) -> CliResult:
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                cli_app(args)
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else 1
            else:
                code = 0
        return CliResult(exit_code=code, output=stdout.getvalue() + stderr.getvalue())


runner = CliRunner()


PROFILE_YAML = """
id: local
name: Local Test
arch: x86_64
libc:
  family: glibc
  version: "2.39"
libstdcxx:
  max_glibcxx: "3.4.33"
  max_cxxabi: "1.3.15"
interpreters:
  - /lib64/ld-linux-x86-64.so.2
provided_libraries:
  - soname: libc.so.6
"""


def _write_profile(path: Path) -> None:
    path.write_text(PROFILE_YAML, encoding="utf-8")


def _write_wheel(path: Path, *, native: bool = False, purelib: bool = True) -> None:
    with zipfile.ZipFile(path, "w") as wheel:
        tag = "cp311-cp311-linux_x86_64" if native else "py3-none-any"
        wheel.writestr(
            "demo-1.0.0.dist-info/WHEEL",
            "\n".join(
                [
                    "Wheel-Version: 1.0",
                    "Generator: compatlab-test",
                    f"Root-Is-Purelib: {str(purelib).lower()}",
                    f"Tag: {tag}",
                    "",
                ]
            ),
        )
        wheel.writestr(
            "demo-1.0.0.dist-info/METADATA",
            "Metadata-Version: 2.1\nName: demo\nVersion: 1.0.0\n",
        )
        wheel.writestr("demo-1.0.0.dist-info/RECORD", "")
        wheel.writestr("demo/__init__.py", b"")
        if native:
            wheel.writestr("demo/_native.cpython-311-x86_64-linux-gnu.so", b"\x7fELFfake")


def _system_facts() -> SystemFacts:
    return SystemFacts(
        os_release=OsReleaseFacts(id="ubuntu", version_id="24.04", pretty_name="Ubuntu 24.04 LTS"),
        architecture="x86_64",
        glibc_version="2.39",
        dynamic_linkers=["/lib64/ld-linux-x86-64.so.2"],
        libraries=[LibraryFact(soname="libc.so.6", path="/lib/libc.so.6")],
        symbol_versions=SymbolVersionFacts(
            glibc=["2.39"],
            glibcxx=["3.4.33"],
            cxxabi=["1.3.15"],
        ),
    )


def _docker_facts() -> SystemFacts:
    facts = _system_facts()
    return facts.model_copy(
        update={
            "source_image": "ubuntu:22.04",
            "source_image_id": "sha256:abc",
            "platform": "linux/amd64",
        }
    )


def _docker_runtime_facts() -> SystemFacts:
    facts = _docker_facts()
    return facts.model_copy(
        update={
            "runtime_preset": "cpp-runtime",
            "runtime_packages": ["libstdc++6", "libgcc-s1"],
            "package_manager": "apt-get",
        }
    )


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
    raw = json.loads(report.read_text(encoding="utf-8"))
    assert raw["summary"]["status"] == "warning"
    assert raw["diagnostics"][0]["code"] == "CL_ELF_SCAN_FAILED"


def test_scan_command_supports_rpm_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    artifact = tmp_path / "demo-1.0.0-1.x86_64.rpm"
    report = tmp_path / "report.json"
    write_test_rpm(artifact, files={"usr/bin/demo": b"\x7fELFfake"})
    monkeypatch.setattr(
        "compatlab.rpm.scanner.scan_elf_path",
        lambda path: ArtifactReport(
            artifact=ArtifactInfo(path=str(path), kind="ELF"),
            elf=ElfInfo(elf_class="ELF64", machine="Advanced Micro Devices X86-64"),
        ),
    )

    result = runner.invoke(app, ["scan", str(artifact), "--json", str(report)])

    assert result.exit_code == 0
    assert "RPM package" in result.output
    raw = json.loads(report.read_text(encoding="utf-8"))
    assert raw["artifact"]["kind"] == "rpm"
    assert raw["package"]["name"] == "demo"
    assert raw["package"]["payload_file_count"] == 1
    assert raw["entries"][0]["path"] == "/usr/bin/demo"


def test_scan_command_supports_rpm_html_no_native(tmp_path: Path) -> None:
    artifact = tmp_path / "demo-1.0.0-1.x86_64.rpm"
    report = tmp_path / "report.html"
    write_test_rpm(artifact, files={"usr/share/doc/readme": b"hello"})

    result = runner.invoke(app, ["scan", str(artifact), "--html", str(report)])

    assert result.exit_code == 0
    html = report.read_text(encoding="utf-8")
    assert "RPM Metadata" in html
    assert "Package Native Entries" in html
    assert "CL_RPM_NO_ELF_ENTRIES" in html


def test_scan_command_supports_wheel_json(tmp_path: Path) -> None:
    artifact = tmp_path / "demo-1.0.0-py3-none-any.whl"
    report = tmp_path / "report.json"
    write_test_wheel(artifact)

    result = runner.invoke(app, ["scan", str(artifact), "--json", str(report)])

    assert result.exit_code == 0
    raw = json.loads(report.read_text(encoding="utf-8"))
    assert raw["artifact"]["kind"] == "wheel"
    assert raw["package"]["name"] == "demo"
    assert raw["summary"]["issue_codes"]["CL_WHEEL_NO_NATIVE_EXTENSIONS"] == 1


def test_scan_command_writes_html_report(tmp_path: Path) -> None:
    artifact = tmp_path / "demo-app"
    artifact.write_bytes(b"not really elf yet")
    report = tmp_path / "report.html"

    result = runner.invoke(app, ["scan", str(artifact), "--html", str(report)])

    assert result.exit_code == 0
    html = report.read_text(encoding="utf-8")
    assert "CompatLab ArtifactDoctor" in html
    assert "Diagnostics" in html
    assert "CL_ELF_SCAN_FAILED" in html


def test_scan_command_rejects_invalid_html_output_path(tmp_path: Path) -> None:
    artifact = tmp_path / "demo-app"
    artifact.write_bytes(b"not really elf yet")

    result = runner.invoke(
        app,
        ["scan", str(artifact), "--html", str(tmp_path / "missing" / "report.html")],
    )

    assert result.exit_code == 2
    assert "Could not write report" in result.output


def test_scan_command_fail_on_warning_returns_nonzero(tmp_path: Path) -> None:
    artifact = tmp_path / "demo-app"
    artifact.write_bytes(b"not really elf yet")

    result = runner.invoke(app, ["scan", str(artifact), "--fail-on", "warning"])

    assert result.exit_code == 1


def test_scan_command_fail_on_never_returns_zero_for_diagnostics(tmp_path: Path) -> None:
    artifact = tmp_path / "demo-app"
    artifact.write_bytes(b"not really elf yet")

    result = runner.invoke(app, ["scan", str(artifact), "--fail-on", "never"])

    assert result.exit_code == 0


def test_scan_command_writes_bundle_dependency_graph(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = tmp_path / "dist"
    artifact = bundle / "demo-app"
    bundle.mkdir()
    artifact.write_bytes(b"not really elf yet")
    output = tmp_path / "report.json"
    graph = DependencyGraph(
        entrypoint_artifact_id="demo-app",
        edges=[
            DependencyEdge(
                from_artifact_id="demo-app",
                needed_name="libfoo.so",
                resolution_kind=DependencyResolutionKind.MISSING,
            )
        ],
        unresolved_dependencies=[
            DependencyEdge(
                from_artifact_id="demo-app",
                needed_name="libfoo.so",
                resolution_kind=DependencyResolutionKind.MISSING,
            )
        ],
    )

    monkeypatch.setattr(
        "compatlab.bundle.resolver.resolve_bundle_dependencies",
        lambda *args, **kwargs: BundleResolutionResult(graph=graph, reports={}, warnings=[]),
    )

    result = runner.invoke(
        app,
        [
            "scan",
            str(artifact),
            "--bundle-root",
            str(bundle),
            "--recursive",
            "--fail-on",
            "never",
            "--json",
            str(output),
        ],
    )

    assert result.exit_code == 0
    raw = json.loads(output.read_text(encoding="utf-8"))
    assert raw["summary"]["issue_codes"]["CL_LIB_MISSING"] == 1
    assert "CL_LIB_MISSING" in {issue["code"] for issue in raw["diagnostics"]}
    assert raw["dependency_graph"]["edges"][0]["resolution_kind"] == "missing"
    assert "Dependency Resolution" in result.output
    assert "Diagnostics" in result.output


def test_scan_command_writes_json_and_html_together(tmp_path: Path) -> None:
    artifact = tmp_path / "demo-app"
    artifact.write_bytes(b"not really elf yet")
    json_report = tmp_path / "report.json"
    html_report = tmp_path / "report.html"

    result = runner.invoke(
        app,
        [
            "scan",
            str(artifact),
            "--json",
            str(json_report),
            "--html",
            str(html_report),
        ],
    )

    assert result.exit_code == 0
    assert json_report.exists()
    assert html_report.exists()
    assert "CL_ELF_SCAN_FAILED" in html_report.read_text(encoding="utf-8")


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


def test_compare_command_accepts_external_target_file(tmp_path: Path) -> None:
    artifact = tmp_path / "demo-app"
    artifact.write_bytes(b"not really elf yet")
    profile = tmp_path / "local.yaml"
    _write_profile(profile)

    result = runner.invoke(app, ["compare", str(artifact), "--target-file", str(profile)])

    assert result.exit_code == 2
    assert "Local Test" in result.output
    assert "scan.failed" in result.output


def test_compare_command_supports_rpm_target_file_json_html(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = tmp_path / "demo-1.0.0-1.x86_64.rpm"
    profile = tmp_path / "local.yaml"
    json_output = tmp_path / "report.json"
    html_output = tmp_path / "report.html"
    _write_profile(profile)
    write_test_rpm(artifact, files={"usr/bin/demo": b"\x7fELFfake"})
    monkeypatch.setattr(
        "compatlab.rpm.scanner.scan_elf_path",
        lambda path: ArtifactReport(
            artifact=ArtifactInfo(path=str(path), kind="ELF"),
            elf=ElfInfo(
                elf_class="ELF64",
                machine="Advanced Micro Devices X86-64",
                needed=["libmissing.so.1"],
            ),
        ),
    )

    result = runner.invoke(
        app,
        [
            "compare",
            str(artifact),
            "--target-file",
            str(profile),
            "--fail-on",
            "never",
            "--json",
            str(json_output),
            "--html",
            str(html_output),
        ],
    )

    assert result.exit_code == 0
    raw = json.loads(json_output.read_text(encoding="utf-8"))
    assert raw["summary"]["status"] == "failed"
    assert raw["entries"][0]["diagnostics"][0]["code"] == "CL_LIB_MISSING"
    assert "CL_LIB_MISSING" in html_output.read_text(encoding="utf-8")


def test_compare_command_supports_rpm_builtin_target_fail_on_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = tmp_path / "demo-1.0.0-1.x86_64.rpm"
    write_test_rpm(artifact, files={"usr/bin/demo": b"\x7fELFfake"})
    monkeypatch.setattr(
        "compatlab.rpm.scanner.scan_elf_path",
        lambda path: ArtifactReport(
            artifact=ArtifactInfo(path=str(path), kind="ELF"),
            elf=ElfInfo(
                elf_class="ELF64",
                machine="Advanced Micro Devices X86-64",
                runpath=["/tmp/build/lib"],
            ),
        ),
    )

    result = runner.invoke(
        app,
        ["compare", str(artifact), "--target", "ubuntu-2204", "--fail-on", "warning"],
    )

    assert result.exit_code == 1
    assert "CL_RPATH_ABSOLUTE" in result.output


def test_compare_command_supports_native_wheel_target_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = tmp_path / "demo-1.0.0-cp311-cp311-linux_x86_64.whl"
    profile = tmp_path / "local.yaml"
    output = tmp_path / "report.json"
    _write_wheel(artifact, native=True, purelib=False)
    _write_profile(profile)
    monkeypatch.setattr(
        "compatlab.wheels.scanner.scan_elf_path",
        lambda path: ArtifactReport(
            artifact=ArtifactInfo(path=str(path), kind="ELF"),
            elf=ElfInfo(
                elf_class="ELF64",
                machine="Advanced Micro Devices X86-64",
                needed=["libmissing.so.1"],
            ),
        ),
    )

    result = runner.invoke(
        app,
        [
            "compare",
            str(artifact),
            "--target-file",
            str(profile),
            "--fail-on",
            "never",
            "--json",
            str(output),
        ],
    )

    assert result.exit_code == 0
    assert "Native compatibility" in result.output
    raw = json.loads(output.read_text(encoding="utf-8"))
    assert raw["summary"]["status"] == "failed"
    assert raw["native_entries"][0]["diagnostics"][0]["code"] == "CL_LIB_MISSING"


def test_compare_command_supports_native_wheel_builtin_target_fail_on_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = tmp_path / "demo-1.0.0-cp311-cp311-linux_x86_64.whl"
    _write_wheel(artifact, native=True, purelib=True)
    monkeypatch.setattr(
        "compatlab.wheels.scanner.scan_elf_path",
        lambda path: ArtifactReport(
            artifact=ArtifactInfo(path=str(path), kind="ELF"),
            elf=ElfInfo(elf_class="ELF64", machine="Advanced Micro Devices X86-64"),
        ),
    )

    result = runner.invoke(
        app,
        ["compare", str(artifact), "--target", "ubuntu-2204", "--fail-on", "warning"],
    )

    assert result.exit_code == 1
    assert "CL_WHEEL_PURELIB_WITH_NATIVE_CODE" in result.output


def test_compare_command_writes_wheel_html_before_nonzero_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = tmp_path / "demo-1.0.0-cp311-cp311-linux_x86_64.whl"
    profile = tmp_path / "local.yaml"
    output = tmp_path / "report.html"
    _write_wheel(artifact, native=True, purelib=False)
    _write_profile(profile)
    monkeypatch.setattr(
        "compatlab.wheels.scanner.scan_elf_path",
        lambda path: ArtifactReport(
            artifact=ArtifactInfo(path=str(path), kind="ELF"),
            elf=ElfInfo(
                elf_class="ELF64",
                machine="Advanced Micro Devices X86-64",
                needed=["libmissing.so.1"],
            ),
        ),
    )

    result = runner.invoke(
        app,
        ["compare", str(artifact), "--target-file", str(profile), "--html", str(output)],
    )

    assert result.exit_code == 1
    assert output.exists()
    assert "CL_LIB_MISSING" in output.read_text(encoding="utf-8")


def test_compare_command_rejects_missing_external_target_file(tmp_path: Path) -> None:
    artifact = tmp_path / "demo-app"
    artifact.write_bytes(b"not really elf yet")

    result = runner.invoke(
        app,
        ["compare", str(artifact), "--target-file", str(tmp_path / "missing.yaml")],
    )

    assert result.exit_code == 2
    assert "Profile file does not exist" in result.output


def test_compare_command_rejects_invalid_external_target_file(tmp_path: Path) -> None:
    artifact = tmp_path / "demo-app"
    artifact.write_bytes(b"not really elf yet")
    profile = tmp_path / "broken.yaml"
    profile.write_text("id: local\n", encoding="utf-8")

    result = runner.invoke(app, ["compare", str(artifact), "--target-file", str(profile)])

    assert result.exit_code == 2
    assert "Invalid target profile" in result.output


def test_compare_command_requires_exactly_one_target_selector(tmp_path: Path) -> None:
    artifact = tmp_path / "demo-app"
    artifact.write_bytes(b"not really elf yet")
    profile = tmp_path / "local.yaml"
    _write_profile(profile)

    neither = runner.invoke(app, ["compare", str(artifact)])
    both = runner.invoke(
        app,
        ["compare", str(artifact), "--target", "ubuntu-2404", "--target-file", str(profile)],
    )

    assert neither.exit_code == 2
    assert both.exit_code == 2
    assert "Provide exactly one" in neither.output
    assert "Provide exactly one" in both.output


def test_compare_command_fail_on_warning_returns_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = tmp_path / "demo-app"
    artifact.write_bytes(b"elf")
    profile = tmp_path / "local.yaml"
    _write_profile(profile)

    monkeypatch.setattr(
        "compatlab.elfscan.scanner.scan_path",
        lambda path: ArtifactReport(
            artifact=ArtifactInfo(path=str(path), kind="ELF"),
            elf=ElfInfo(
                elf_class="ELF64",
                machine="Advanced Micro Devices X86-64",
                runpath=["/tmp/build/lib"],
            ),
        ),
    )

    result = runner.invoke(
        app,
        [
            "compare",
            str(artifact),
            "--target-file",
            str(profile),
            "--fail-on",
            "warning",
        ],
    )

    assert result.exit_code == 1
    assert "CL_RPATH_ABSOLUTE" in result.output


def test_compare_command_fail_on_never_writes_diagnostic_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = tmp_path / "demo-app"
    artifact.write_bytes(b"elf")
    profile = tmp_path / "local.yaml"
    output = tmp_path / "report.json"
    _write_profile(profile)

    monkeypatch.setattr(
        "compatlab.elfscan.scanner.scan_path",
        lambda path: ArtifactReport(
            artifact=ArtifactInfo(path=str(path), kind="ELF"),
            elf=ElfInfo(
                elf_class="ELF64",
                machine="Advanced Micro Devices X86-64",
                needed=["libmissing.so.1"],
            ),
        ),
    )

    result = runner.invoke(
        app,
        [
            "compare",
            str(artifact),
            "--target-file",
            str(profile),
            "--fail-on",
            "never",
            "--json",
            str(output),
        ],
    )

    assert result.exit_code == 0
    raw = json.loads(output.read_text(encoding="utf-8"))
    assert raw["summary"]["status"] == "failed"
    assert raw["diagnostics"][0]["code"] == "CL_LIB_MISSING"


def test_compare_command_writes_html_report_on_scan_error(tmp_path: Path) -> None:
    artifact = tmp_path / "demo-app"
    artifact.write_bytes(b"not really elf yet")
    output = tmp_path / "report.html"

    result = runner.invoke(
        app,
        ["compare", str(artifact), "--target", "ubuntu-1804", "--html", str(output)],
    )

    assert result.exit_code == 2
    html = output.read_text(encoding="utf-8")
    assert "CompatLab ArtifactDoctor" in html
    assert "compare" in html
    assert "CL_ELF_SCAN_FAILED" in html


def test_compare_command_fail_on_never_writes_html_and_returns_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = tmp_path / "demo-app"
    artifact.write_bytes(b"elf")
    profile = tmp_path / "local.yaml"
    output = tmp_path / "report.html"
    _write_profile(profile)

    monkeypatch.setattr(
        "compatlab.elfscan.scanner.scan_path",
        lambda path: ArtifactReport(
            artifact=ArtifactInfo(path=str(path), kind="ELF"),
            elf=ElfInfo(
                elf_class="ELF64",
                machine="Advanced Micro Devices X86-64",
                needed=["libmissing.so.1"],
            ),
        ),
    )

    result = runner.invoke(
        app,
        [
            "compare",
            str(artifact),
            "--target-file",
            str(profile),
            "--fail-on",
            "never",
            "--html",
            str(output),
        ],
    )

    assert result.exit_code == 0
    assert "CL_LIB_MISSING" in output.read_text(encoding="utf-8")


def test_compare_command_fail_on_error_writes_html_before_nonzero_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = tmp_path / "demo-app"
    artifact.write_bytes(b"elf")
    profile = tmp_path / "local.yaml"
    output = tmp_path / "report.html"
    _write_profile(profile)

    monkeypatch.setattr(
        "compatlab.elfscan.scanner.scan_path",
        lambda path: ArtifactReport(
            artifact=ArtifactInfo(path=str(path), kind="ELF"),
            elf=ElfInfo(
                elf_class="ELF64",
                machine="Advanced Micro Devices X86-64",
                needed=["libmissing.so.1"],
            ),
        ),
    )

    result = runner.invoke(
        app,
        [
            "compare",
            str(artifact),
            "--target-file",
            str(profile),
            "--fail-on",
            "error",
            "--html",
            str(output),
        ],
    )

    assert result.exit_code == 1
    assert output.exists()
    assert "CL_LIB_MISSING" in output.read_text(encoding="utf-8")


def test_compare_command_writes_json_and_html_together(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = tmp_path / "demo-app"
    artifact.write_bytes(b"elf")
    profile = tmp_path / "local.yaml"
    json_output = tmp_path / "report.json"
    html_output = tmp_path / "report.html"
    _write_profile(profile)

    monkeypatch.setattr(
        "compatlab.elfscan.scanner.scan_path",
        lambda path: ArtifactReport(
            artifact=ArtifactInfo(path=str(path), kind="ELF"),
            elf=ElfInfo(elf_class="ELF64", machine="Advanced Micro Devices X86-64"),
        ),
    )

    result = runner.invoke(
        app,
        [
            "compare",
            str(artifact),
            "--target-file",
            str(profile),
            "--json",
            str(json_output),
            "--html",
            str(html_output),
        ],
    )

    assert result.exit_code == 0
    assert json_output.exists()
    assert html_output.exists()
    assert "CompatLab ArtifactDoctor" in html_output.read_text(encoding="utf-8")


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


def test_runtime_presets_list_outputs_builtin_presets() -> None:
    result = runner.invoke(app, ["profiles", "runtime-presets", "list"])

    assert result.exit_code == 0
    assert "cpp-runtime" in result.output
    assert "python-runtime" in result.output


def test_runtime_presets_show_outputs_preset_details() -> None:
    result = runner.invoke(app, ["profiles", "runtime-presets", "show", "cpp-runtime"])

    assert result.exit_code == 0
    assert "Common C/C++ runtime libraries" in result.output
    assert "apt-get" in result.output
    assert "libstdc++6" in result.output


def test_runtime_presets_show_rejects_unknown_preset() -> None:
    result = runner.invoke(app, ["profiles", "runtime-presets", "show", "node-runtime"])

    assert result.exit_code == 2
    assert "Unknown runtime preset" in result.output


def test_profiles_detect_writes_raw_facts_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "system-facts.json"
    monkeypatch.setattr("compatlab.profile.local.detect_current_system", _system_facts)

    result = runner.invoke(app, ["profiles", "detect", "--json", str(output)])

    assert result.exit_code == 0
    raw = json.loads(output.read_text(encoding="utf-8"))
    assert raw["os_release"]["id"] == "ubuntu"
    assert raw["architecture"] == "x86_64"
    assert raw["symbol_versions"]["glibc"] == ["2.39"]
    assert "System profile detected" in result.output


def test_profiles_detect_from_image_writes_raw_facts_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "system-facts.json"

    def fake_detect(image: str, **kwargs: object) -> SystemFacts:
        assert image == "ubuntu:22.04"
        assert kwargs["platform"] == "linux/amd64"
        assert kwargs["pull"] is True
        return _docker_facts()

    monkeypatch.setattr("compatlab.profile.docker.detect_docker_image_system", fake_detect)

    result = runner.invoke(
        app,
        [
            "profiles",
            "detect",
            "--from-image",
            "ubuntu:22.04",
            "--platform",
            "linux/amd64",
            "--pull",
            "--json",
            str(output),
        ],
    )

    assert result.exit_code == 0
    raw = json.loads(output.read_text(encoding="utf-8"))
    assert raw["source_image"] == "ubuntu:22.04"
    assert raw["platform"] == "linux/amd64"


def test_profiles_detect_from_image_with_runtime_preset_writes_runtime_facts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "system-facts.json"

    def fake_detect(image: str, **kwargs: object) -> SystemFacts:
        assert image == "ubuntu:22.04"
        assert kwargs["runtime_preset"] == "cpp-runtime"
        return _docker_runtime_facts()

    monkeypatch.setattr("compatlab.profile.docker.detect_docker_image_system", fake_detect)

    result = runner.invoke(
        app,
        [
            "profiles",
            "detect",
            "--from-image",
            "ubuntu:22.04",
            "--runtime-preset",
            "cpp-runtime",
            "--json",
            str(output),
        ],
    )

    assert result.exit_code == 0
    raw = json.loads(output.read_text(encoding="utf-8"))
    assert raw["runtime_preset"] == "cpp-runtime"
    assert raw["runtime_packages"] == ["libstdc++6", "libgcc-s1"]
    assert raw["package_manager"] == "apt-get"


def test_profiles_detect_rejects_runtime_preset_without_image() -> None:
    result = runner.invoke(app, ["profiles", "detect", "--runtime-preset", "cpp-runtime"])

    assert result.exit_code == 2
    assert "--runtime-preset is valid only with --from-image" in result.output


def test_profiles_generate_writes_loadable_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "local.yaml"
    monkeypatch.setattr("compatlab.profile.local.detect_current_system", _system_facts)

    result = runner.invoke(
        app,
        ["profiles", "generate", "--from-current", "--name", "local", "--output", str(output)],
    )

    assert result.exit_code == 0
    assert "generated" in result.output
    generated = output.read_text(encoding="utf-8")
    assert "metadata:" in generated
    assert "generated_by: compatlab" in generated
    loaded = load_profile_file(output)
    assert loaded.id == "local"
    assert loaded.metadata is not None


def test_profiles_generate_from_image_writes_loadable_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "ubuntu-2204.yaml"

    def fake_detect(image: str, **kwargs: object) -> SystemFacts:
        assert image == "ubuntu:22.04"
        assert kwargs["platform"] == "linux/amd64"
        assert kwargs["pull"] is True
        return _docker_facts()

    monkeypatch.setattr("compatlab.profile.docker.detect_docker_image_system", fake_detect)

    result = runner.invoke(
        app,
        [
            "profiles",
            "generate",
            "--from-image",
            "ubuntu:22.04",
            "--platform",
            "linux/amd64",
            "--pull",
            "--name",
            "ubuntu-2204-docker",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    assert "Docker image profile generated" in result.output
    loaded = load_profile_file(output)
    assert loaded.id == "ubuntu-2204-docker"
    assert loaded.metadata is not None
    assert loaded.metadata.source == "docker-image"
    assert loaded.metadata.source_image == "ubuntu:22.04"
    assert loaded.metadata.platform == "linux/amd64"


def test_profiles_generate_from_image_with_runtime_preset_writes_runtime_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "ubuntu-2204.yaml"

    def fake_detect(image: str, **kwargs: object) -> SystemFacts:
        assert image == "ubuntu:22.04"
        assert kwargs["runtime_preset"] == "cpp-runtime"
        return _docker_runtime_facts()

    monkeypatch.setattr("compatlab.profile.docker.detect_docker_image_system", fake_detect)

    result = runner.invoke(
        app,
        [
            "profiles",
            "generate",
            "--from-image",
            "ubuntu:22.04",
            "--runtime-preset",
            "cpp-runtime",
            "--name",
            "ubuntu-2204-cpp-runtime",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    assert "Runtime preset:" in result.output
    loaded = load_profile_file(output)
    assert loaded.metadata is not None
    assert loaded.metadata.source == "docker-runtime-image"
    assert loaded.metadata.runtime_preset == "cpp-runtime"
    assert loaded.metadata.runtime_packages == ["libstdc++6", "libgcc-s1"]
    assert loaded.metadata.package_manager == "apt-get"


def test_profiles_generate_rejects_multiple_sources(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "profiles",
            "generate",
            "--from-current",
            "--from-image",
            "ubuntu:22.04",
            "--output",
            str(tmp_path / "local.yaml"),
        ],
    )

    assert result.exit_code == 2
    assert "Provide exactly one" in result.output


def test_profiles_generate_rejects_runtime_preset_with_current_system(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "profiles",
            "generate",
            "--from-current",
            "--runtime-preset",
            "cpp-runtime",
            "--output",
            str(tmp_path / "local.yaml"),
        ],
    )

    assert result.exit_code == 2
    assert "--runtime-preset is valid only with --from-image" in result.output


def test_profiles_generate_from_image_reports_docker_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_detect(image: str, **kwargs: object) -> SystemFacts:
        raise DockerError("Docker is not available.")

    monkeypatch.setattr("compatlab.profile.docker.detect_docker_image_system", fake_detect)

    result = runner.invoke(
        app,
        [
            "profiles",
            "generate",
            "--from-image",
            "ubuntu:22.04",
            "--name",
            "ubuntu-2204-docker",
            "--output",
            str(tmp_path / "ubuntu-2204.yaml"),
        ],
    )

    assert result.exit_code == 2
    assert "Docker is not available" in result.output


def test_profiles_validate_accepts_valid_profile(tmp_path: Path) -> None:
    profile = tmp_path / "local.yaml"
    _write_profile(profile)

    result = runner.invoke(app, ["profiles", "validate", str(profile)])

    assert result.exit_code == 0
    assert "Status:" in result.output
    assert "valid" in result.output
    assert "local" in result.output


def test_profiles_validate_rejects_missing_profile(tmp_path: Path) -> None:
    result = runner.invoke(app, ["profiles", "validate", str(tmp_path / "missing.yaml")])

    assert result.exit_code == 2
    assert "invalid" in result.output
    assert "Profile file does not exist" in result.output


def test_profiles_validate_rejects_invalid_profile_and_writes_json(tmp_path: Path) -> None:
    profile = tmp_path / "broken.yaml"
    profile.write_text("id: local\n", encoding="utf-8")
    output = tmp_path / "validation.json"

    result = runner.invoke(app, ["profiles", "validate", str(profile), "--json", str(output)])

    assert result.exit_code == 2
    raw = json.loads(output.read_text(encoding="utf-8"))
    assert raw["status"] == "invalid"
    assert "Invalid target profile" in raw["error"]


def test_profiles_validate_rejects_malformed_yaml(tmp_path: Path) -> None:
    profile = tmp_path / "broken.yaml"
    profile.write_text("id: [\n", encoding="utf-8")

    result = runner.invoke(app, ["profiles", "validate", str(profile)])

    assert result.exit_code == 2
    assert "Invalid YAML profile" in result.output


def test_profiles_validate_rejects_wrong_field_types(tmp_path: Path) -> None:
    profile = tmp_path / "wrong-types.yaml"
    profile.write_text(
        """
id: local
name: Local Test
arch:
  - x86_64
libc:
  family: glibc
  version: "2.39"
""",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["profiles", "validate", str(profile)])

    assert result.exit_code == 2
    assert "Invalid target profile" in result.output
