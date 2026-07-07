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
compatlab scan ./dist/demo-1.0.0-py3-none-any.whl
compatlab scan ./dist/demo-1.0.0-cp311-cp311-linux_x86_64.whl
compatlab scan ./dist/example-1.0.0-1.x86_64.rpm
compatlab scan ./dist/my-app --bundle-root ./dist --recursive
compatlab compare ./app --target ubuntu-1804
compatlab compare ./dist/demo-1.0.0-cp311-cp311-linux_x86_64.whl --target ubuntu-2204
compatlab compare ./dist/example-1.0.0-1.x86_64.rpm --target ubuntu-2204
compatlab compare ./app --target-file ./local.yaml
compatlab compare ./dist/my-app --target-file ./local.yaml --bundle-root ./dist --recursive
compatlab compare ./dist/my-app --target-file ./local.yaml --bundle-root ./dist --recursive --fail-on warning
compatlab profiles list
compatlab profiles show ubuntu-1804
compatlab profiles detect
compatlab profiles generate --from-current --name local --output local.yaml
compatlab profiles generate --from-image ubuntu:22.04 --name ubuntu-2204-docker --output ubuntu-2204.yaml
compatlab profiles runtime-presets list
compatlab profiles generate --from-image ubuntu:22.04 --runtime-preset cpp-runtime --name ubuntu-2204-cpp --output ubuntu-2204-cpp.yaml
compatlab profiles validate ubuntu-2204.yaml
```

JSON report output is wired for scan and compare:

```bash
compatlab scan ./app --json report.json
compatlab scan ./dist/demo-1.0.0-cp311-cp311-linux_x86_64.whl --json report.json
compatlab scan ./dist/example-1.0.0-1.x86_64.rpm --json report.json
compatlab compare ./app --target ubuntu-1804 --json report.json
compatlab compare ./dist/demo-1.0.0-cp311-cp311-linux_x86_64.whl --target ubuntu-2204 --json report.json
compatlab compare ./dist/example-1.0.0-1.x86_64.rpm --target-file ./profiles/prod.yaml --json report.json --html report.html
compatlab compare ./dist/my-app --target-file ./local.yaml --bundle-root ./dist --recursive --json report.json
compatlab compare ./dist/my-app --target-file ./local.yaml --bundle-root ./dist --recursive --fail-on never --json report.json
compatlab profiles detect --json system-facts.json
compatlab profiles detect --from-image ubuntu:22.04 --json image-facts.json
compatlab profiles detect --from-image ubuntu:22.04 --runtime-preset cpp-runtime --json runtime-facts.json
```

## HTML Reports

CompatLab can write static, self-contained HTML reports for `scan` and
`compare`. No server, CDN, or JavaScript application is required. HTML reports
are intended for human review in CI artifacts, release checks, and bug reports;
JSON remains the stable machine-readable format.

```bash
uv run compatlab scan ./dist/my-app \
  --bundle-root ./dist \
  --recursive \
  --html report.html

uv run compatlab compare ./dist/my-app \
  --target ubuntu-2204 \
  --bundle-root ./dist \
  --recursive \
  --fail-on warning \
  --json report.json \
  --html report.html
```

The HTML report includes the diagnostic summary, normalized diagnostic issues,
bundle dependency resolution details, legacy compatibility problems and
warnings, and compact ELF/target metadata.

## Python Wheel Scanning

CompatLab accepts Python wheel (`.whl`) files in the existing `scan` and
`compare` commands. Wheel scanning is static: CompatLab opens the zip archive,
reads `WHEEL`, `METADATA`, and `RECORD` metadata, discovers native ELF entries
such as `.so`, `.so.*`, `*.cpython-...so`, and `*.abi3.so`, and scans only those
native files with the existing ELF pipeline. Wheel code is not imported or
executed.

```bash
uv run compatlab scan ./dist/demo-1.0.0-py3-none-any.whl
uv run compatlab scan ./dist/demo-1.0.0-cp311-cp311-linux_x86_64.whl \
  --json wheel-report.json \
  --html wheel-report.html

uv run compatlab compare ./dist/demo-1.0.0-cp311-cp311-linux_x86_64.whl \
  --target ubuntu-2204 \
  --fail-on warning \
  --json wheel-compat.json \
  --html wheel-compat.html
```

Pure Python wheels report `CL_WHEEL_NO_NATIVE_EXTENSIONS` as an informational
diagnostic. Native wheels aggregate compatibility diagnostics from every native
entry, so existing codes such as `CL_SYMBOL_GLIBCXX_TOO_NEW`, `CL_LIB_MISSING`,
and `CL_RPATH_ABSOLUTE` continue to drive JSON summaries and `--fail-on`.

## RPM Package Scanning

CompatLab accepts RPM (`.rpm`) packages in the existing `scan` and `compare`
commands. RPM scanning is static: CompatLab reads package metadata, inspects the
payload, discovers native ELF files, safely extracts only those native entries
into a temporary directory, and reuses the existing ELF scanner and compatibility
rules for each entry.

```bash
uv run compatlab scan ./dist/example-1.0.0-1.x86_64.rpm

uv run compatlab compare ./dist/example-1.0.0-1.x86_64.rpm \
  --target ubuntu-2204

uv run compatlab compare ./dist/example-1.0.0-1.x86_64.rpm \
  --target-file ./profiles/prod.yaml \
  --json report.json \
  --html report.html
```

RPM reports include package metadata, payload file counts, native ELF entry
details, package-level diagnostics, and per-entry compatibility diagnostics.
CompatLab does not install the RPM, execute package scripts, run payload
binaries, solve YUM/DNF dependencies, or perform vulnerability scanning.

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

## Docker Runtime Presets

CompatLab can generate a profile from a temporary Docker runtime environment
after installing a predefined runtime package preset. The source image is not
mutated, committed, or saved. CompatLab creates a temporary container, installs
the selected preset packages inside that container, exports the resulting rootfs,
and reuses the Docker image profile detection pipeline.

```bash
uv run compatlab profiles runtime-presets list
uv run compatlab profiles runtime-presets show cpp-runtime

uv run compatlab profiles generate \
  --from-image ubuntu:22.04 \
  --runtime-preset cpp-runtime \
  --name ubuntu-2204-cpp-runtime \
  --output /tmp/ubuntu-2204-cpp-runtime.yaml
```

Built-in v0.6 presets:

- `cpp-runtime`: common C/C++ runtime libraries;
- `python-runtime`: common Python 3 runtime libraries.

Runtime preset installation currently supports `apt-get`, `dnf`, and `yum`
based images.

## Bundle Dependency Resolution

CompatLab can resolve local shared-library dependencies inside an application
bundle. Use `--bundle-root` to point at the directory being shipped and
`--recursive` to follow transitive `DT_NEEDED` dependencies:

```bash
uv run compatlab compare ./dist/my-app \
  --target-file /tmp/ubuntu-2204-cpp-runtime.yaml \
  --bundle-root ./dist \
  --recursive
```

The resolver checks `RUNPATH`, `RPATH`, common bundle library directories such
as `lib/` and `lib64/`, and `$ORIGIN`-relative layouts. The terminal report
shows whether each dependency comes from the bundle, the target profile, or is
missing/ambiguous. JSON reports include a `dependency_graph` with nodes, edges,
resolution kind, candidates, and unresolved dependencies.

Conservative limits are available for large bundles:

```bash
uv run compatlab scan ./dist/my-app --bundle-root ./dist --recursive --max-depth 10 --max-files 500
```

## Diagnostics and CI Gates

CompatLab JSON reports include a stable `summary` object and normalized
`diagnostics` issues for scripts and CI systems. Diagnostics use stable codes
such as `CL_LIB_MISSING`, `CL_SYMBOL_GLIBCXX_TOO_NEW`, and
`CL_RPATH_ABSOLUTE`.

Use `--fail-on` to decide which diagnostics should fail a CI job:

- `error`: fail when at least one error diagnostic exists; this is the default;
- `warning`: fail when at least one warning or error diagnostic exists;
- `never`: do not fail because of diagnostics if the command completed.

```bash
uv run compatlab compare ./dist/my-app \
  --target ubuntu-2204 \
  --bundle-root ./dist \
  --recursive \
  --fail-on warning
```

```bash
uv run compatlab compare ./dist/my-app \
  --target-file ./profiles/prod.yaml \
  --bundle-root ./dist \
  --recursive \
  --fail-on never \
  --json report.json
```

Reports include counters and issue-code totals:

```json
{
  "summary": {
    "status": "failed",
    "errors": 1,
    "warnings": 1,
    "infos": 0,
    "issue_codes": {
      "CL_LIB_MISSING": 1,
      "CL_RPATH_ABSOLUTE": 1
    }
  },
  "diagnostics": []
}
```

## MVP Scope

The first MVP is intentionally narrow:

- one ELF binary or shared library as input;
- optional local bundle root with recursive ELF dependency resolution;
- one target profile in YAML;
- pretty terminal output with Rich;
- JSON reports based on Pydantic models;
- Typer-based CLI suitable for CI;
- target profiles for common Linux baselines;
- generated target profiles from the current system, Docker image rootfs, or a
  temporary Docker runtime preset environment;
- problem taxonomy ready for compatibility diagnostics.

## Not In Scope Yet

CompatLab does not add arbitrary package installation, Dockerfile generation,
Docker image mutation/commit, web UI, database, daemon, wheel/RPM/DEB analysis,
SBOM/security scanning, automatic patching, or a Go implementation. Those are
explicitly outside the current implementation pass.

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
