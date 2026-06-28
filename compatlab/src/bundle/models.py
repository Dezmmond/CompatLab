from enum import Enum

from pydantic import BaseModel, Field


class DependencyResolutionKind(str, Enum):
    BUNDLED = "bundled"
    TARGET = "target"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"
    INCOMPATIBLE = "incompatible"


class DependencyNode(BaseModel):
    artifact_id: str
    path: str | None = None
    soname: str | None = None
    needed_libraries: list[str] = Field(default_factory=list)
    rpath: list[str] = Field(default_factory=list)
    runpath: list[str] = Field(default_factory=list)
    required_glibc_versions: list[str] = Field(default_factory=list)
    required_glibcxx_versions: list[str] = Field(default_factory=list)
    required_cxxabi_versions: list[str] = Field(default_factory=list)


class DependencyEdge(BaseModel):
    from_artifact_id: str
    needed_name: str
    resolution_kind: DependencyResolutionKind
    resolved_artifact_id: str | None = None
    resolved_path: str | None = None
    candidates: list[str] = Field(default_factory=list)
    message: str | None = None


class DependencyGraph(BaseModel):
    entrypoint_artifact_id: str
    nodes: list[DependencyNode] = Field(default_factory=list)
    edges: list[DependencyEdge] = Field(default_factory=list)
    unresolved_dependencies: list[DependencyEdge] = Field(default_factory=list)
