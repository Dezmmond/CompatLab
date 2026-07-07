from enum import Enum
from pathlib import Path

from compatlab.models import ArtifactInfo


class ArtifactKind(str, Enum):
    ELF = "elf"
    WHEEL = "wheel"
    RPM = "rpm"
    UNKNOWN = "unknown"


def detect_artifact_kind(path: Path) -> ArtifactKind:
    try:
        with path.open("rb") as handle:
            magic = handle.read(4)
    except OSError:
        return ArtifactKind.UNKNOWN

    if magic == b"\x7fELF":
        return ArtifactKind.ELF

    if path.suffix == ".whl":
        return ArtifactKind.WHEEL

    if magic == b"\xed\xab\xee\xdb" or path.suffix == ".rpm":
        return ArtifactKind.RPM

    return ArtifactKind.UNKNOWN


def detect_artifact(path: Path) -> ArtifactInfo:
    stat = path.stat()
    return ArtifactInfo(path=str(path), kind="linux-artifact", size_bytes=stat.st_size)
