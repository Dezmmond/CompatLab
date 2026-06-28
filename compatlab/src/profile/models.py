from pydantic import BaseModel, Field


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
