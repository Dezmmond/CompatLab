"""Build target profile documents from detected system facts."""

from datetime import UTC, datetime

from compatlab.compare.engine import parse_version_tuple
from compatlab.models import (
    LibcProfile,
    LibstdcxxProfile,
    ProfileMetadata,
    ProvidedLibrary,
    SystemFacts,
    TargetProfile,
)


class TargetProfileGenerator:
    def generate(
        self,
        facts: SystemFacts,
        *,
        name: str,
        generated_at: datetime | None = None,
    ) -> TargetProfile:
        timestamp = generated_at or datetime.now(UTC)
        return TargetProfile(
            id=name,
            name=self._profile_name(facts, name),
            arch=facts.architecture or "unknown",
            libc=LibcProfile(
                family="glibc", version=self._max_or_detected(facts.symbol_versions.glibc, facts)
            ),
            libstdcxx=LibstdcxxProfile(
                max_glibcxx=self._max_version(facts.symbol_versions.glibcxx),
                max_cxxabi=self._max_version(facts.symbol_versions.cxxabi),
            ),
            interpreters=sorted(facts.dynamic_linkers),
            provided_libraries=[
                ProvidedLibrary(soname=soname)
                for soname in sorted({library.soname for library in facts.libraries})
            ],
            metadata=self._metadata(facts, timestamp),
            notes="Generated from current system facts.",
        )

    def _metadata(self, facts: SystemFacts, timestamp: datetime) -> ProfileMetadata:
        return ProfileMetadata(
            generated_by="compatlab",
            generated_at=timestamp.isoformat().replace("+00:00", "Z"),
            source=self._metadata_source(facts),
            source_image=facts.source_image,
            source_image_id=facts.source_image_id,
            source_os_id=facts.os_release.id,
            source_os_version_id=facts.os_release.version_id,
            detection_backend=self._detection_backend(facts),
            platform=facts.platform,
            runtime_preset=facts.runtime_preset,
            runtime_packages=facts.runtime_packages or None,
            package_manager=facts.package_manager,
        )

    @staticmethod
    def _profile_name(facts: SystemFacts, name: str) -> str:
        if facts.os_release.pretty_name:
            return facts.os_release.pretty_name
        return name

    @staticmethod
    def _metadata_source(facts: SystemFacts) -> str:
        if facts.source_image is None:
            return "current-system"
        if facts.runtime_preset is not None:
            return "docker-runtime-image"
        return "docker-image"

    @staticmethod
    def _detection_backend(facts: SystemFacts) -> str:
        if facts.source_image is None:
            return "local-system"
        if facts.runtime_preset is not None:
            return "docker-runtime-rootfs-export"
        return "docker-rootfs-export"

    def _max_or_detected(self, versions: list[str], facts: SystemFacts) -> str:
        return self._max_version(versions) or facts.glibc_version or "0"

    @staticmethod
    def _max_version(versions: list[str]) -> str | None:
        if not versions:
            return None
        return max(versions, key=parse_version_tuple)


def generate_target_profile_from_facts(
    facts: SystemFacts,
    *,
    name: str,
    generated_at: datetime | None = None,
) -> TargetProfile:
    return TargetProfileGenerator().generate(facts, name=name, generated_at=generated_at)
