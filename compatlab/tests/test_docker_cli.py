from pathlib import Path

import pytest

from compatlab.profile.docker import DockerClient, DockerError
from compatlab.scanners.elf_scanner import CommandResult


class FakeRunner:
    def __init__(self, results: list[CommandResult]) -> None:
        self.results = results
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str], timeout: float) -> CommandResult:
        self.commands.append(command)
        return self.results.pop(0)


def _result(args: list[str], returncode: int = 0, stdout: str = "", stderr: str = ""):
    return CommandResult(args=args, returncode=returncode, stdout=stdout, stderr=stderr)


def test_export_image_rootfs_builds_expected_docker_commands(tmp_path: Path) -> None:
    runner = FakeRunner(
        [
            _result(["docker"], stdout="[]"),
            _result(["docker"], stdout="container-123\n"),
            _result(["docker"]),
            _result(["docker"]),
        ]
    )
    client = DockerClient(timeout=12.0, runner=runner)

    client.export_image_rootfs(
        "ubuntu:22.04",
        tmp_path / "rootfs.tar",
        platform="linux/amd64",
    )

    assert runner.commands == [
        ["docker", "image", "inspect", "ubuntu:22.04"],
        ["docker", "create", "--platform", "linux/amd64", "ubuntu:22.04"],
        ["docker", "export", "container-123", "--output", str(tmp_path / "rootfs.tar")],
        ["docker", "rm", "-f", "container-123"],
    ]


def test_export_image_rootfs_pulls_when_requested(tmp_path: Path) -> None:
    runner = FakeRunner(
        [
            _result(["docker"], stdout="pulled"),
            _result(["docker"], stdout="container-123\n"),
            _result(["docker"]),
            _result(["docker"]),
        ]
    )
    client = DockerClient(runner=runner)

    client.export_image_rootfs(
        "ubuntu:22.04",
        tmp_path / "rootfs.tar",
        pull=True,
        platform="linux/amd64",
    )

    assert runner.commands[0] == [
        "docker",
        "pull",
        "--platform",
        "linux/amd64",
        "ubuntu:22.04",
    ]


def test_export_image_rootfs_removes_container_when_export_fails(tmp_path: Path) -> None:
    runner = FakeRunner(
        [
            _result(["docker"], stdout="[]"),
            _result(["docker"], stdout="container-123\n"),
            _result(["docker"], returncode=1, stderr="export failed"),
            _result(["docker"]),
        ]
    )
    client = DockerClient(runner=runner)

    with pytest.raises(DockerError, match="Docker export failed"):
        client.export_image_rootfs("ubuntu:22.04", tmp_path / "rootfs.tar")

    assert runner.commands[-1] == ["docker", "rm", "-f", "container-123"]


def test_export_runtime_rootfs_builds_expected_docker_commands(tmp_path: Path) -> None:
    runner = FakeRunner(
        [
            _result(["docker"], stdout="[]"),
            _result(["docker"], stdout="container-123\n"),
            _result(["docker"]),
            _result(["docker"]),
            _result(["docker"]),
        ]
    )
    client = DockerClient(timeout=12.0, runner=runner)
    install_script = "apt-get update\napt-get install -y libstdc++6"

    client.export_runtime_rootfs(
        "ubuntu:22.04",
        tmp_path / "rootfs.tar",
        install_script,
        platform="linux/amd64",
    )

    assert runner.commands == [
        ["docker", "image", "inspect", "ubuntu:22.04"],
        [
            "docker",
            "create",
            "--platform",
            "linux/amd64",
            "ubuntu:22.04",
            "sh",
            "-c",
            install_script,
        ],
        ["docker", "start", "--attach", "container-123"],
        ["docker", "export", "container-123", "--output", str(tmp_path / "rootfs.tar")],
        ["docker", "rm", "-f", "container-123"],
    ]


def test_export_runtime_rootfs_pulls_when_requested(tmp_path: Path) -> None:
    runner = FakeRunner(
        [
            _result(["docker"], stdout="pulled"),
            _result(["docker"], stdout="container-123\n"),
            _result(["docker"]),
            _result(["docker"]),
            _result(["docker"]),
        ]
    )
    client = DockerClient(runner=runner)

    client.export_runtime_rootfs(
        "ubuntu:22.04",
        tmp_path / "rootfs.tar",
        "true",
        pull=True,
        platform="linux/amd64",
    )

    assert runner.commands[0] == [
        "docker",
        "pull",
        "--platform",
        "linux/amd64",
        "ubuntu:22.04",
    ]


def test_export_runtime_rootfs_removes_container_when_install_fails(tmp_path: Path) -> None:
    runner = FakeRunner(
        [
            _result(["docker"], stdout="[]"),
            _result(["docker"], stdout="container-123\n"),
            _result(["docker"], returncode=1, stderr="install failed"),
            _result(["docker"]),
        ]
    )
    client = DockerClient(runner=runner)

    with pytest.raises(DockerError, match="Package installation failed"):
        client.export_runtime_rootfs("ubuntu:22.04", tmp_path / "rootfs.tar", "false")

    assert runner.commands[-1] == ["docker", "rm", "-f", "container-123"]


def test_missing_docker_raises_clear_error(tmp_path: Path) -> None:
    runner = FakeRunner(
        [
            _result(
                ["docker"],
                returncode=127,
                stderr="docker command not found",
            )
        ]
    )
    client = DockerClient(runner=runner)

    with pytest.raises(DockerError, match="Docker is not available"):
        client.export_image_rootfs("ubuntu:22.04", tmp_path / "rootfs.tar")


def test_missing_image_raises_clear_error(tmp_path: Path) -> None:
    runner = FakeRunner(
        [
            _result(
                ["docker"],
                returncode=1,
                stderr="No such image: ubuntu:22.04",
            )
        ]
    )
    client = DockerClient(runner=runner)

    with pytest.raises(DockerError, match="not available locally"):
        client.export_image_rootfs("ubuntu:22.04", tmp_path / "rootfs.tar")
