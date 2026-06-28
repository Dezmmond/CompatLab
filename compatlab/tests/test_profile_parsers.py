from pathlib import Path

from compatlab.src.profile.ldconfig import parse_ldconfig_cache
from compatlab.src.profile.ldd import parse_ldd_glibc_version
from compatlab.src.profile.os_release import parse_os_release


FIXTURES = Path(__file__).parent / "fixtures" / "profiles_detect"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_os_release_extracts_known_fields() -> None:
    facts = parse_os_release(_fixture("ubuntu_2404_os_release.txt"))

    assert facts.id == "ubuntu"
    assert facts.name == "Ubuntu"
    assert facts.version_id == "24.04"
    assert facts.pretty_name == "Ubuntu 24.04.2 LTS"


def test_parse_os_release_ignores_comments_and_malformed_lines() -> None:
    facts = parse_os_release(
        """
        # comment
        ID=rocky
        malformed
        VERSION_ID='9.4'
        =ignored
        """
    )

    assert facts.id == "rocky"
    assert facts.version_id == "9.4"


def test_parse_ldd_glibc_version_extracts_first_line_version() -> None:
    assert parse_ldd_glibc_version(_fixture("ldd_ubuntu_2404.txt")) == "2.39"


def test_parse_ldd_glibc_version_returns_none_when_missing() -> None:
    assert parse_ldd_glibc_version("musl libc (x86_64)\n") is None


def test_parse_ldconfig_cache_extracts_libraries_deterministically() -> None:
    libraries = parse_ldconfig_cache(_fixture("ldconfig_ubuntu_2404.txt"))

    assert [library.soname for library in libraries] == [
        "libc.so.6",
        "libstdc++.so.6",
        "libz.so.1",
    ]
    assert libraries[1].path == "/lib/x86_64-linux-gnu/libstdc++.so.6"
    assert libraries[1].arch == "libc6,x86-64"
