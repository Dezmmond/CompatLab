from pathlib import Path

from compatlab.src.report.models import ArtifactInfo


def detect_artifact(path: Path) -> ArtifactInfo:
    stat = path.stat()
    return ArtifactInfo(path=str(path), kind="linux-artifact", size_bytes=stat.st_size)
