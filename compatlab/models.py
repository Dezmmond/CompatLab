from enum import Enum
from pydantic import BaseModel, Field
from typing import Literal


Severity = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]


class DiagnosticSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class DiagnosticCategory(str, Enum):
    ARTIFACT = "artifact"
    TARGET = "target"
    BUNDLE = "bundle"
    SYMBOLS = "symbols"
    LOADER = "loader"
    RPATH = "rpath"
    LIMITS = "limits"
    PACKAGE = "package"


class DiagnosticIssue(BaseModel):
    code: str
    severity: DiagnosticSeverity
    category: DiagnosticCategory
    title: str
    message: str
    affected_path: str | None = None
    dependency_name: str | None = None
    dependency_chain: list[str] = Field(default_factory=list)
    required: str | None = None
    provided: str | None = None
    hint: str | None = None


class DiagnosticSummary(BaseModel):
    status: str = "passed"
    errors: int = 0
    warnings: int = 0
    infos: int = 0
    issue_codes: dict[str, int] = Field(default_factory=dict)


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


class SymbolVersion(BaseModel):
    namespace: str
    version: str
    raw: str


class ElfInfo(BaseModel):
    elf_class: str | None = None
    endianness: str | None = None
    os_abi: str | None = None
    machine: str | None = None
    elf_type: str | None = None
    entry_point: str | None = None
    interpreter: str | None = None
    is_dynamic: bool | None = None
    needed: list[str] = Field(default_factory=list)
    rpath: list[str] = Field(default_factory=list)
    runpath: list[str] = Field(default_factory=list)
    required_versions: list[SymbolVersion] = Field(default_factory=list)


class Problem(BaseModel):
    id: str
    severity: Severity
    title: str
    details: str
    artifact_path: str | None = None
    evidence: dict[str, str] = Field(default_factory=dict)
    suggestions: list[str] = Field(default_factory=list)


class OsReleaseFacts(BaseModel):
    id: str | None = None
    name: str | None = None
    version_id: str | None = None
    pretty_name: str | None = None


class LibraryFact(BaseModel):
    soname: str
    path: str | None = None
    arch: str | None = None


class SymbolVersionFacts(BaseModel):
    glibc: list[str] = Field(default_factory=list)
    glibcxx: list[str] = Field(default_factory=list)
    cxxabi: list[str] = Field(default_factory=list)


class FactWarning(BaseModel):
    code: str
    message: str
    source: str | None = None


class SystemFacts(BaseModel):
    os_release: OsReleaseFacts = Field(default_factory=OsReleaseFacts)
    architecture: str | None = None
    glibc_version: str | None = None
    source_image: str | None = None
    source_image_id: str | None = None
    platform: str | None = None
    runtime_preset: str | None = None
    runtime_packages: list[str] | None = None
    package_manager: str | None = None
    dynamic_linkers: list[str] = Field(default_factory=list)
    library_paths: list[str] = Field(default_factory=list)
    libraries: list[LibraryFact] = Field(default_factory=list)
    symbol_versions: SymbolVersionFacts = Field(default_factory=SymbolVersionFacts)
    detected_by: list[str] = Field(default_factory=list)
    warnings: list[FactWarning] = Field(default_factory=list)


class ProfileMetadata(BaseModel):
    generated_by: str | None = None
    generated_at: str | None = None
    source: str | None = None
    source_image: str | None = None
    source_image_id: str | None = None
    source_os_id: str | None = None
    source_os_version_id: str | None = None
    detection_backend: str | None = None
    platform: str | None = None
    runtime_preset: str | None = None
    runtime_packages: list[str] | None = None
    package_manager: str | None = None


class LibcProfile(BaseModel):
    family: str
    version: str


class LibstdcxxProfile(BaseModel):
    max_glibcxx: str | None = None
    max_cxxabi: str | None = None


class ProvidedLibrary(BaseModel):
    soname: str


class TargetProfile(BaseModel):
    id: str
    name: str
    arch: str
    libc: LibcProfile
    libstdcxx: LibstdcxxProfile | None = None
    interpreters: list[str] = Field(default_factory=list)
    provided_libraries: list[ProvidedLibrary] = Field(default_factory=list)
    metadata: ProfileMetadata | None = None
    notes: str | None = None


class ArtifactInfo(BaseModel):
    path: str
    kind: str
    size_bytes: int | None = None
    sha256: str | None = None


class PackageMetadata(BaseModel):
    type: str
    name: str | None = None
    epoch: int | None = None
    version: str | None = None
    release: str | None = None
    architecture: str | None = None
    summary: str | None = None
    license: str | None = None
    vendor: str | None = None
    group: str | None = None
    build_time: int | None = None
    source_rpm: str | None = None
    payload_file_count: int | None = None
    native_entry_count: int | None = None
    root_is_purelib: bool | None = None
    tags: list[str] = Field(default_factory=list)
    generator: str | None = None
    build: str | None = None
    dist_info_dir: str | None = None


class PackageEntry(BaseModel):
    path: str
    kind: str = "elf"
    size: int | None = None
    elf: ElfInfo | None = None
    diagnostics: list[DiagnosticIssue] = Field(default_factory=list)
    summary: DiagnosticSummary = Field(default_factory=DiagnosticSummary)
    problems: list[Problem] = Field(default_factory=list)
    warnings: list[Problem] = Field(default_factory=list)


class ArtifactReport(BaseModel):
    schema_version: str = "0.1"
    tool: str = "compatlab"
    artifact: ArtifactInfo
    elf: ElfInfo | None = None
    package: PackageMetadata | None = None
    entries: list[PackageEntry] = Field(default_factory=list)
    native_entries: list[PackageEntry] = Field(default_factory=list)
    target: TargetProfile | None = None
    summary: DiagnosticSummary = Field(default_factory=DiagnosticSummary)
    diagnostics: list[DiagnosticIssue] = Field(default_factory=list)
    dependency_graph: DependencyGraph | None = None
    problems: list[Problem] = Field(default_factory=list)
    warnings: list[Problem] = Field(default_factory=list)

    @property
    def is_compatible(self) -> bool:
        return not any(problem.severity in {"CRITICAL", "HIGH"} for problem in self.problems)
