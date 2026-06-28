from pydantic import BaseModel, Field


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
