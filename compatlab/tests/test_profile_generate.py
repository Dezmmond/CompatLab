from datetime import UTC, datetime

from compatlab.src.profile.generate import generate_target_profile_from_facts
from compatlab.src.profile.models import (
    LibraryFact,
    OsReleaseFacts,
    SystemFacts,
    SymbolVersionFacts,
)


def test_generate_target_profile_from_facts_maps_detected_values() -> None:
    facts = SystemFacts(
        os_release=OsReleaseFacts(id="ubuntu", version_id="24.04", pretty_name="Ubuntu 24.04 LTS"),
        architecture="x86_64",
        glibc_version="2.39",
        dynamic_linkers=["/lib64/ld-linux-x86-64.so.2"],
        libraries=[
            LibraryFact(soname="libc.so.6", path="/lib/libc.so.6"),
            LibraryFact(soname="libstdc++.so.6", path="/lib/libstdc++.so.6"),
            LibraryFact(soname="libc.so.6", path="/another/libc.so.6"),
        ],
        symbol_versions=SymbolVersionFacts(
            glibc=["2.2.5", "2.39"],
            glibcxx=["3.4", "3.4.33"],
            cxxabi=["1.3", "1.3.15"],
        ),
    )

    profile = generate_target_profile_from_facts(
        facts,
        name="local",
        generated_at=datetime(2026, 6, 28, 12, 0, tzinfo=UTC),
    )

    assert profile.id == "local"
    assert profile.name == "Ubuntu 24.04 LTS"
    assert profile.arch == "x86_64"
    assert profile.libc.version == "2.39"
    assert profile.libstdcxx is not None
    assert profile.libstdcxx.max_glibcxx == "3.4.33"
    assert profile.libstdcxx.max_cxxabi == "1.3.15"
    assert profile.interpreters == ["/lib64/ld-linux-x86-64.so.2"]
    assert [library.soname for library in profile.provided_libraries] == [
        "libc.so.6",
        "libstdc++.so.6",
    ]
    assert profile.metadata is not None
    assert profile.metadata.generated_at == "2026-06-28T12:00:00Z"
    assert profile.metadata.source_os_id == "ubuntu"
