"""Runtime package presets used when probing container images."""

from pydantic import BaseModel, Field

from compatlab.models import OsReleaseFacts
from compatlab.profile.rootfs import parse_os_release_from_tar, path_exists


SUPPORTED_PACKAGE_MANAGERS = ("apt-get", "dnf", "yum")
PACKAGE_MANAGER_PATHS = {
    "apt-get": ("/usr/bin/apt-get", "/bin/apt-get"),
    "dnf": ("/usr/bin/dnf", "/bin/dnf"),
    "yum": ("/usr/bin/yum", "/bin/yum"),
}
PACKAGE_MANAGER_BY_OS_ID = {
    "ubuntu": "apt-get",
    "debian": "apt-get",
    "rocky": "dnf",
    "rhel": "dnf",
    "fedora": "dnf",
    "sberlinux": "dnf",
    "centos": "yum",
}


class RuntimePresetError(ValueError):
    pass


class RuntimePreset(BaseModel):
    name: str
    description: str
    packages_by_manager: dict[str, list[str]]
    supported_package_managers: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


_RUNTIME_PRESETS = {
    "cpp-runtime": RuntimePreset(
        name="cpp-runtime",
        description="Common C/C++ runtime libraries",
        packages_by_manager={
            "apt-get": ["libstdc++6", "libgcc-s1"],
            "dnf": ["libstdc++", "libgcc"],
            "yum": ["libstdc++", "libgcc"],
        },
        supported_package_managers=["apt-get", "dnf", "yum"],
        limitations=["Does not install compiler toolchains or development headers."],
    ),
    "python-runtime": RuntimePreset(
        name="python-runtime",
        description="Common Python 3 runtime libraries",
        packages_by_manager={
            "apt-get": ["python3", "libpython3-stdlib"],
            "dnf": ["python3", "python3-libs"],
            "yum": ["python3", "python3-libs"],
        },
        supported_package_managers=["apt-get", "dnf", "yum"],
        limitations=["Does not install Python build dependencies or project packages."],
    ),
}


def list_runtime_presets() -> list[RuntimePreset]:
    return [_RUNTIME_PRESETS[name] for name in sorted(_RUNTIME_PRESETS)]


def get_runtime_preset(name: str) -> RuntimePreset:
    try:
        return _RUNTIME_PRESETS[name]
    except KeyError as exc:
        available = ", ".join(sorted(_RUNTIME_PRESETS))
        raise RuntimePresetError(
            f"Unknown runtime preset '{name}'. Available presets: {available}."
        ) from exc


def packages_for_manager(preset: RuntimePreset, package_manager: str) -> list[str]:
    packages = preset.packages_by_manager.get(package_manager)
    if packages is None:
        raise RuntimePresetError(
            f"Runtime preset '{preset.name}' is not supported for package manager "
            f"'{package_manager}'."
        )
    return list(packages)


def detect_package_manager(
    os_release: OsReleaseFacts, available_paths: set[str] | None = None
) -> str:
    if available_paths:
        for manager in SUPPORTED_PACKAGE_MANAGERS:
            if any(path in available_paths for path in PACKAGE_MANAGER_PATHS[manager]):
                return manager

    if os_release.id is not None:
        manager = PACKAGE_MANAGER_BY_OS_ID.get(os_release.id.lower())
        if manager is not None:
            return manager

    raise RuntimePresetError(
        "Could not detect a supported package manager. Supported package managers: "
        f"{', '.join(SUPPORTED_PACKAGE_MANAGERS)}."
    )


def detect_package_manager_from_rootfs(tar_path: str) -> str:
    available_paths = {
        path
        for paths in PACKAGE_MANAGER_PATHS.values()
        for path in paths
        if path_exists(tar_path, path)
    }
    return detect_package_manager(parse_os_release_from_tar(tar_path), available_paths)


def build_install_script(package_manager: str, packages: list[str]) -> str:
    if package_manager not in SUPPORTED_PACKAGE_MANAGERS:
        supported = ", ".join(SUPPORTED_PACKAGE_MANAGERS)
        raise RuntimePresetError(
            f"Unsupported package manager '{package_manager}'. Supported package managers: "
            f"{supported}."
        )
    if not packages:
        raise RuntimePresetError("Runtime preset package list must not be empty.")

    package_args = " ".join(packages)
    if package_manager == "apt-get":
        return "\n".join(
            [
                "export DEBIAN_FRONTEND=noninteractive",
                "apt-get update",
                f"apt-get install -y --no-install-recommends {package_args}",
                "rm -rf /var/lib/apt/lists/*",
            ]
        )
    if package_manager == "dnf":
        return "\n".join(
            [
                f"dnf install -y --setopt=install_weak_deps=False {package_args}",
                "dnf clean all",
            ]
        )
    return "\n".join(
        [
            f"yum install -y {package_args}",
            "yum clean all",
        ]
    )
