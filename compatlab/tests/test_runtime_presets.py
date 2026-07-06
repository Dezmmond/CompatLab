import tarfile
from io import BytesIO
from pathlib import Path

import pytest
from compatlab.models import OsReleaseFacts

from compatlab.profile.runtimes import (
    RuntimePresetError,
    build_install_script,
    detect_package_manager,
    detect_package_manager_from_rootfs,
    get_runtime_preset,
    list_runtime_presets,
    packages_for_manager,
)


def test_list_runtime_presets_contains_initial_presets() -> None:
    names = [preset.name for preset in list_runtime_presets()]

    assert names == ["cpp-runtime", "python-runtime"]


def test_get_runtime_preset_returns_stable_cpp_packages() -> None:
    preset = get_runtime_preset("cpp-runtime")

    assert preset.description == "Common C/C++ runtime libraries"
    assert preset.supported_package_managers == ["apt-get", "dnf", "yum"]
    assert packages_for_manager(preset, "apt-get") == ["libstdc++6", "libgcc-s1"]
    assert packages_for_manager(preset, "dnf") == ["libstdc++", "libgcc"]
    assert packages_for_manager(preset, "yum") == ["libstdc++", "libgcc"]


def test_get_runtime_preset_returns_stable_python_packages() -> None:
    preset = get_runtime_preset("python-runtime")

    assert packages_for_manager(preset, "apt-get") == ["python3", "libpython3-stdlib"]
    assert packages_for_manager(preset, "dnf") == ["python3", "python3-libs"]
    assert packages_for_manager(preset, "yum") == ["python3", "python3-libs"]


def test_unknown_runtime_preset_raises_useful_error() -> None:
    with pytest.raises(RuntimePresetError, match="Unknown runtime preset 'node-runtime'"):
        get_runtime_preset("node-runtime")


def test_packages_for_unsupported_manager_raises_useful_error() -> None:
    preset = get_runtime_preset("cpp-runtime")

    with pytest.raises(RuntimePresetError, match="not supported for package manager 'apk'"):
        packages_for_manager(preset, "apk")


def test_detect_package_manager_maps_debian_family() -> None:
    assert detect_package_manager(OsReleaseFacts(id="ubuntu")) == "apt-get"
    assert detect_package_manager(OsReleaseFacts(id="debian")) == "apt-get"


def test_detect_package_manager_maps_rhel_family() -> None:
    assert detect_package_manager(OsReleaseFacts(id="rocky")) == "dnf"
    assert detect_package_manager(OsReleaseFacts(id="rhel")) == "dnf"
    assert detect_package_manager(OsReleaseFacts(id="centos")) == "yum"


def test_detect_package_manager_prefers_available_binary_paths() -> None:
    assert (
        detect_package_manager(
            OsReleaseFacts(id="ubuntu"),
            available_paths={"/usr/bin/yum"},
        )
        == "yum"
    )


def test_detect_package_manager_from_rootfs_uses_tar_contents(tmp_path: Path) -> None:
    rootfs = tmp_path / "rootfs.tar"
    _write_rootfs_tar(rootfs, os_release=b"ID=unknown\n", binaries=["/usr/bin/dnf"])

    assert detect_package_manager_from_rootfs(str(rootfs)) == "dnf"


def test_detect_package_manager_rejects_unsupported_os() -> None:
    with pytest.raises(RuntimePresetError, match="Could not detect a supported package manager"):
        detect_package_manager(OsReleaseFacts(id="alpine"))


def test_build_apt_get_install_script() -> None:
    script = build_install_script("apt-get", ["libstdc++6", "libgcc-s1"])

    assert script.splitlines() == [
        "export DEBIAN_FRONTEND=noninteractive",
        "apt-get update",
        "apt-get install -y --no-install-recommends libstdc++6 libgcc-s1",
        "rm -rf /var/lib/apt/lists/*",
    ]


def test_build_dnf_install_script() -> None:
    script = build_install_script("dnf", ["libstdc++", "libgcc"])

    assert script.splitlines() == [
        "dnf install -y --setopt=install_weak_deps=False libstdc++ libgcc",
        "dnf clean all",
    ]


def test_build_yum_install_script() -> None:
    script = build_install_script("yum", ["libstdc++", "libgcc"])

    assert script.splitlines() == [
        "yum install -y libstdc++ libgcc",
        "yum clean all",
    ]


def test_build_install_script_rejects_empty_packages() -> None:
    with pytest.raises(RuntimePresetError, match="must not be empty"):
        build_install_script("apt-get", [])


def test_build_install_script_rejects_unsupported_manager() -> None:
    with pytest.raises(RuntimePresetError, match="Unsupported package manager 'apk'"):
        build_install_script("apk", ["libstdc++"])


def _write_rootfs_tar(path: Path, *, os_release: bytes, binaries: list[str]) -> None:
    with tarfile.open(path, "w") as archive:
        _add_file(archive, "etc/os-release", os_release)
        for binary in binaries:
            _add_file(archive, binary.lstrip("/"), b"")


def _add_file(archive: tarfile.TarFile, name: str, content: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(content)
    archive.addfile(info, BytesIO(content))
