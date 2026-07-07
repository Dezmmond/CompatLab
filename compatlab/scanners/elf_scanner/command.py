import os
import subprocess

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str


def run_command(command: list[str], timeout: float = 5.0) -> CommandResult:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            env={**os.environ, "LC_ALL": "C", "LANG": "C"},
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return CommandResult(
            args=command,
            returncode=127,
            stdout="",
            stderr=f"{command[0]} command not found",
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            args=command,
            returncode=124,
            stdout=exc.stdout or "",
            stderr=f"{command[0]} command timed out after {timeout:g}s",
        )

    return CommandResult(
        args=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def run_readelf(args: list[str], path: Path, timeout: float = 5.0) -> CommandResult:
    command = ["readelf", *args, str(path)]
    return run_command(command, timeout=timeout)
