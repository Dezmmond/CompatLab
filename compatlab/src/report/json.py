from pathlib import Path

from compatlab.src.report.models import ArtifactReport


def write_json_report(report: ArtifactReport, path: Path) -> None:
    path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
