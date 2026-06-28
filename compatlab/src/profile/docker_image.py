from pathlib import Path
from tempfile import TemporaryDirectory

from compatlab.src.compare.engine import normalize_architecture, parse_version_tuple
from compatlab.src.elfscan.command import CommandResult, run_readelf
from compatlab.src.elfscan.parsers import parse_version_info
from compatlab.src.profile.docker_cli import DockerClient, DockerImageMetadata
from compatlab.src.profile.models import FactWarning, SymbolVersionFacts, SystemFacts
from compatlab.src.profile.rootfs_tar import (
    detect_dynamic_linkers_in_tar,
    extract_member_to_directory,
    list_libraries,
    list_symbol_library_candidates,
    parse_os_release_from_tar,
)


def detect_docker_image_system(
    image: str,
    *,
    platform: str | None = None,
    pull: bool = False,
    timeout: float = 30.0,
    client: DockerClient | None = None,
) -> SystemFacts:
    docker = client or DockerClient(timeout=timeout)
    metadata = docker.inspect_image_metadata(image)
    with TemporaryDirectory(prefix="compatlab-rootfs-") as temp_dir:
        rootfs = Path(temp_dir) / "rootfs.tar"
        docker.export_image_rootfs(image, rootfs, platform=platform, pull=pull)
        return system_facts_from_rootfs_tar(
            rootfs,
            image=image,
            metadata=metadata,
            platform=platform,
        )


def system_facts_from_rootfs_tar(
    rootfs: Path,
    *,
    image: str,
    metadata: DockerImageMetadata,
    platform: str | None = None,
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
        dynamic_linkers=dynamic_linkers,
        library_paths=sorted({library.path for library in libraries if library.path is not None}),
        libraries=libraries,
        symbol_versions=symbol_versions,
        detected_by=["docker image inspect", "docker export", "rootfs tar parser"],
        warnings=warnings,
    )


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
