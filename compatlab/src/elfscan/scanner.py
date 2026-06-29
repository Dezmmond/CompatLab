from pathlib import Path

from compatlab.src.artifact.detect import detect_artifact
from compatlab.src.elfscan.command import CommandResult, run_readelf
from compatlab.src.elfscan.models import ElfInfo
from compatlab.src.elfscan.parsers import (
    parse_dynamic_section,
    parse_elf_header,
    parse_program_headers,
    parse_version_info,
)
from compatlab.src.problem.models import Problem
from compatlab.src.report.models import ArtifactReport


class ScanWarningFactory:
    def warning(
        self, path: Path, title: str, details: str, evidence: dict[str, str] | None = None
    ) -> Problem:
        return Problem(
            id="scan.warning",
            severity="INFO",
            title=title,
            details=details,
            artifact_path=str(path),
            evidence=evidence or {},
        )

    def command_warning(self, path: Path, result: CommandResult) -> Problem:
        command = " ".join(result.args)
        stderr = result.stderr.strip()
        details = f"{command} exited with code {result.returncode}"
        if stderr:
            details = f"{details}: {stderr}"
        return self.warning(
            path,
            title="readelf command failed",
            details=details,
            evidence={"command": command, "returncode": str(result.returncode)},
        )


class ElfScanner:
    def __init__(
        self,
        *,
        readelf=None,
        warnings: ScanWarningFactory | None = None,
    ) -> None:
        self.readelf = readelf or run_readelf
        self.warnings = warnings or ScanWarningFactory()

    def scan(self, path: Path) -> ArtifactReport:
        artifact = detect_artifact(path)
        warnings: list[Problem] = []
        elf = ElfInfo(is_dynamic=False)

        header_output = self._apply_result(path, warnings, self.readelf(["-h"], path), "readelf -h")
        if header_output is not None:
            elf = elf.model_copy(update=parse_elf_header(header_output))

        program_headers = self._apply_result(
            path, warnings, self.readelf(["-l"], path), "readelf -l"
        )
        if program_headers is not None:
            elf = elf.model_copy(update=parse_program_headers(program_headers))

        dynamic_output = self._apply_result(
            path, warnings, self.readelf(["-d"], path), "readelf -d"
        )
        if dynamic_output is not None:
            elf = elf.model_copy(update=parse_dynamic_section(dynamic_output))
        else:
            warnings.append(
                self.warnings.warning(
                    path,
                    title="dynamic section not available",
                    details="DT_NEEDED, RPATH and RUNPATH could not be extracted.",
                )
            )

        version_output = self._apply_result(
            path,
            warnings,
            self.readelf(["--version-info"], path),
            "readelf --version-info",
        )
        if version_output is not None:
            elf = elf.model_copy(update={"required_versions": parse_version_info(version_output)})

        if elf.elf_class is None:
            warnings.append(
                self.warnings.warning(
                    path,
                    title="artifact is not recognized as ELF",
                    details="readelf did not return a parseable ELF header.",
                )
            )
        else:
            artifact = artifact.model_copy(update={"kind": "ELF"})

        return ArtifactReport(artifact=artifact, elf=elf, warnings=warnings)

    def _apply_result(
        self,
        path: Path,
        warnings: list[Problem],
        result: CommandResult,
        parser_name: str,
    ) -> str | None:
        if result.returncode == 0:
            return result.stdout
        warnings.append(self.warnings.command_warning(path, result))
        if result.stdout.strip():
            warnings.append(
                self.warnings.warning(
                    path,
                    title="partial readelf output used",
                    details=f"Using partial stdout from {parser_name}.",
                )
            )
            return result.stdout
        return None


def scan_path(path: Path) -> ArtifactReport:
    return ElfScanner().scan(path)
