from pathlib import Path

from compatlab.src.artifact.detect import detect_artifact
from compatlab.src.elfscan.models import ElfInfo
from compatlab.src.report.models import ArtifactReport


def scan_path(path: Path) -> ArtifactReport:
    artifact = detect_artifact(path)
    # Placeholder for the future readelf backend. The report schema is stable enough
    # for CLI and comparison plumbing while real extraction is added next.
    elf = ElfInfo(elf_class=None, machine=None, elf_type=None, is_dynamic=None)
    return ArtifactReport(artifact=artifact, elf=elf)
