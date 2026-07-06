"""Load built-in and external target profile YAML files."""

import yaml

from pathlib import Path
from pydantic import ValidationError
from typing import Any

from compatlab.models import TargetProfile


class ProfileNotFoundError(ValueError):
    pass


class ProfileLoadError(ValueError):
    pass


def builtin_profiles_dir() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / "profiles"
        if candidate.is_dir():
            return candidate
    return current.parents[2] / "profiles"


def list_builtin_profiles() -> list[TargetProfile]:
    profiles = [load_profile(path) for path in sorted(builtin_profiles_dir().glob("*.yml"))]
    return sorted(profiles, key=lambda profile: profile.id)


def load_target_profile(target: str) -> TargetProfile:
    target_path = Path(target)
    if target_path.exists():
        return load_profile_file(target_path)

    profile_path = builtin_profiles_dir() / f"{target}.yml"
    if profile_path.exists():
        return load_profile_file(profile_path)

    raise ProfileNotFoundError(f"Unknown target profile: {target}")


def load_profile_file(path: Path) -> TargetProfile:
    if not path.exists():
        raise ProfileNotFoundError(f"Profile file does not exist: {path}")
    return load_profile(path)


def load_profile(path: Path) -> TargetProfile:
    try:
        with path.open("r", encoding="utf-8") as stream:
            raw: Any = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        raise ProfileLoadError(f"Invalid YAML profile: {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ProfileLoadError(f"Profile file is not a YAML mapping: {path}")
    try:
        return TargetProfile.model_validate(raw)
    except ValidationError as exc:
        raise ProfileLoadError(f"Invalid target profile: {path}: {exc}") from exc
