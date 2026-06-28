# CompatLab ArtifactDoctor

Preflight compatibility checker for Linux binary artifacts.

CompatLab ArtifactDoctor is a Python-first CLI tool for checking whether a Linux
binary artifact is likely to run on a target Linux profile before it is shipped.
The product goal is to turn low-level ELF facts into a compatibility diagnosis:
too-new `glibc` or `libstdc++`, missing dynamic linker, missing `DT_NEEDED`
libraries, wrong architecture, and suspicious `RPATH`/`RUNPATH` values.

This repository contains the Python-first CLI skeleton and the first real ELF
scanner backend based on the system `readelf` utility.

## CLI

```bash
compatlab scan ./app
compatlab compare ./app --target ubuntu-1804
compatlab profiles list
compatlab profiles show ubuntu-1804
```

JSON report output is wired for scan and compare:

```bash
compatlab scan ./app --json report.json
compatlab compare ./app --target ubuntu-1804 --json report.json
```

## MVP Scope

The first MVP is intentionally narrow:

- one ELF binary or shared library as input;
- one target profile in YAML;
- pretty terminal output with Rich;
- JSON reports based on Pydantic models;
- Typer-based CLI suitable for CI;
- target profiles for common Linux baselines;
- problem taxonomy ready for compatibility diagnostics.

## Not In Scope Yet

This skeleton does not add a web UI, database, daemon, wheel/RPM/DEB analysis,
container/rootfs scanning, SBOM/security scanning, automatic patching, or a Go
implementation. Those are explicitly outside the first implementation pass.

## Development

```bash
make test
make coverage
make check
uv run compatlab scan /bin/bash
```

`make coverage` prints the total test coverage percentage in the terminal and
writes `coverage.xml`. `make coverage-html` also writes an HTML report under
`htmlcov/`.
