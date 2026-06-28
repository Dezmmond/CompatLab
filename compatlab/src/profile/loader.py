from pathlib import Path
from typing import Any

import yaml

from compatlab.src.profile.builtin import builtin_profiles_dir
from compatlab.src.profile.models import TargetProfile


class ProfileNotFoundError(ValueError):
    pass


def list_builtin_profiles() -> list[TargetProfile]:
    profiles = [load_profile(path) for path in sorted(builtin_profiles_dir().glob("*.yml"))]
    return sorted(profiles, key=lambda profile: profile.id)


def load_target_profile(target: str) -> TargetProfile:
    target_path = Path(target)
    if target_path.exists():
        return load_profile(target_path)

    profile_path = builtin_profiles_dir() / f"{target}.yml"
    if profile_path.exists():
        return load_profile(profile_path)

    raise ProfileNotFoundError(f"Unknown target profile: {target}")


def load_profile(path: Path) -> TargetProfile:
    with path.open("r", encoding="utf-8") as stream:
        raw: Any = yaml.safe_load(stream)
    if not isinstance(raw, dict):
        raise ValueError(f"Profile file is not a YAML mapping: {path}")
    return TargetProfile.model_validate(raw)
