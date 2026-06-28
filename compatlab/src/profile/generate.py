from datetime import UTC, datetime

from compatlab.src.compare.engine import parse_version_tuple
from compatlab.src.profile.models import (
    LibcProfile,
    LibstdcxxProfile,
    ProfileMetadata,
    ProvidedLibrary,
    SystemFacts,
    TargetProfile,
)


def generate_target_profile_from_facts(
    facts: SystemFacts,
    *,
    name: str,
    generated_at: datetime | None = None,
) -> TargetProfile:
    timestamp = generated_at or datetime.now(UTC)
    return TargetProfile(
        id=name,
        name=_profile_name(facts, name),
        arch=facts.architecture or "unknown",
        libc=LibcProfile(
            family="glibc", version=_max_or_detected(facts.symbol_versions.glibc, facts)
        ),
        libstdcxx=LibstdcxxProfile(
            max_glibcxx=_max_version(facts.symbol_versions.glibcxx),
            max_cxxabi=_max_version(facts.symbol_versions.cxxabi),
        ),
        interpreters=sorted(facts.dynamic_linkers),
        provided_libraries=[
            ProvidedLibrary(soname=soname)
            for soname in sorted({library.soname for library in facts.libraries})
        ],
        metadata=ProfileMetadata(
            generated_by="compatlab",
            generated_at=timestamp.isoformat().replace("+00:00", "Z"),
            source="current-system",
            source_os_id=facts.os_release.id,
            source_os_version_id=facts.os_release.version_id,
            detection_backend="local-system",
        ),
        notes="Generated from current system facts.",
    )


def _profile_name(facts: SystemFacts, name: str) -> str:
    if facts.os_release.pretty_name:
        return facts.os_release.pretty_name
    return name


def _max_or_detected(versions: list[str], facts: SystemFacts) -> str:
    return _max_version(versions) or facts.glibc_version or "0"


def _max_version(versions: list[str]) -> str | None:
    if not versions:
        return None
    return max(versions, key=parse_version_tuple)
