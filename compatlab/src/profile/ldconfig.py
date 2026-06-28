import re

from compatlab.src.profile.models import LibraryFact


_LDCONFIG_LINE_RE = re.compile(
    r"^\s*(?P<soname>\S+)\s+\((?P<arch>[^)]*)\)\s+=>\s+(?P<path>\S+)\s*$"
)


def parse_ldconfig_cache(output: str) -> list[LibraryFact]:
    libraries: dict[str, LibraryFact] = {}
    for line in output.splitlines():
        match = _LDCONFIG_LINE_RE.match(line)
        if match is None:
            continue
        soname = match.group("soname")
        libraries.setdefault(
            soname,
            LibraryFact(
                soname=soname,
                path=match.group("path"),
                arch=match.group("arch") or None,
            ),
        )
    return [libraries[soname] for soname in sorted(libraries)]
