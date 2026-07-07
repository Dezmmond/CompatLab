import gzip
import stat
import struct

from pathlib import Path


RPM_TYPE_INT32 = 4
RPM_TYPE_STRING = 6
RPM_TYPE_STRING_ARRAY = 8


def write_test_rpm(
    path: Path,
    *,
    name: str = "demo",
    version: str = "1.0.0",
    release: str = "1",
    arch: str = "x86_64",
    summary: str = "Demo RPM",
    license_name: str = "MIT",
    files: dict[str, bytes] | None = None,
    payload_format: str = "cpio",
    payload_compressor: str = "gzip",
) -> None:
    files = files or {}
    payload = build_newc(files)
    if payload_compressor == "gzip":
        payload = gzip.compress(payload)
    elif payload_compressor != "none":
        raise ValueError(f"Unsupported test payload compressor: {payload_compressor}")

    lead = bytearray(96)
    lead[:4] = b"\xed\xab\xee\xdb"
    lead[4] = 3
    lead[5] = 0
    signature_header = build_rpm_header([])
    metadata_header = build_rpm_header(
        [
            (1000, RPM_TYPE_STRING, name),
            (1001, RPM_TYPE_STRING, version),
            (1002, RPM_TYPE_STRING, release),
            (1004, RPM_TYPE_STRING_ARRAY, [summary]),
            (1014, RPM_TYPE_STRING, license_name),
            (1022, RPM_TYPE_STRING, arch),
            (1124, RPM_TYPE_STRING, payload_format),
            (1125, RPM_TYPE_STRING, payload_compressor),
        ]
    )
    path.write_bytes(bytes(lead) + signature_header + metadata_header + payload)


def build_rpm_header(entries: list[tuple[int, int, object]]) -> bytes:
    store = bytearray()
    indexes = []
    for tag, value_type, value in entries:
        offset = len(store)
        if value_type == RPM_TYPE_STRING:
            data = str(value).encode() + b"\0"
            count = 1
        elif value_type == RPM_TYPE_STRING_ARRAY:
            values = [str(item).encode() + b"\0" for item in value]
            data = b"".join(values)
            count = len(values)
        elif value_type == RPM_TYPE_INT32:
            data = struct.pack(">I", int(value))
            count = 1
        else:
            raise ValueError(f"Unsupported test RPM value type: {value_type}")
        store.extend(data)
        indexes.append((tag, value_type, offset, count))

    header = bytearray(b"\x8e\xad\xe8\x01" + b"\0" * 4)
    header.extend(struct.pack(">II", len(indexes), len(store)))
    for index in indexes:
        header.extend(struct.pack(">IIII", *index))
    header.extend(store)
    header.extend(b"\0" * (-len(header) % 8))
    return bytes(header)


def build_newc(files: dict[str, bytes]) -> bytes:
    output = bytearray()
    for index, (name, data) in enumerate(files.items(), start=1):
        output.extend(_newc_entry(name, data, ino=index))
    output.extend(_newc_entry("TRAILER!!!", b"", ino=len(files) + 1))
    return bytes(output)


def _newc_entry(name: str, data: bytes, *, ino: int) -> bytes:
    name_bytes = name.encode() + b"\0"
    fields = [
        "070701",
        f"{ino:08x}",
        f"{(stat.S_IFREG | 0o755):08x}",
        "00000000",
        "00000000",
        "00000001",
        "00000000",
        f"{len(data):08x}",
        "00000000",
        "00000000",
        "00000000",
        "00000000",
        f"{len(name_bytes):08x}",
        "00000000",
    ]
    entry = bytearray("".join(fields).encode())
    entry.extend(name_bytes)
    entry.extend(b"\0" * (-len(entry) % 4))
    entry.extend(data)
    entry.extend(b"\0" * (-len(entry) % 4))
    return bytes(entry)
