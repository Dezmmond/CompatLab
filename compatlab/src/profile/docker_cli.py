from collections.abc import Callable
from dataclasses import dataclass
import json
from pathlib import Path

from compatlab.src.elfscan.command import CommandResult, run_command


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

    def create_container(self, image: str, platform: str | None = None) -> str:
        command = ["docker", "create"]
        if platform is not None:
            command.extend(["--platform", platform])
        command.append(image)
        result = self.runner(command, self.timeout)
        container_id = _require_success(result, f"Docker container create failed for '{image}'.")
        return container_id.strip()

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
