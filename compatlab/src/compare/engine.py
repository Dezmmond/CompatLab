from compatlab.src.profile.models import TargetProfile
from compatlab.src.report.models import ArtifactReport


def compare_report(report: ArtifactReport, target: TargetProfile) -> ArtifactReport:
    return report.model_copy(update={"target": target})
