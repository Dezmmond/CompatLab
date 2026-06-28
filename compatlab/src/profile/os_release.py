from compatlab.src.profile.models import OsReleaseFacts


def parse_os_release(content: str) -> OsReleaseFacts:
    fields: dict[str, str] = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        fields[key] = _strip_value(value.strip())

    return OsReleaseFacts(
        id=fields.get("ID"),
        name=fields.get("NAME"),
        version_id=fields.get("VERSION_ID"),
        pretty_name=fields.get("PRETTY_NAME"),
    )


def _strip_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
