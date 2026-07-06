"""Application services used by CLI adapters."""

from compatlab.services.artifacts import (
    ArtifactCommandService,
    CompareCommandOptions,
    ScanCommandOptions,
)
from compatlab.services.exceptions import CommandExit
from compatlab.services.profiles import (
    ProfileCommandService,
    ProfileFileWriter,
    RuntimePresetRenderer,
    SystemFactsRenderer,
)
from compatlab.services.reports import (
    DependencyProblemFactory,
    DiagnosticsAugmenter,
    HtmlContextFactory,
    ReportWriter,
)

__all__ = [
    "ArtifactCommandService",
    "CommandExit",
    "CompareCommandOptions",
    "DependencyProblemFactory",
    "DiagnosticsAugmenter",
    "HtmlContextFactory",
    "ProfileCommandService",
    "ProfileFileWriter",
    "ReportWriter",
    "RuntimePresetRenderer",
    "ScanCommandOptions",
    "SystemFactsRenderer",
]
