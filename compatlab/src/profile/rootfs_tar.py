from dataclasses import dataclass
from pathlib import PurePosixPath
import shutil
import tarfile

from compatlab.src.profile.linkers import KNOWN_DYNAMIC_LINKERS
from compatlab.src.profile.models import LibraryFact, OsReleaseFacts
from compatlab.src.profile.os_release import parse_os_release


COMMON_LIBRARY_DIRS = (
    "lib",
    "lib64",
    "usr/lib",
    "usr/lib64",
)

CANDIDATE_SYMBOL_LIBRARIES = ("libc.so.6", "libstdc++.so.6")


@dataclass(frozen=True)
class RootfsLibraryCandidate:
    soname: str
    path: str


def read_text_file(tar_path: str, path: str) -> str | None:
    normalized = _normalize_path(path)
    with tarfile.open(tar_path) as archive:
        member = _find_member(archive, normalized)
        if member is None or not member.isfile():
            return None
        extracted = archive.extractfile(member)
        if extracted is None:
            return None
        return extracted.read().decode("utf-8", errors="replace")


def path_exists(tar_path: str, path: str) -> bool:
    normalized = _normalize_path(path)
    with tarfile.open(tar_path) as archive:
        return _find_member(archive, normalized) is not None


def parse_os_release_from_tar(tar_path: str) -> OsReleaseFacts:
    return parse_os_release(read_text_file(tar_path, "/etc/os-release") or "")


def list_libraries(tar_path: str) -> list[LibraryFact]:
    libraries: dict[str, LibraryFact] = {}
    with tarfile.open(tar_path) as archive:
        for member in archive.getmembers():
            path = _normalize_path(member.name)
            if not _is_library_entry(path, member):
                continue
            soname = PurePosixPath(path).name
            libraries.setdefault(soname, LibraryFact(soname=soname, path=f"/{path}"))
    return [libraries[soname] for soname in sorted(libraries)]


def detect_dynamic_linkers_in_tar(tar_path: str) -> list[str]:
    candidates = {_normalize_path(path) for path in KNOWN_DYNAMIC_LINKERS}
    found: list[str] = []
    with tarfile.open(tar_path) as archive:
        for member in archive.getmembers():
            path = _normalize_path(member.name)
            if path in candidates and (member.isfile() or member.issym() or member.islnk()):
                found.append(f"/{path}")
    return sorted(set(found))


def list_symbol_library_candidates(tar_path: str) -> list[RootfsLibraryCandidate]:
    candidates: dict[str, RootfsLibraryCandidate] = {}
    with tarfile.open(tar_path) as archive:
        for member in archive.getmembers():
            path = _normalize_path(member.name)
            soname = PurePosixPath(path).name
            if soname not in CANDIDATE_SYMBOL_LIBRARIES:
                continue
            if not _is_library_entry(path, member):
                continue
            candidates.setdefault(soname, RootfsLibraryCandidate(soname=soname, path=f"/{path}"))
    return [candidates[soname] for soname in sorted(candidates)]


def extract_member_to_directory(tar_path: str, member_path: str, output_dir: str) -> str | None:
    normalized = _normalize_path(member_path)
    with tarfile.open(tar_path) as archive:
        member = _find_member(archive, normalized)
        if member is None:
            return None
        if member.issym() or member.islnk():
            member = _resolve_link_member(archive, member)
            if member is None:
                return None
        if not member.isfile():
            return None
        extracted = archive.extractfile(member)
        if extracted is None:
            return None

        output_path = PurePosixPath(normalized).name
        destination = f"{output_dir}/{output_path}"
        with open(destination, "wb") as stream:
            shutil.copyfileobj(extracted, stream)
        return destination


def _find_member(archive: tarfile.TarFile, path: str) -> tarfile.TarInfo | None:
    members = {_normalize_path(member.name): member for member in archive.getmembers()}
    return members.get(path)


def _resolve_link_member(
    archive: tarfile.TarFile, member: tarfile.TarInfo
) -> tarfile.TarInfo | None:
    if member.issym():
        target = _resolve_symlink_path(_normalize_path(member.name), member.linkname)
    else:
        target = _normalize_path(member.linkname)
    return _find_member(archive, target)


def _resolve_symlink_path(member_path: str, linkname: str) -> str:
    if linkname.startswith("/"):
        return _normalize_path(linkname)
    parent = PurePosixPath(member_path).parent
    return _normalize_path(str(parent / linkname))


def _is_library_entry(path: str, member: tarfile.TarInfo) -> bool:
    if not (member.isfile() or member.issym() or member.islnk()):
        return False
    if not _is_common_library_path(path):
        return False
    name = PurePosixPath(path).name
    return ".so" in name


def _is_common_library_path(path: str) -> bool:
    return any(
        path == directory or path.startswith(f"{directory}/") for directory in COMMON_LIBRARY_DIRS
    )


def _normalize_path(path: str) -> str:
    return str(PurePosixPath(path.lstrip("/")))
