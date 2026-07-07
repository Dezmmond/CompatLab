from enum import Enum
from pathlib import Path

from compatlab.models import ArtifactInfo


class ArtifactKind(str, Enum):
    ELF = "elf"
    WHEEL = "wheel"
    UNKNOWN = "unknown"


def detect_artifact_kind(path: Path) -> ArtifactKind:
    if path.suffix == ".whl":
        return ArtifactKind.WHEEL
    try:
        with path.open("rb") as handle:
            if handle.read(4) == b"\x7fELF":
                return ArtifactKind.ELF
    except OSError:
        return ArtifactKind.UNKNOWN
    return ArtifactKind.UNKNOWN


def detect_artifact(path: Path) -> ArtifactInfo:
    stat = path.stat()
    return ArtifactInfo(path=str(path), kind="linux-artifact", size_bytes=stat.st_size)
