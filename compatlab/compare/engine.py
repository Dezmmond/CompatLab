from compatlab.models import (
    SymbolVersion,
    TargetProfile,
    ArtifactReport,
    Problem,
)


BUILD_PATH_PREFIXES = ("/home", "/tmp", "/build", "/workspace", "/var/tmp")


class VersionComparator:
    """Compares ABI version strings such as GLIBC_2.38 or 3.4.29."""

    @staticmethod
    def parse_tuple(value: str) -> tuple[int, ...]:
        version = value.rsplit("_", maxsplit=1)[-1]
        return tuple(int(part) for part in version.split("."))

    def is_newer(self, required: str, provided: str) -> bool:
        return self.parse_tuple(required) > self.parse_tuple(provided)

    def max_required(self, versions: list[SymbolVersion], namespace: str) -> SymbolVersion | None:
        matching = [version for version in versions if version.namespace == namespace]
        if not matching:
            return None
        return max(matching, key=lambda version: self.parse_tuple(version.version))


class ArchitectureNormalizer:
    _ALIASES = {
        "advanced micro devices x86_64": "x86_64",
        "amd64": "x86_64",
        "amd x86_64": "x86_64",
        "x86_64": "x86_64",
        "x64": "x86_64",
        "intel 80386": "x86",
        "i386": "x86",
        "i686": "x86",
        "x86": "x86",
        "aarch64": "aarch64",
        "arm aarch64": "aarch64",
    }

    def normalize(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower().replace("-", "_")
        normalized = " ".join(normalized.split())
        return self._ALIASES.get(normalized, normalized)


class ProblemFactory:
    @staticmethod
    def create(
            report: ArtifactReport,
        *,
        problem_id: str,
        severity: str,
        title: str,
        details: str,
        evidence: dict[str, str] | None = None,
        suggestions: list[str] | None = None,
    ) -> Problem:
        return Problem(
            id=problem_id,
            severity=severity,
            title=title,
            details=details,
            artifact_path=report.artifact.path,
            evidence=evidence or {},
            suggestions=suggestions or [],
        )


class CompatibilityComparator:
    def __init__(
        self,
        *,
        versions: VersionComparator | None = None,
        architectures: ArchitectureNormalizer | None = None,
        problems: ProblemFactory | None = None,
    ) -> None:
        self.versions = versions or VersionComparator()
        self.architectures = architectures or ArchitectureNormalizer()
        self.problems = problems or ProblemFactory()

    def compare(
        self,
        report: ArtifactReport,
        target: TargetProfile,
        *,
        assumed_provided_libraries: set[str] | None = None,
    ) -> ArtifactReport:
        problems: list[Problem] = list(report.problems)
        warnings: list[Problem] = list(report.warnings)
        if report.elf is None:
            return report.model_copy(
                update={"target": target, "problems": problems, "warnings": warnings}
            )

        problems.extend(self._check_architecture(report, target))
        problems.extend(self._check_interpreter(report, target))
        problems.extend(self._check_glibc(report, target))
        problems.extend(self._check_glibcxx(report, target))
        problems.extend(self._check_cxxabi(report, target))
        problems.extend(self._check_libraries(report, target, assumed_provided_libraries or set()))
        warnings.extend(self._check_search_paths(report, "rpath"))
        warnings.extend(self._check_search_paths(report, "runpath"))

        return report.model_copy(
            update={"target": target, "problems": problems, "warnings": warnings}
        )

    def _problem(
        self,
        report: ArtifactReport,
        *,
        problem_id: str,
        severity: str,
        title: str,
        details: str,
        evidence: dict[str, str] | None = None,
        suggestions: list[str] | None = None,
    ) -> Problem:
        return self.problems.create(
            report,
            problem_id=problem_id,
            severity=severity,
            title=title,
            details=details,
            evidence=evidence,
            suggestions=suggestions,
        )

    def _check_architecture(self, report: ArtifactReport, target: TargetProfile) -> list[Problem]:
        if report.elf is None:
            return []
        artifact_arch = self.architectures.normalize(report.elf.machine)
        target_arch = self.architectures.normalize(target.arch)
        if artifact_arch is None or artifact_arch == target_arch:
            return []
        return [
            self._problem(
                report,
                problem_id="wrong.architecture",
                severity="CRITICAL",
                title="Artifact architecture does not match target profile",
                details=(
                    f"Artifact architecture is {artifact_arch}, but target profile expects "
                    f"{target_arch}."
                ),
                evidence={
                    "artifact_arch": artifact_arch,
                    "target_arch": target_arch or target.arch,
                },
            )
        ]

    def _check_interpreter(self, report: ArtifactReport, target: TargetProfile) -> list[Problem]:
        if report.elf is None or not report.elf.is_dynamic:
            return []
        if report.elf.interpreter is None:
            return [
                self._problem(
                    report,
                    problem_id="missing.interpreter",
                    severity="HIGH",
                    title="Dynamic ELF does not declare a program interpreter",
                    details="Artifact is dynamic, but no PT_INTERP program interpreter was found.",
                )
            ]
        if report.elf.interpreter in target.interpreters:
            return []
        return [
            self._problem(
                report,
                problem_id="profile.interpreter_not_provided",
                severity="HIGH",
                title="Target profile does not provide the required dynamic linker",
                details=(
                    f"Artifact expects {report.elf.interpreter}, but target {target.id} does not "
                    "list it as provided."
                ),
                evidence={"interpreter": report.elf.interpreter, "target": target.id},
            )
        ]

    def _check_glibc(self, report: ArtifactReport, target: TargetProfile) -> list[Problem]:
        if report.elf is None or target.libc.family != "glibc":
            return []
        required = self.versions.max_required(report.elf.required_versions, "GLIBC")
        if required is None or not self.versions.is_newer(required.version, target.libc.version):
            return []
        provided = f"GLIBC_{target.libc.version}"
        return [
            self._problem(
                report,
                problem_id="glibc.too_new",
                severity="HIGH",
                title="Artifact requires newer glibc than target provides",
                details=(
                    f"Artifact requires {required.raw}, but target {target.id} provides up to "
                    f"{provided}."
                ),
                evidence={"required": required.raw, "provided": provided, "target": target.id},
                suggestions=[
                    "Rebuild the artifact on an older baseline distribution.",
                    "Use a target-compatible build container.",
                    "Choose a newer target profile.",
                ],
            )
        ]

    def _check_glibcxx(self, report: ArtifactReport, target: TargetProfile) -> list[Problem]:
        if report.elf is None or target.libstdcxx is None or target.libstdcxx.max_glibcxx is None:
            return []
        required = self.versions.max_required(report.elf.required_versions, "GLIBCXX")
        provided_version = target.libstdcxx.max_glibcxx
        if required is None or not self.versions.is_newer(required.version, provided_version):
            return []
        provided = f"GLIBCXX_{provided_version}"
        return [
            self._problem(
                report,
                problem_id="glibcxx.too_new",
                severity="HIGH",
                title="Artifact requires newer libstdc++ symbols than target provides",
                details=(
                    f"Artifact requires {required.raw}, but target {target.id} provides up to "
                    f"{provided}."
                ),
                evidence={"required": required.raw, "provided": provided, "target": target.id},
            )
        ]

    def _check_cxxabi(self, report: ArtifactReport, target: TargetProfile) -> list[Problem]:
        if report.elf is None or target.libstdcxx is None or target.libstdcxx.max_cxxabi is None:
            return []
        required = self.versions.max_required(report.elf.required_versions, "CXXABI")
        provided_version = target.libstdcxx.max_cxxabi
        if required is None or not self.versions.is_newer(required.version, provided_version):
            return []
        provided = f"CXXABI_{provided_version}"
        return [
            self._problem(
                report,
                problem_id="cxxabi.too_new",
                severity="HIGH",
                title="Artifact requires newer CXXABI symbols than target provides",
                details=(
                    f"Artifact requires {required.raw}, but target {target.id} provides up to "
                    f"{provided}."
                ),
                evidence={"required": required.raw, "provided": provided, "target": target.id},
            )
        ]

    def _check_libraries(
        self, report: ArtifactReport, target: TargetProfile, assumed_provided_libraries: set[str]
    ) -> list[Problem]:
        if report.elf is None:
            return []
        provided = {library.soname for library in target.provided_libraries}
        problems = []
        for library in report.elf.needed:
            if library in provided or library in assumed_provided_libraries:
                continue
            problems.append(
                self._problem(
                    report,
                    problem_id="profile.library_not_provided",
                    severity="HIGH",
                    title="Target profile does not list a required shared library",
                    details=(
                        f"Artifact requires {library}, but target {target.id} does not list it as "
                        "provided."
                    ),
                    evidence={"library": library, "target": target.id},
                )
            )
        return problems

    def _check_search_paths(self, report: ArtifactReport, field: str) -> list[Problem]:
        if report.elf is None:
            return []
        paths = getattr(report.elf, field)
        problems = []
        for path in paths:
            if path.startswith("/"):
                problems.append(
                    self._problem(
                        report,
                        problem_id=f"bad.{field}.absolute",
                        severity="LOW",
                        title=f"{field.upper()} contains an absolute path",
                        details=f"{field.upper()} entry {path} is absolute.",
                        evidence={field: path},
                    )
                )
            if self._is_build_path(path):
                problems.append(
                    self._problem(
                        report,
                        problem_id=f"bad.{field}.build_path",
                        severity="LOW",
                        title=f"{field.upper()} contains a build-time path",
                        details=f"{field.upper()} entry {path} looks like a build-time path.",
                        evidence={field: path},
                    )
                )
        return problems

    @staticmethod
    def _is_build_path(path: str) -> bool:
        return any(
            path == prefix or path.startswith(f"{prefix}/") for prefix in BUILD_PATH_PREFIXES
        )


def parse_version_tuple(value: str) -> tuple[int, ...]:
    return VersionComparator().parse_tuple(value)


def max_required_version(versions: list[SymbolVersion], namespace: str) -> SymbolVersion | None:
    return VersionComparator().max_required(versions, namespace)


def is_version_newer(required: str, provided: str) -> bool:
    return VersionComparator().is_newer(required, provided)


def normalize_architecture(value: str | None) -> str | None:
    return ArchitectureNormalizer().normalize(value)


def compare_report(
    report: ArtifactReport,
    target: TargetProfile,
    *,
    assumed_provided_libraries: set[str] | None = None,
) -> ArtifactReport:
    return CompatibilityComparator().compare(
        report, target, assumed_provided_libraries=assumed_provided_libraries
    )
