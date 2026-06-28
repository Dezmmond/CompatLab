from pydantic import BaseModel, Field


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
