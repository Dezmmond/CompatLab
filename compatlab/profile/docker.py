"""Detect system facts from Docker images and exported rootfs tarballs."""

import json

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from compatlab.compare.engine import normalize_architecture, parse_version_tuple
from compatlab.elfscan.command import CommandResult, run_command, run_readelf
from compatlab.elfscan.parsers import parse_version_info
from compatlab.models import FactWarning, SymbolVersionFacts, SystemFacts
from compatlab.profile.rootfs import (
    detect_dynamic_linkers_in_tar,
    extract_member_to_directory,
    list_libraries,
    list_symbol_library_candidates,
    parse_os_release_from_tar,
)
from compatlab.profile.runtimes import (
    build_install_script,
    detect_package_manager_from_rootfs,
    get_runtime_preset,
    packages_for_manager,
)


class DockerError(RuntimeError):
    pass


CommandRunner = Callable[[list[str], float], CommandResult]


@dataclass(frozen=True)
class DockerImageMetadata:
    image: str
    image_id: str | None = None
    architecture: str | None = None
    os: str | None = None
    repo_digests: list[str] | None = None


@dataclass(frozen=True)
class DockerClient:
    timeout: float = 30.0
    runner: CommandRunner = run_command

    def inspect_image(self, image: str) -> str:
        result = self.runner(["docker", "image", "inspect", image], self.timeout)
        return _require_success(result, f"Docker image '{image}' is not available locally.")

    def inspect_image_metadata(self, image: str) -> DockerImageMetadata:
        return parse_image_inspect(image, self.inspect_image(image))

    def pull_image(self, image: str, platform: str | None = None) -> str:
        command = ["docker", "pull"]
        if platform is not None:
            command.extend(["--platform", platform])
        command.append(image)
        result = self.runner(command, self.timeout)
        return _require_success(result, f"Docker image pull failed for '{image}'.")

    def create_container(
        self,
        image: str,
        platform: str | None = None,
        command_args: list[str] | None = None,
    ) -> str:
        command = ["docker", "create"]
        if platform is not None:
            command.extend(["--platform", platform])
        command.append(image)
        if command_args is not None:
            command.extend(command_args)
        result = self.runner(command, self.timeout)
        container_id = _require_success(result, f"Docker container create failed for '{image}'.")
        return container_id.strip()

    def start_container_attached(self, container_id: str) -> None:
        result = self.runner(["docker", "start", "--attach", container_id], self.timeout)
        _require_success(
            result,
            f"Package installation failed in temporary container '{container_id}'.",
        )

    def export_container(self, container_id: str, output: Path) -> None:
        result = self.runner(
            ["docker", "export", container_id, "--output", str(output)],
            self.timeout,
        )
        _require_success(result, f"Docker export failed for container '{container_id}'.")

    def remove_container(self, container_id: str) -> None:
        result = self.runner(["docker", "rm", "-f", container_id], self.timeout)
        _require_success(result, f"Docker container cleanup failed for '{container_id}'.")

    def export_image_rootfs(
        self,
        image: str,
        output: Path,
        *,
        platform: str | None = None,
        pull: bool = False,
    ) -> None:
        if pull:
            self.pull_image(image, platform=platform)
        else:
            self.inspect_image(image)

        container_id = self.create_container(image, platform=platform)
        try:
            self.export_container(container_id, output)
        finally:
            self.remove_container(container_id)

    def export_runtime_rootfs(
        self,
        image: str,
        output: Path,
        install_script: str,
        *,
        platform: str | None = None,
        pull: bool = False,
    ) -> None:
        if pull:
            self.pull_image(image, platform=platform)
        else:
            self.inspect_image(image)

        container_id = self.create_container(
            image,
            platform=platform,
            command_args=["sh", "-c", install_script],
        )
        try:
            self.start_container_attached(container_id)
            self.export_container(container_id, output)
        finally:
            self.remove_container(container_id)


def detect_docker_image_system(
    image: str,
    *,
    platform: str | None = None,
    pull: bool = False,
    runtime_preset: str | None = None,
    timeout: float = 30.0,
    client: DockerClient | None = None,
) -> SystemFacts:
    docker = client or DockerClient(timeout=timeout)
    metadata = docker.inspect_image_metadata(image)
    with TemporaryDirectory(prefix="compatlab-rootfs-") as temp_dir:
        rootfs = Path(temp_dir) / "rootfs.tar"
        runtime_packages: list[str] = []
        package_manager: str | None = None

        if runtime_preset is None:
            docker.export_image_rootfs(image, rootfs, platform=platform, pull=pull)
        else:
            base_rootfs = Path(temp_dir) / "base-rootfs.tar"
            docker.export_image_rootfs(image, base_rootfs, platform=platform, pull=pull)
            preset = get_runtime_preset(runtime_preset)
            package_manager = detect_package_manager_from_rootfs(str(base_rootfs))
            runtime_packages = packages_for_manager(preset, package_manager)
            install_script = build_install_script(package_manager, runtime_packages)
            docker.export_runtime_rootfs(
                image,
                rootfs,
                install_script,
                platform=platform,
            )

        return system_facts_from_rootfs_tar(
            rootfs,
            image=image,
            metadata=metadata,
            platform=platform,
            runtime_preset=runtime_preset,
            runtime_packages=runtime_packages,
            package_manager=package_manager,
        )


def system_facts_from_rootfs_tar(
    rootfs: Path,
    *,
    image: str,
    metadata: DockerImageMetadata,
    platform: str | None = None,
    runtime_preset: str | None = None,
    runtime_packages: list[str] | None = None,
    package_manager: str | None = None,
) -> SystemFacts:
    warnings: list[FactWarning] = []
    libraries = list_libraries(str(rootfs))
    dynamic_linkers = detect_dynamic_linkers_in_tar(str(rootfs))
    symbol_versions = _detect_symbol_versions_from_rootfs(rootfs, warnings)

    return SystemFacts(
        os_release=parse_os_release_from_tar(str(rootfs)),
        architecture=normalize_architecture(metadata.architecture),
        source_image=image,
        source_image_id=metadata.image_id,
        platform=platform,
        runtime_preset=runtime_preset,
        runtime_packages=runtime_packages or [],
        package_manager=package_manager,
        dynamic_linkers=dynamic_linkers,
        library_paths=sorted({library.path for library in libraries if library.path is not None}),
        libraries=libraries,
        symbol_versions=symbol_versions,
        detected_by=_detected_by(runtime_preset),
        warnings=warnings,
    )


def _detected_by(runtime_preset: str | None) -> list[str]:
    if runtime_preset is None:
        return ["docker image inspect", "docker export", "rootfs tar parser"]
    return [
        "docker image inspect",
        "docker export",
        "runtime preset install",
        "rootfs tar parser",
    ]


def _detect_symbol_versions_from_rootfs(
    rootfs: Path,
    warnings: list[FactWarning],
) -> SymbolVersionFacts:
    candidates = list_symbol_library_candidates(str(rootfs))
    grouped: dict[str, list[str]] = {}
    with TemporaryDirectory(prefix="compatlab-libs-") as temp_dir:
        for candidate in candidates:
            extracted = extract_member_to_directory(str(rootfs), candidate.path, temp_dir)
            if extracted is None:
                warnings.append(
                    FactWarning(
                        code="rootfs.library_extract_failed",
                        message=f"Could not extract {candidate.path} from rootfs.",
                        source=candidate.path,
                    )
                )
                continue
            result = run_readelf(["--version-info"], Path(extracted))
            if result.returncode != 0:
                warnings.append(_command_warning(candidate.path, result))
                continue
            for version in parse_version_info(result.stdout):
                grouped.setdefault(version.namespace, []).append(version.version)

    return SymbolVersionFacts(
        glibc=_sorted_unique_versions(grouped.get("GLIBC", [])),
        glibcxx=_sorted_unique_versions(grouped.get("GLIBCXX", [])),
        cxxabi=_sorted_unique_versions(grouped.get("CXXABI", [])),
    )


def _sorted_unique_versions(versions: list[str]) -> list[str]:
    return sorted(set(versions), key=parse_version_tuple)


def _command_warning(path: str, result: CommandResult) -> FactWarning:
    details = result.stderr.strip() or f"exit code {result.returncode}"
    return FactWarning(
        code="rootfs.readelf_failed",
        message=f"readelf --version-info failed for {path}: {details}",
        source=path,
    )


def _require_success(result: CommandResult, message: str) -> str:
    if result.returncode == 0:
        return result.stdout
    details = result.stderr.strip() or result.stdout.strip()
    if result.returncode == 127:
        raise DockerError("Docker is not available. Install Docker or run on a host with Docker.")
    if details:
        raise DockerError(f"{message} {details}")
    raise DockerError(message)


def parse_image_inspect(image: str, output: str) -> DockerImageMetadata:
    try:
        raw = json.loads(output)
    except json.JSONDecodeError as exc:
        raise DockerError(f"Docker image inspect returned invalid JSON for '{image}'.") from exc
    if not isinstance(raw, list) or not raw or not isinstance(raw[0], dict):
        raise DockerError(f"Docker image inspect returned no metadata for '{image}'.")
    item = raw[0]
    repo_digests = item.get("RepoDigests")
    if not isinstance(repo_digests, list):
        repo_digests = []
    return DockerImageMetadata(
        image=image,
        image_id=_string_or_none(item.get("Id")),
        architecture=_string_or_none(item.get("Architecture")),
        os=_string_or_none(item.get("Os")),
        repo_digests=[digest for digest in repo_digests if isinstance(digest, str)],
    )


def _string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None
