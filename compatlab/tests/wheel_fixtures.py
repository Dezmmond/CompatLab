from pathlib import Path
import zipfile


def write_test_wheel(path: Path, *, native: bool = False, purelib: bool = True) -> None:
    tag = "cp311-cp311-linux_x86_64" if native else "py3-none-any"
    with zipfile.ZipFile(path, "w") as wheel:
        wheel.writestr(
            "demo-1.0.0.dist-info/WHEEL",
            "\n".join(
                [
                    "Wheel-Version: 1.0",
                    "Generator: compatlab-test",
                    f"Root-Is-Purelib: {str(purelib).lower()}",
                    f"Tag: {tag}",
                    "",
                ]
            ),
        )
        wheel.writestr(
            "demo-1.0.0.dist-info/METADATA",
            "Metadata-Version: 2.1\nName: demo\nVersion: 1.0.0\n",
        )
        wheel.writestr("demo-1.0.0.dist-info/RECORD", "")
        wheel.writestr("demo/__init__.py", b"")
        if native:
            wheel.writestr("demo/_native.cpython-311-x86_64-linux-gnu.so", b"\x7fELFfake")
