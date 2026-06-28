from pathlib import Path


KNOWN_DYNAMIC_LINKERS = (
    "/lib64/ld-linux-x86-64.so.2",
    "/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2",
    "/lib/ld-linux.so.2",
    "/lib/ld-linux-aarch64.so.1",
    "/lib/aarch64-linux-gnu/ld-linux-aarch64.so.1",
)


def detect_dynamic_linkers(candidates: tuple[str, ...] = KNOWN_DYNAMIC_LINKERS) -> list[str]:
    return [candidate for candidate in candidates if Path(candidate).exists()]
