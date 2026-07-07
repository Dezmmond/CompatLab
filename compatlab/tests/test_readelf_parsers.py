from pathlib import Path

from compatlab.scanners.elf_scanner import (
    parse_dynamic_section,
    parse_elf_header,
    parse_program_headers,
    parse_version_info,
)

FIXTURES = Path(__file__).parent / "fixtures" / "readelf"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_elf_header() -> None:
    parsed = parse_elf_header(_fixture("header_bash.txt"))

    assert parsed["elf_class"] == "ELF64"
    assert parsed["endianness"] == "little"
    assert parsed["os_abi"] == "UNIX - System V"
    assert parsed["elf_type"] == "DYN"
    assert parsed["machine"] == "Advanced Micro Devices X86-64"
    assert parsed["entry_point"] == "0x31750"


def test_parse_program_headers_extracts_interpreter() -> None:
    parsed = parse_program_headers(_fixture("program_headers_bash.txt"))

    assert parsed == {"interpreter": "/lib64/ld-linux-x86-64.so.2"}


def test_parse_dynamic_section_extracts_needed_rpath_and_runpath() -> None:
    parsed = parse_dynamic_section(_fixture("dynamic_bash.txt"))

    assert parsed["is_dynamic"] is True
    assert parsed["needed"] == ["libtinfo.so.6", "libc.so.6"]
    assert parsed["rpath"] == ["/opt/vendor/lib"]
    assert parsed["runpath"] == ["$ORIGIN/../lib"]


def test_parse_version_info_extracts_required_versions_once() -> None:
    versions = parse_version_info(_fixture("version_info_bash.txt"))
    raw_versions = [version.raw for version in versions]

    assert raw_versions == [
        "CXXABI_1.3",
        "GLIBC_2.2.5",
        "GLIBC_2.3",
        "GLIBC_2.34",
        "GLIBCXX_3.4.29",
    ]
