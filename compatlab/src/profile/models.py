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
    notes: str | None = None
