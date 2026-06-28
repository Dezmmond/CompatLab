import re


_VERSION_RE = re.compile(r"\b(?P<version>[0-9]+(?:\.[0-9]+)+)\b")


def parse_ldd_glibc_version(output: str) -> str | None:
    first_line = next((line.strip() for line in output.splitlines() if line.strip()), "")
    if not first_line:
        return None
    match = _VERSION_RE.search(first_line)
    if match is None:
        return None
    return match.group("version")
