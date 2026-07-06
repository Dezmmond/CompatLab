import json
from pathlib import Path

import yaml
from rich.console import Console

import compatlab.profile.detect as profile_detect
import compatlab.profile.docker_image as docker_image
import compatlab.profile.loader as profile_loader
from compatlab.models import SystemFacts, TargetProfile
from compatlab.profile.docker_cli import DockerError
from compatlab.profile.generate import generate_target_profile_from_facts
from compatlab.profile.loader import (
    ProfileLoadError,
    ProfileNotFoundError,
)
from compatlab.profile.runtime_presets import (
    RuntimePreset,
    RuntimePresetError,
    get_runtime_preset,
    list_runtime_presets,
)
from compatlab.report.pretty import render_profiles
from compatlab.services.exceptions import CommandExit


class ProfileFileWriter:
    @staticmethod
    def write_system_facts_json(facts: SystemFacts, path: Path) -> None:
        path.write_text(facts.model_dump_json(indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def write_target_profile_yaml(profile: TargetProfile, path: Path) -> None:
        raw = profile.model_dump(mode="json", exclude_none=True)
        path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    @staticmethod
    def write_validation_json(
            path: Path,
        *,
        profile_file: Path,
        status: str,
        target: str | None = None,
        architecture: str | None = None,
        error: str | None = None,
    ) -> None:
        payload = {"profile": str(profile_file), "status": status}
        if error is not None:
            payload["error"] = error
        if target is not None:
            payload["target"] = target
        if architecture is not None:
            payload["architecture"] = architecture
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


class SystemFactsRenderer:
    def __init__(self, console: Console) -> None:
        self.console = console

    def render(self, facts: SystemFacts) -> None:
        self.console.print("[bold]System profile detected[/bold]")
        self.console.print(
            f"[bold]OS:[/bold] {facts.os_release.pretty_name or facts.os_release.id or 'unknown'}"
        )
        self.console.print(f"[bold]Architecture:[/bold] {facts.architecture or 'unknown'}")
        self.console.print(f"[bold]glibc:[/bold] {facts.glibc_version or 'unknown'}")
        self.console.print(
            f"[bold]GLIBC max:[/bold] {self._last_or_unknown(facts.symbol_versions.glibc)}"
        )
        self.console.print(
            f"[bold]GLIBCXX max:[/bold] {self._last_or_unknown(facts.symbol_versions.glibcxx)}"
        )
        self.console.print(
            f"[bold]CXXABI max:[/bold] {self._last_or_unknown(facts.symbol_versions.cxxabi)}"
        )
        self.console.print(f"[bold]Interpreters:[/bold] {len(facts.dynamic_linkers)}")
        self.console.print(f"[bold]Libraries:[/bold] {len(facts.libraries)}")
        self.console.print(f"[bold]Warnings:[/bold] {len(facts.warnings)}")

    @staticmethod
    def _last_or_unknown(values: list[str]) -> str:
        if not values:
            return "unknown"
        return values[-1]


class RuntimePresetRenderer:
    def __init__(self, console: Console) -> None:
        self.console = console

    def render(self, preset: RuntimePreset) -> None:
        self.console.print(f"[bold]Runtime preset:[/bold] {preset.name}")
        self.console.print(f"[bold]Description:[/bold] {preset.description}")
        self.console.print(
            f"[bold]Package managers:[/bold] {', '.join(preset.supported_package_managers)}"
        )
        self.console.print("[bold]Packages:[/bold]")
        for manager in preset.supported_package_managers:
            packages = preset.packages_by_manager.get(manager, [])
            self.console.print(f"  {manager}: {', '.join(packages)}")
        if preset.limitations:
            self.console.print("[bold]Limitations:[/bold]")
            for limitation in preset.limitations:
                self.console.print(f"  {limitation}")


class ProfileCommandService:
    def __init__(
        self,
        *,
        console: Console,
        files: ProfileFileWriter | None = None,
        facts_renderer: SystemFactsRenderer | None = None,
        runtime_renderer: RuntimePresetRenderer | None = None,
    ) -> None:
        self.console = console

        self.files = files or ProfileFileWriter()
        self.facts_renderer = facts_renderer or SystemFactsRenderer(console)
        self.runtime_renderer = runtime_renderer or RuntimePresetRenderer(console)

    def list_profiles(self) -> None:
        render_profiles(profile_loader.list_builtin_profiles(), self.console)

    def show_profile(self, target: str) -> None:
        try:
            profile = profile_loader.load_target_profile(target)
        except ProfileNotFoundError as exc:
            self.console.print(f"[red]{exc}[/red]")
            raise CommandExit(2) from exc
        self.console.print_json(profile.model_dump_json(indent=2))

    def list_runtime_presets(self) -> None:
        self.console.print("[bold]Available runtime presets:[/bold]")
        for preset in list_runtime_presets():
            self.console.print(f"{preset.name:18} {preset.description}")

    def show_runtime_preset(self, name: str) -> None:
        try:
            preset = get_runtime_preset(name)
        except RuntimePresetError as exc:
            self.console.print(f"[red]Error: {exc}[/red]")
            raise CommandExit(2) from exc
        self.runtime_renderer.render(preset)

    def detect(
        self,
        *,
        from_image: str | None,
        platform: str | None,
        pull: bool,
        runtime_preset: str | None,
        json_output: Path | None,
    ) -> None:
        self._validate_runtime_preset_source(from_image, runtime_preset)
        facts = self._detect_facts(
            from_image=from_image,
            platform=platform,
            pull=pull,
            runtime_preset=runtime_preset,
        )
        if json_output is not None:
            self.files.write_system_facts_json(facts, json_output)
        self.facts_renderer.render(facts)

    def generate(
        self,
        *,
        from_current: bool,
        from_image: str | None,
        platform: str | None,
        pull: bool,
        runtime_preset: str | None,
        name: str,
        output: Path | None,
    ) -> None:
        if from_current == (from_image is not None):
            self.console.print("[red]Provide exactly one of --from-current or --from-image.[/red]")
            raise CommandExit(2)
        self._validate_runtime_preset_source(from_image, runtime_preset)
        if output is None:
            self.console.print("[red]--output is required.[/red]")
            raise CommandExit(2)

        facts = self._detect_facts(
            from_image=from_image,
            platform=platform,
            pull=pull,
            runtime_preset=runtime_preset,
        )
        profile = generate_target_profile_from_facts(facts, name=name)
        self.files.write_target_profile_yaml(profile, output)
        self._render_generated_profile(
            profile,
            output=output,
            from_image=from_image,
            runtime_preset=runtime_preset,
        )

    def validate(self, *, profile_file: Path, json_output: Path | None) -> None:
        try:
            profile = profile_loader.load_profile_file(profile_file)
        except (ProfileNotFoundError, ProfileLoadError) as exc:
            if json_output is not None:
                self.files.write_validation_json(
                    json_output,
                    profile_file=profile_file,
                    status="invalid",
                    error=str(exc),
                )
            self.console.print(f"[bold]Profile:[/bold] {profile_file}")
            self.console.print("[bold]Status:[/bold] [red]invalid[/red]")
            self.console.print(f"[bold]Error:[/bold] {exc}")
            raise CommandExit(2) from exc

        if json_output is not None:
            self.files.write_validation_json(
                json_output,
                profile_file=profile_file,
                status="valid",
                target=profile.id,
                architecture=profile.arch,
            )
        self.console.print(f"[bold]Profile:[/bold] {profile_file}")
        self.console.print("[bold]Status:[/bold] [green]valid[/green]")
        self.console.print(f"[bold]Target:[/bold] {profile.id}")
        self.console.print(f"[bold]Architecture:[/bold] {profile.arch}")

    def _detect_facts(
        self,
        *,
        from_image: str | None,
        platform: str | None,
        pull: bool,
        runtime_preset: str | None,
    ) -> SystemFacts:
        try:
            if from_image is not None:
                return docker_image.detect_docker_image_system(
                    from_image,
                    platform=platform,
                    pull=pull,
                    runtime_preset=runtime_preset,
                )
            return profile_detect.detect_current_system()
        except (DockerError, RuntimePresetError) as exc:
            self.console.print(f"[red]Error: {exc}[/red]")
            raise CommandExit(2) from exc

    def _validate_runtime_preset_source(
        self, from_image: str | None, runtime_preset: str | None
    ) -> None:
        if runtime_preset is not None and from_image is None:
            self.console.print("[red]--runtime-preset is valid only with --from-image.[/red]")
            raise CommandExit(2)

    def _render_generated_profile(
        self,
        profile: TargetProfile,
        *,
        output: Path,
        from_image: str | None,
        runtime_preset: str | None,
    ) -> None:
        if from_image is not None:
            self.console.print("[bold]Docker image profile generated[/bold]")
            self.console.print(f"[bold]Image:[/bold] {from_image}")
            if runtime_preset is not None:
                self.console.print(f"[bold]Runtime preset:[/bold] {runtime_preset}")
            self.console.print(f"[bold]Name:[/bold] {profile.id}")
            self.console.print(f"[bold]Architecture:[/bold] {profile.arch}")
            self.console.print(f"[bold]OS:[/bold] {profile.name}")
            self.console.print(f"[bold]Output:[/bold] {output}")
            return

        self.console.print(f"[bold]Profile:[/bold] {output}")
        self.console.print("[bold]Status:[/bold] generated")
        self.console.print(f"[bold]Target:[/bold] {profile.id}")
        self.console.print(f"[bold]Architecture:[/bold] {profile.arch}")
