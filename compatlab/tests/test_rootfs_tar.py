import tarfile
from io import BytesIO
from pathlib import Path

from compatlab.profile.rootfs import (
    detect_dynamic_linkers_in_tar,
    extract_member_to_directory,
    list_libraries,
    list_symbol_library_candidates,
    parse_os_release_from_tar,
    path_exists,
    read_text_file,
)


def _write_rootfs_tar(path: Path) -> None:
    with tarfile.open(path, "w") as archive:
        _add_file(
            archive,
            "etc/os-release",
            b'ID=ubuntu\nVERSION_ID="22.04"\nPRETTY_NAME="Ubuntu 22.04 LTS"\n',
        )
        _add_file(archive, "lib/x86_64-linux-gnu/libc-2.35.so", b"libc")
        _add_symlink(
            archive,
            "lib/x86_64-linux-gnu/libc.so.6",
            "libc-2.35.so",
        )
        _add_file(archive, "usr/lib/x86_64-linux-gnu/libstdc++.so.6", b"libstdc++")
        _add_file(archive, "lib64/ld-linux-x86-64.so.2", b"loader")
        _add_file(archive, "opt/app/libignored.so", b"ignored")


def _add_file(archive: tarfile.TarFile, name: str, content: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(content)
    archive.addfile(info, BytesIO(content))


def _add_symlink(archive: tarfile.TarFile, name: str, target: str) -> None:
    info = tarfile.TarInfo(name)
    info.type = tarfile.SYMTYPE
    info.linkname = target
    archive.addfile(info)


def test_read_text_file_reads_normalized_path(tmp_path: Path) -> None:
    rootfs = tmp_path / "rootfs.tar"
    _write_rootfs_tar(rootfs)

    content = read_text_file(str(rootfs), "/etc/os-release")

    assert content is not None
    assert "Ubuntu 22.04 LTS" in content


def test_path_exists_checks_normalized_path(tmp_path: Path) -> None:
    rootfs = tmp_path / "rootfs.tar"
    _write_rootfs_tar(rootfs)

    assert path_exists(str(rootfs), "/etc/os-release") is True
    assert path_exists(str(rootfs), "/usr/bin/apt-get") is False


def test_parse_os_release_from_tar_extracts_os_facts(tmp_path: Path) -> None:
    rootfs = tmp_path / "rootfs.tar"
    _write_rootfs_tar(rootfs)

    facts = parse_os_release_from_tar(str(rootfs))

    assert facts.id == "ubuntu"
    assert facts.version_id == "22.04"
    assert facts.pretty_name == "Ubuntu 22.04 LTS"


def test_list_libraries_returns_common_library_basenames(tmp_path: Path) -> None:
    rootfs = tmp_path / "rootfs.tar"
    _write_rootfs_tar(rootfs)

    libraries = list_libraries(str(rootfs))

    assert [library.soname for library in libraries] == [
        "ld-linux-x86-64.so.2",
        "libc-2.35.so",
        "libc.so.6",
        "libstdc++.so.6",
    ]
    assert all(not library.path.startswith("/opt") for library in libraries if library.path)


def test_detect_dynamic_linkers_in_tar_uses_known_paths(tmp_path: Path) -> None:
    rootfs = tmp_path / "rootfs.tar"
    _write_rootfs_tar(rootfs)

    assert detect_dynamic_linkers_in_tar(str(rootfs)) == ["/lib64/ld-linux-x86-64.so.2"]


def test_list_symbol_library_candidates_finds_libc_and_libstdcxx(tmp_path: Path) -> None:
    rootfs = tmp_path / "rootfs.tar"
    _write_rootfs_tar(rootfs)

    candidates = list_symbol_library_candidates(str(rootfs))

    assert [candidate.soname for candidate in candidates] == ["libc.so.6", "libstdc++.so.6"]


def test_extract_member_to_directory_resolves_relative_symlink(tmp_path: Path) -> None:
    rootfs = tmp_path / "rootfs.tar"
    output = tmp_path / "extracted"
    output.mkdir()
    _write_rootfs_tar(rootfs)

    extracted = extract_member_to_directory(
        str(rootfs),
        "/lib/x86_64-linux-gnu/libc.so.6",
        str(output),
    )

    assert extracted == str(output / "libc.so.6")
    assert Path(extracted).read_bytes() == b"libc"
