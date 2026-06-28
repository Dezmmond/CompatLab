from pydantic import BaseModel, Field

from compatlab.src.bundle.models import DependencyGraph
from compatlab.src.elfscan.models import ElfInfo
from compatlab.src.problem.models import Problem
from compatlab.src.profile.models import TargetProfile


class ArtifactInfo(BaseModel):
    path: str
    kind: str
    size_bytes: int | None = None
    sha256: str | None = None


class ArtifactReport(BaseModel):
    schema_version: str = "0.1"
    tool: str = "compatlab"
    artifact: ArtifactInfo
    elf: ElfInfo | None = None
    target: TargetProfile | None = None
    dependency_graph: DependencyGraph | None = None
    problems: list[Problem] = Field(default_factory=list)
    warnings: list[Problem] = Field(default_factory=list)

    @property
    def is_compatible(self) -> bool:
        return not any(problem.severity in {"CRITICAL", "HIGH"} for problem in self.problems)
