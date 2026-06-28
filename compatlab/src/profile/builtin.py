from pathlib import Path


def builtin_profiles_dir() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / "profiles"
        if candidate.is_dir():
            return candidate
    return current.parents[2] / "profiles"
