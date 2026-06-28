from compatlab.src.elfscan.models import SymbolVersion
from compatlab.src.problem.models import Problem
from compatlab.src.profile.models import TargetProfile
from compatlab.src.report.models import ArtifactReport


BUILD_PATH_PREFIXES = ("/home", "/tmp", "/build", "/workspace", "/var/tmp")


def parse_version_tuple(value: str) -> tuple[int, ...]:
    version = value.rsplit("_", maxsplit=1)[-1]
    return tuple(int(part) for part in version.split("."))


def max_required_version(versions: list[SymbolVersion], namespace: str) -> SymbolVersion | None:
    matching = [version for version in versions if version.namespace == namespace]
    if not matching:
        return None
    return max(matching, key=lambda version: parse_version_tuple(version.version))


def is_version_newer(required: str, provided: str) -> bool:
    return parse_version_tuple(required) > parse_version_tuple(provided)


def normalize_architecture(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower().replace("-", "_")
    normalized = " ".join(normalized.split())
    aliases = {
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
    return aliases.get(normalized, normalized)


def compare_report(report: ArtifactReport, target: TargetProfile) -> ArtifactReport:
    problems: list[Problem] = list(report.problems)
    warnings: list[Problem] = list(report.warnings)
    if report.elf is None:
        return report.model_copy(
            update={"target": target, "problems": problems, "warnings": warnings}
        )

    problems.extend(_check_architecture(report, target))
    problems.extend(_check_interpreter(report, target))
    problems.extend(_check_glibc(report, target))
    problems.extend(_check_glibcxx(report, target))
    problems.extend(_check_cxxabi(report, target))
    problems.extend(_check_libraries(report, target))
    warnings.extend(_check_search_paths(report, "rpath"))
    warnings.extend(_check_search_paths(report, "runpath"))

    return report.model_copy(update={"target": target, "problems": problems, "warnings": warnings})


def _problem(
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


def _check_architecture(report: ArtifactReport, target: TargetProfile) -> list[Problem]:
    if report.elf is None:
        return []
    artifact_arch = normalize_architecture(report.elf.machine)
    target_arch = normalize_architecture(target.arch)
    if artifact_arch is None or artifact_arch == target_arch:
        return []
    return [
        _problem(
            report,
            problem_id="wrong.architecture",
            severity="CRITICAL",
            title="Artifact architecture does not match target profile",
            details=(
                f"Artifact architecture is {artifact_arch}, but target profile expects "
                f"{target_arch}."
            ),
            evidence={"artifact_arch": artifact_arch, "target_arch": target_arch or target.arch},
        )
    ]


def _check_interpreter(report: ArtifactReport, target: TargetProfile) -> list[Problem]:
    if report.elf is None or not report.elf.is_dynamic:
        return []
    if report.elf.interpreter is None:
        return [
            _problem(
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
        _problem(
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


def _check_glibc(report: ArtifactReport, target: TargetProfile) -> list[Problem]:
    if report.elf is None or target.libc.family != "glibc":
        return []
    required = max_required_version(report.elf.required_versions, "GLIBC")
    if required is None or not is_version_newer(required.version, target.libc.version):
        return []
    provided = f"GLIBC_{target.libc.version}"
    return [
        _problem(
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


def _check_glibcxx(report: ArtifactReport, target: TargetProfile) -> list[Problem]:
    if report.elf is None or target.libstdcxx is None or target.libstdcxx.max_glibcxx is None:
        return []
    required = max_required_version(report.elf.required_versions, "GLIBCXX")
    provided_version = target.libstdcxx.max_glibcxx
    if required is None or not is_version_newer(required.version, provided_version):
        return []
    provided = f"GLIBCXX_{provided_version}"
    return [
        _problem(
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


def _check_cxxabi(report: ArtifactReport, target: TargetProfile) -> list[Problem]:
    if report.elf is None or target.libstdcxx is None or target.libstdcxx.max_cxxabi is None:
        return []
    required = max_required_version(report.elf.required_versions, "CXXABI")
    provided_version = target.libstdcxx.max_cxxabi
    if required is None or not is_version_newer(required.version, provided_version):
        return []
    provided = f"CXXABI_{provided_version}"
    return [
        _problem(
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


def _check_libraries(report: ArtifactReport, target: TargetProfile) -> list[Problem]:
    if report.elf is None:
        return []
    provided = {library.soname for library in target.provided_libraries}
    problems = []
    for library in report.elf.needed:
        if library in provided:
            continue
        problems.append(
            _problem(
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


def _check_search_paths(report: ArtifactReport, field: str) -> list[Problem]:
    if report.elf is None:
        return []
    paths = getattr(report.elf, field)
    problems = []
    for path in paths:
        if path.startswith("/"):
            problems.append(
                _problem(
                    report,
                    problem_id=f"bad.{field}.absolute",
                    severity="LOW",
                    title=f"{field.upper()} contains an absolute path",
                    details=f"{field.upper()} entry {path} is absolute.",
                    evidence={field: path},
                )
            )
        if _is_build_path(path):
            problems.append(
                _problem(
                    report,
                    problem_id=f"bad.{field}.build_path",
                    severity="LOW",
                    title=f"{field.upper()} contains a build-time path",
                    details=f"{field.upper()} entry {path} looks like a build-time path.",
                    evidence={field: path},
                )
            )
    return problems


def _is_build_path(path: str) -> bool:
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in BUILD_PATH_PREFIXES)
