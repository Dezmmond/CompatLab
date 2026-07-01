from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from . import __version__
from .bundle.resolver import (
    DEFAULT_MAX_DEPTH,
    DEFAULT_MAX_FILES
)
from .services.artifacts import (
    ArtifactCommandService,
    CompareCommandOptions,
    ScanCommandOptions
)
from .services.profiles import ProfileCommandService
from .diagnostics import FailOn


app = typer.Typer(help="Preflight compatibility checker for Linux binary artifacts.")

profiles_app = typer.Typer(help="Inspect built-in target profiles.")
runtime_presets_app = typer.Typer(help="Inspect built-in Docker runtime presets.")

app.add_typer(profiles_app, name="profiles")
profiles_app.add_typer(runtime_presets_app, name="runtime-presets")

console = Console()


class CliServiceFactory:
    @staticmethod
    def artifacts() -> ArtifactCommandService:
        return ArtifactCommandService(console=console)

    @staticmethod
    def profiles() -> ProfileCommandService:
        return ProfileCommandService(console=console)


services = CliServiceFactory()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"compatlab {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option("--version", callback=_version_callback, help="Show version and exit."),
    ] = False,
) -> None:
    _ = version


@app.command()
def scan(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=True, dir_okay=False)],
    bundle_root: Annotated[
        Path | None,
        typer.Option("--bundle-root", exists=True, file_okay=False, dir_okay=True),
    ] = None,
    recursive: Annotated[
        bool, typer.Option("--recursive", help="Resolve transitive bundled ELF dependencies.")
    ] = False,
    max_depth: Annotated[
        int, typer.Option("--max-depth", help="Maximum recursive dependency depth.")
    ] = DEFAULT_MAX_DEPTH,
    max_files: Annotated[
        int, typer.Option("--max-files", help="Maximum files to index under bundle root.")
    ] = DEFAULT_MAX_FILES,
    fail_on: Annotated[
        FailOn,
        typer.Option("--fail-on", help="Fail on diagnostics: error, warning, or never."),
    ] = FailOn.ERROR,
    json_output: Annotated[Path | None, typer.Option("--json", help="Write JSON report.")] = None,
    html_output: Annotated[
        Path | None, typer.Option("--html", help="Write static HTML report.")
    ] = None,
) -> None:
    """Scan one Linux artifact and print a structured stub report."""
    services.artifacts().scan(
        ScanCommandOptions(
            path=path,
            bundle_root=bundle_root,
            recursive=recursive,
            max_depth=max_depth,
            max_files=max_files,
            fail_on=fail_on,
            json_output=json_output,
            html_output=html_output,
        )
    )


@app.command()
def compare(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=True, dir_okay=False)],
    target: Annotated[str | None, typer.Option("--target", help="Built-in profile id.")] = None,
    target_file: Annotated[
        Path | None,
        typer.Option("--target-file", help="External YAML target profile."),
    ] = None,
    bundle_root: Annotated[
        Path | None,
        typer.Option("--bundle-root", exists=True, file_okay=False, dir_okay=True),
    ] = None,
    recursive: Annotated[
        bool, typer.Option("--recursive", help="Resolve transitive bundled ELF dependencies.")
    ] = False,
    max_depth: Annotated[
        int, typer.Option("--max-depth", help="Maximum recursive dependency depth.")
    ] = DEFAULT_MAX_DEPTH,
    max_files: Annotated[
        int, typer.Option("--max-files", help="Maximum files to index under bundle root.")
    ] = DEFAULT_MAX_FILES,
    fail_on: Annotated[
        FailOn,
        typer.Option("--fail-on", help="Fail on diagnostics: error, warning, or never."),
    ] = FailOn.ERROR,
    json_output: Annotated[Path | None, typer.Option("--json", help="Write JSON report.")] = None,
    html_output: Annotated[
        Path | None, typer.Option("--html", help="Write static HTML report.")
    ] = None,
) -> None:
    """Compare one Linux artifact with a target profile."""
    services.artifacts().compare(
        CompareCommandOptions(
            path=path,
            target=target,
            target_file=target_file,
            bundle_root=bundle_root,
            recursive=recursive,
            max_depth=max_depth,
            max_files=max_files,
            fail_on=fail_on,
            json_output=json_output,
            html_output=html_output,
        )
    )


@profiles_app.command("list")
def profiles_list() -> None:
    """List built-in target profiles."""
    services.profiles().list_profiles()


@profiles_app.command("show")
def profiles_show(
    target: Annotated[str, typer.Argument(help="Built-in profile id or YAML path.")],
) -> None:
    """Show one target profile."""
    services.profiles().show_profile(target)


@runtime_presets_app.command("list")
def runtime_presets_list() -> None:
    """List built-in Docker runtime presets."""
    services.profiles().list_runtime_presets()


@runtime_presets_app.command("show")
def runtime_presets_show(
    name: Annotated[str, typer.Argument(help="Runtime preset name.")],
) -> None:
    """Show one Docker runtime preset."""
    services.profiles().show_runtime_preset(name)


@profiles_app.command("detect")
def profiles_detect(
    from_image: Annotated[
        str | None,
        typer.Option("--from-image", help="Detect raw facts from a Docker image."),
    ] = None,
    platform: Annotated[
        str | None,
        typer.Option("--platform", help="Docker image platform, for example linux/amd64."),
    ] = None,
    pull: Annotated[
        bool, typer.Option("--pull", help="Pull Docker image before detection.")
    ] = False,
    runtime_preset: Annotated[
        str | None,
        typer.Option(
            "--runtime-preset", help="Install a built-in runtime preset before detection."
        ),
    ] = None,
    json_output: Annotated[
        Path | None,
        typer.Option("--json", help="Write raw detected system facts as JSON."),
    ] = None,
) -> None:
    """Detect raw facts from the current Linux system."""
    services.profiles().detect(
        from_image=from_image,
        platform=platform,
        pull=pull,
        runtime_preset=runtime_preset,
        json_output=json_output,
    )


@profiles_app.command("generate")
def profiles_generate(
    from_current: Annotated[
        bool,
        typer.Option("--from-current", help="Generate from the current Linux system."),
    ] = False,
    from_image: Annotated[
        str | None,
        typer.Option("--from-image", help="Generate from a Docker image."),
    ] = None,
    platform: Annotated[
        str | None,
        typer.Option("--platform", help="Docker image platform, for example linux/amd64."),
    ] = None,
    pull: Annotated[
        bool, typer.Option("--pull", help="Pull Docker image before generation.")
    ] = False,
    runtime_preset: Annotated[
        str | None,
        typer.Option(
            "--runtime-preset", help="Install a built-in runtime preset before generation."
        ),
    ] = None,
    name: Annotated[str, typer.Option("--name", help="Generated target profile id.")] = "local",
    output: Annotated[
        Path | None, typer.Option("--output", help="Output YAML profile path.")
    ] = None,
) -> None:
    """Generate a YAML target profile."""
    services.profiles().generate(
        from_current=from_current,
        from_image=from_image,
        platform=platform,
        pull=pull,
        runtime_preset=runtime_preset,
        name=name,
        output=output,
    )


@profiles_app.command("validate")
def profiles_validate(
    profile_file: Annotated[Path, typer.Argument(help="YAML target profile path.")],
    json_output: Annotated[
        Path | None,
        typer.Option("--json", help="Write validation result as JSON."),
    ] = None,
) -> None:
    """Validate a YAML target profile."""
    services.profiles().validate(profile_file=profile_file, json_output=json_output)


if __name__ == "__main__":
    app()
