import tarfile
from io import BytesIO
from pathlib import Path

import pytest

from compatlab.elfscan.command import CommandResult
from compatlab.profile.docker import DockerImageMetadata
from compatlab.profile.docker import (
    detect_docker_image_system,
    system_facts_from_rootfs_tar,
)


def _write_rootfs_tar(path: Path, *, binaries: list[str] | None = None) -> None:
    with tarfile.open(path, "w") as archive:
        _add_file(
            archive,
            "etc/os-release",
            b'ID=ubuntu\nVERSION_ID="22.04"\nPRETTY_NAME="Ubuntu 22.04 LTS"\n',
        )
        _add_file(archive, "lib/x86_64-linux-gnu/libc.so.6", b"libc")
        _add_file(archive, "usr/lib/x86_64-linux-gnu/libstdc++.so.6", b"libstdc++")
        _add_file(archive, "lib64/ld-linux-x86-64.so.2", b"loader")
        for binary in binaries or []:
            _add_file(archive, binary.lstrip("/"), b"")


def _add_file(archive: tarfile.TarFile, name: str, content: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(content)
    archive.addfile(info, BytesIO(content))


def test_system_facts_from_rootfs_tar_uses_metadata_and_rootfs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rootfs = tmp_path / "rootfs.tar"
    _write_rootfs_tar(rootfs)

    def fake_readelf(args: list[str], path: Path) -> CommandResult:
        if path.name == "libc.so.6":
            stdout = "Name: GLIBC_2.2.5\nName: GLIBC_2.35\n"
        else:
            stdout = "Name: GLIBCXX_3.4.30\nName: CXXABI_1.3.13\n"
        return CommandResult(
            args=["readelf", *args, str(path)], returncode=0, stdout=stdout, stderr=""
        )

    monkeypatch.setattr("compatlab.profile.docker.run_readelf", fake_readelf)

    facts = system_facts_from_rootfs_tar(
        rootfs,
        image="ubuntu:22.04",
        metadata=DockerImageMetadata(
            image="ubuntu:22.04",
            image_id="sha256:abc",
            architecture="amd64",
            os="linux",
        ),
        platform="linux/amd64",
    )

    assert facts.os_release.id == "ubuntu"
    assert facts.architecture == "x86_64"
    assert facts.source_image == "ubuntu:22.04"
    assert facts.source_image_id == "sha256:abc"
    assert facts.platform == "linux/amd64"
    assert facts.dynamic_linkers == ["/lib64/ld-linux-x86-64.so.2"]
    assert facts.symbol_versions.glibc == ["2.2.5", "2.35"]
    assert facts.symbol_versions.glibcxx == ["3.4.30"]
    assert facts.symbol_versions.cxxabi == ["1.3.13"]
    assert not facts.warnings


def test_detect_docker_image_system_with_runtime_preset_exports_runtime_rootfs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeDockerClient:
        def __init__(self) -> None:
            self.runtime_script: str | None = None

        @staticmethod
        def inspect_image_metadata(image: str) -> DockerImageMetadata:
            return DockerImageMetadata(
                image=image,
                image_id="sha256:abc",
                architecture="amd64",
                os="linux",
            )

        @staticmethod
        def export_image_rootfs(
                image: str,
            output: Path,
            *,
            platform: str | None = None,
            pull: bool = False,
        ) -> None:
            assert image == "ubuntu:22.04"
            assert platform == "linux/amd64"
            assert pull is True
            _write_rootfs_tar(output, binaries=["/usr/bin/apt-get"])

        def export_runtime_rootfs(
            self,
            image: str,
            output: Path,
            install_script: str,
            *,
            platform: str | None = None,
            pull: bool = False,
        ) -> None:
            assert image == "ubuntu:22.04"
            assert platform == "linux/amd64"
            assert pull is False
            self.runtime_script = install_script
            _write_rootfs_tar(output)

    def fake_readelf(args: list[str], path: Path) -> CommandResult:
        return CommandResult(
            args=["readelf", *args, str(path)],
            returncode=0,
            stdout="Name: GLIBC_2.35\n",
            stderr="",
        )

    client = FakeDockerClient()
    monkeypatch.setattr("compatlab.profile.docker.run_readelf", fake_readelf)

    facts = detect_docker_image_system(
        "ubuntu:22.04",
        platform="linux/amd64",
        pull=True,
        runtime_preset="cpp-runtime",
        client=client,  # type: ignore[arg-type]
    )

    assert client.runtime_script is not None
    assert "apt-get install -y --no-install-recommends libstdc++6 libgcc-s1" in (
        client.runtime_script
    )
    assert facts.runtime_preset == "cpp-runtime"
    assert facts.runtime_packages == ["libstdc++6", "libgcc-s1"]
    assert facts.package_manager == "apt-get"
    assert facts.detected_by == [
        "docker image inspect",
        "docker export",
        "runtime preset install",
        "rootfs tar parser",
    ]
