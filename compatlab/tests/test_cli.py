from pathlib import Path
import json
import shutil

import pytest
from typer.testing import CliRunner

from compatlab.src.cli import app
from compatlab.src.profile.docker_cli import DockerError
from compatlab.src.profile.loader import load_profile_file
from compatlab.src.profile.models import (
    LibraryFact,
    OsReleaseFacts,
    SystemFacts,
    SymbolVersionFacts,
)


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
    monkeypatch.setattr("compatlab.src.cli.detect_current_system", _system_facts)

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

    monkeypatch.setattr("compatlab.src.cli.detect_docker_image_system", fake_detect)

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

    monkeypatch.setattr("compatlab.src.cli.detect_docker_image_system", fake_detect)

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
    monkeypatch.setattr("compatlab.src.cli.detect_current_system", _system_facts)

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

    monkeypatch.setattr("compatlab.src.cli.detect_docker_image_system", fake_detect)

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

    monkeypatch.setattr("compatlab.src.cli.detect_docker_image_system", fake_detect)

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

    monkeypatch.setattr("compatlab.src.cli.detect_docker_image_system", fake_detect)

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
