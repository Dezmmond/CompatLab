# CompatLab ArtifactDoctor

Preflight compatibility checker for Linux binary artifacts.

CompatLab ArtifactDoctor is a Python-first CLI tool for checking whether a Linux
binary artifact is likely to run on a target Linux profile before it is shipped.
The product goal is to turn low-level ELF facts into a compatibility diagnosis:
too-new `glibc` or `libstdc++`, missing dynamic linker, missing `DT_NEEDED`
libraries, wrong architecture, and suspicious `RPATH`/`RUNPATH` values.

This repository contains the Python-first CLI, a real ELF scanner backend based
on the system `readelf` utility, compatibility comparison rules, and target
profile generation from the current system or Docker image rootfs exports.

## CLI

```bash
compatlab scan ./app
compatlab compare ./app --target ubuntu-1804
compatlab compare ./app --target-file ./local.yaml
compatlab profiles list
compatlab profiles show ubuntu-1804
compatlab profiles detect
compatlab profiles generate --from-current --name local --output local.yaml
compatlab profiles generate --from-image ubuntu:22.04 --name ubuntu-2204-docker --output ubuntu-2204.yaml
compatlab profiles validate ubuntu-2204.yaml
```

JSON report output is wired for scan and compare:

```bash
compatlab scan ./app --json report.json
compatlab compare ./app --target ubuntu-1804 --json report.json
compatlab profiles detect --json system-facts.json
compatlab profiles detect --from-image ubuntu:22.04 --json image-facts.json
```

## Docker Image Profiles

CompatLab can generate a target profile from a Docker image without requiring
Python, `readelf`, `ldconfig`, or development tools inside the image. It uses the
host Docker CLI to create and export a temporary container rootfs, parses that
tar archive from Python, and runs host-side `readelf` on extracted system
libraries.

```bash
uv run compatlab profiles generate \
  --from-image ubuntu:22.04 \
  --name ubuntu-2204-docker \
  --output /tmp/ubuntu-2204-docker.yaml

uv run compatlab profiles validate /tmp/ubuntu-2204-docker.yaml
uv run compatlab compare ./dist/my-app --target-file /tmp/ubuntu-2204-docker.yaml
```

Images are not pulled automatically. Use `--pull` when you explicitly want the
Docker CLI to pull first:

```bash
uv run compatlab profiles generate \
  --from-image ubuntu:22.04 \
  --pull \
  --name ubuntu-2204-docker \
  --output /tmp/ubuntu-2204-docker.yaml
```

## MVP Scope

The first MVP is intentionally narrow:

- one ELF binary or shared library as input;
- one target profile in YAML;
- pretty terminal output with Rich;
- JSON reports based on Pydantic models;
- Typer-based CLI suitable for CI;
- target profiles for common Linux baselines;
- generated target profiles from the current system or Docker image rootfs;
- problem taxonomy ready for compatibility diagnostics.

## Not In Scope Yet

CompatLab does not add runtime package presets, package installation inside
Docker images, web UI, database, daemon, wheel/RPM/DEB analysis, SBOM/security
scanning, automatic patching, or a Go implementation. Those are explicitly
outside the current implementation pass.

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
