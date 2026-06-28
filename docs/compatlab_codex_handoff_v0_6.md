# CompatLab ArtifactDoctor v0.6 — Codex Handoff Specification

## Purpose of this document

This document is a handoff for a coding agent working on the next development
iteration of **CompatLab ArtifactDoctor**.

The agent should treat this as a task specification, not as a request to redesign
the whole project. The goal is to implement a focused v0.6 release on top of the
existing v0.1–v0.5 codebase.

---

## Project summary

**CompatLab ArtifactDoctor** is a Python-first CLI tool for checking whether a
Linux binary artifact is likely to run on a target Linux profile before it is
shipped.

The core product idea:

> Scan an ELF artifact, extract compatibility-relevant facts, compare those facts
> with a target Linux profile, and report explainable compatibility problems.

The tool currently works with:

- single ELF binaries or shared libraries;
- YAML target profiles;
- built-in target profiles;
- generated profiles from the current Linux system;
- generated profiles from Docker images;
- terminal output through Rich;
- JSON reports;
- Typer-based CLI;
- Pydantic models;
- test-first parser/fixture design.

---

## Current version history

### v0.1

Initial CLI and project skeleton:

- `compatlab scan PATH`;
- `compatlab compare PATH --target TARGET`;
- `compatlab profiles list`;
- `compatlab profiles show TARGET`;
- YAML target profile model;
- built-in profiles;
- JSON report plumbing;
- basic smoke tests.

### v0.2

First real ELF scanner:

- `readelf` backend;
- parsers for ELF header, program headers, dynamic section, symbol versions;
- extraction of:
  - architecture;
  - interpreter;
  - `DT_NEEDED`;
  - `RPATH`;
  - `RUNPATH`;
  - required `GLIBC_*`, `GLIBCXX_*`, `CXXABI_*`;
- scan warnings and fixture tests.

### v0.3

First real comparison engine:

- `compatlab compare PATH --target TARGET` runs scanner and compatibility checks;
- architecture checks;
- interpreter checks;
- glibc/libstdc++/CXXABI version checks;
- direct library availability checks;
- suspicious `RPATH`/`RUNPATH` warnings;
- CI-friendly exit codes.

### v0.4

Automatic current-system profile generation:

- `SystemFacts` model;
- current host detection from:
  - `/etc/os-release`;
  - Python platform facts;
  - `ldd --version`;
  - `ldconfig -p`;
  - common dynamic linker paths;
  - host-side `readelf` for available symbol versions;
- `compatlab profiles detect`;
- `compatlab profiles detect --json PATH`;
- `compatlab profiles generate --from-current --name NAME --output PATH`;
- `compatlab profiles validate PROFILE.yaml`;
- `compatlab compare PATH --target-file PROFILE.yaml`.

### v0.5

Docker image profile generation:

- rootfs tar parsing helpers for exported Docker filesystems;
- Docker CLI wrapper around the safe command runner;
- `docker image inspect`;
- optional `docker pull`;
- `docker create`;
- `docker export`;
- cleanup through `docker rm -f`;
- Docker image detection without requiring Python, `readelf`, or `ldconfig`
  inside the image;
- host-side `readelf` on extracted libraries;
- `compatlab profiles generate --from-image IMAGE --name NAME --output PATH`;
- `--pull`;
- `--platform`;
- `compatlab profiles detect --from-image IMAGE --json PATH`;
- Docker-source metadata in generated profiles.

---

## v0.6 release theme

### Recommended release name

**CompatLab ArtifactDoctor 0.6 — Docker runtime profile presets**

### Main goal

Teach CompatLab to generate a target profile not only from a plain Docker image,
but also from a **temporary runtime environment** based on that image after
installing a predefined set of runtime packages.

In plain terms:

- v0.5 can answer: “What does this Docker image provide by default?”
- v0.6 should answer: “What would this target environment provide after installing
  a known runtime preset, such as C++ runtime or Python runtime?”

This is useful because many base images are too minimal. A real production target
often has additional runtime packages installed.

---

## Important product boundary

v0.6 may install packages into a **temporary Docker container**.

v0.6 must not:

- mutate the original Docker image;
- commit a modified Docker image;
- generate Dockerfiles;
- become a package manager abstraction framework;
- scan RPM/DEB/Wheel files directly;
- add recursive artifact dependency resolution;
- add web UI/database/server mode;
- add automatic patching.

Keep the release narrow.

---

## Target user workflow

The target user should be able to run:

```bash
uv run compatlab profiles runtime-presets list
```

Example output:

```text
Available runtime presets:

  cpp-runtime       Common C/C++ runtime libraries
  python-runtime    Python runtime libraries
```

Then generate a runtime-aware profile:

```bash
uv run compatlab profiles generate \
  --from-image ubuntu:22.04 \
  --runtime-preset cpp-runtime \
  --name ubuntu-2204-cpp-runtime \
  --output /tmp/ubuntu-2204-cpp-runtime.yaml
```

Validate it:

```bash
uv run compatlab profiles validate /tmp/ubuntu-2204-cpp-runtime.yaml
```

Use it:

```bash
uv run compatlab compare ./dist/my-app \
  --target-file /tmp/ubuntu-2204-cpp-runtime.yaml
```

Export raw facts for debugging:

```bash
uv run compatlab profiles detect \
  --from-image ubuntu:22.04 \
  --runtime-preset cpp-runtime \
  --json /tmp/ubuntu-2204-cpp-runtime-facts.json
```

Optional pull and platform selection should continue to work:

```bash
uv run compatlab profiles generate \
  --from-image ubuntu:22.04 \
  --runtime-preset python-runtime \
  --pull \
  --platform linux/amd64 \
  --name ubuntu-2204-python-runtime \
  --output /tmp/ubuntu-2204-python-runtime.yaml
```

---

## Proposed CLI additions

### 1. List runtime presets

```bash
compatlab profiles runtime-presets list
```

This command should list built-in runtime presets.

### 2. Show one runtime preset

```bash
compatlab profiles runtime-presets show cpp-runtime
```

This should print:

- preset name;
- description;
- supported OS families;
- package manager families;
- package names per family;
- known limitations.

### 3. Generate from Docker image with runtime preset

Extend existing command:

```bash
compatlab profiles generate \
  --from-image IMAGE \
  --runtime-preset PRESET \
  --name NAME \
  --output PATH
```

Rules:

- `--runtime-preset` is valid only with `--from-image`.
- `--runtime-preset` is invalid with `--from-current`.
- `--runtime-preset` is optional.
- Existing v0.5 behavior without `--runtime-preset` must continue unchanged.

### 4. Detect Docker image with runtime preset

Extend existing command:

```bash
compatlab profiles detect \
  --from-image IMAGE \
  --runtime-preset PRESET \
  --json PATH
```

Rules:

- same source selector rules as `profiles generate`;
- raw exported facts should include runtime preset metadata.

---

## Suggested built-in runtime presets

Start small. Do not try to model every possible runtime.

### Preset: `cpp-runtime`

Purpose:

> Common C/C++ runtime libraries used by dynamically linked C and C++ programs.

Suggested packages:

Debian/Ubuntu:

```text
libstdc++6
libgcc-s1
```

RHEL/Rocky/SberLinux-like:

```text
libstdc++
libgcc
```

### Preset: `python-runtime`

Purpose:

> Common Python 3 runtime libraries.

Suggested packages:

Debian/Ubuntu:

```text
python3
libpython3-stdlib
```

RHEL/Rocky/SberLinux-like:

```text
python3
python3-libs
```

### Optional preset: `postgres-client-runtime`

Only add this if the main architecture is already clean.

Purpose:

> Runtime libraries commonly needed by applications linking to PostgreSQL client
> libraries.

Suggested packages:

Debian/Ubuntu:

```text
libpq5
```

RHEL/Rocky/SberLinux-like:

```text
libpq
```

This preset is optional. Do not block v0.6 on it.

---

## Supported package manager families

For v0.6, support only:

- `apt-get`;
- `dnf`;
- `yum`.

Do not add Alpine `apk` support in the first pass. Alpine uses musl libc, while
CompatLab’s current compatibility checks are centered on glibc/libstdc++ symbol
versions. Alpine support should be a separate design topic.

---

## Runtime installation strategy

Use a temporary Docker container. Do not mutate the source image.

Recommended high-level flow:

1. Optionally pull the image if `--pull` is set.
2. Inspect the image with existing Docker image metadata logic.
3. Detect the base OS/package manager.
4. Resolve runtime preset packages for that OS/package manager family.
5. Create a temporary container.
6. Run a package installation command inside that temporary container.
7. Export the resulting container rootfs.
8. Reuse the v0.5 rootfs tar parsing path.
9. Convert resulting `SystemFacts` into `TargetProfile`.
10. Add runtime metadata.
11. Cleanup temporary container in `finally`.

The source image must remain unchanged.

---

## Docker command orchestration options

Prefer simple Docker CLI operations that are easy to test with mocks.

One possible approach:

```bash
docker create --platform linux/amd64 --name compatlab-... IMAGE sh -c '<install script>'
docker start --attach compatlab-...
docker export compatlab-... > rootfs.tar
docker rm -f compatlab-...
```

Another acceptable approach:

```bash
docker create --platform linux/amd64 --name compatlab-... IMAGE sh
docker start compatlab-...
docker exec compatlab-... sh -c '<install script>'
docker export compatlab-... > rootfs.tar
docker rm -f compatlab-...
```

Choose the approach that fits the existing v0.5 Docker wrapper best.

Important cleanup rule:

- Always remove the temporary container in `finally`.
- If installation fails, report a clear error and still cleanup.

---

## Package manager command generation

Implement this as isolated, testable logic.

Suggested shape:

```python
def build_install_script(package_manager: str, packages: list[str]) -> str:
    ...
```

Expected scripts:

### apt-get

```sh
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends libstdc++6 libgcc-s1
rm -rf /var/lib/apt/lists/*
```

### dnf

```sh
dnf install -y --setopt=install_weak_deps=False libstdc++ libgcc
dnf clean all
```

### yum

```sh
yum install -y libstdc++ libgcc
yum clean all
```

Do not use shell string concatenation carelessly. Package names should come from
trusted built-in preset definitions, not from arbitrary user input in v0.6.

---

## Package manager detection

Keep this pragmatic.

Potential sources:

1. `/etc/os-release` from the image/rootfs;
2. known OS family mapping:
   - `ubuntu`, `debian` -> `apt-get`;
   - `rocky`, `rhel`, `centos`, `fedora`, `sberlinux` -> `dnf` or `yum`;
3. optionally, checking whether package manager binaries exist in rootfs:
   - `/usr/bin/apt-get`;
   - `/usr/bin/dnf`;
   - `/usr/bin/yum`.

Do not over-engineer this. If unsupported, fail clearly:

```text
Runtime preset installation is not supported for image IMAGE:
could not detect a supported package manager.
Supported package managers: apt-get, dnf, yum.
```

---

## Data model additions

Add a small model for runtime presets.

Example:

```python
class RuntimePreset(BaseModel):
    name: str
    description: str
    packages_by_family: dict[str, list[str]]
    supported_package_managers: list[str]
```

Add runtime metadata either to existing profile metadata model or to the existing
metadata dictionary, depending on how the current code is structured.

Suggested metadata fields in generated YAML:

```yaml
metadata:
  generator: compatlab
  generated_at: "2026-06-28T..."
  source_type: docker-runtime-image
  source_image: ubuntu:22.04
  source_image_id: sha256:...
  platform: linux/amd64
  detection_backend: docker-runtime-rootfs-export
  runtime_preset: cpp-runtime
  runtime_packages:
    - libstdc++6
    - libgcc-s1
  package_manager: apt-get
```

Do not break compatibility with old built-in profiles where metadata may be
absent.

---

## Implementation tasks

### Task 1 — inspect current project

Before writing code, inspect:

- Typer CLI entrypoint;
- `profiles` command group;
- `SystemFacts` model;
- `TargetProfile` model;
- current-system detection path;
- Docker image detection path from v0.5;
- rootfs tar parser;
- Docker wrapper;
- YAML profile generator;
- metadata generation;
- test layout and fixture style.

Do not start with a large refactor.

### Task 2 — add runtime preset registry

Implement:

- built-in preset definitions;
- lookup by name;
- list presets;
- show preset;
- useful error for unknown preset.

Tests:

- known preset lookup;
- unknown preset error;
- list contains `cpp-runtime` and `python-runtime`;
- package definitions are stable.

### Task 3 — add package manager detection

Implement helper that can resolve a supported package manager from rootfs facts.

Tests:

- Ubuntu/Debian -> `apt-get`;
- Rocky/RHEL-like -> `dnf` or `yum`;
- unsupported OS -> clear failure;
- missing package manager info -> clear failure.

### Task 4 — add install script builder

Implement isolated script generation.

Tests:

- apt-get script contains update/install/cleanup;
- dnf script contains install/clean;
- yum script contains install/clean;
- empty package list is rejected or handled explicitly.

### Task 5 — extend Docker backend with runtime container flow

Add a new Docker detection/generation branch for:

```text
from image + runtime preset
```

Reuse existing v0.5 rootfs parsing once the temporary container is exported.

Tests should mock Docker command calls. Do not require real Docker for unit tests.

Validate command order approximately:

1. inspect/pull if needed;
2. create container;
3. run/start/exec install command;
4. export;
5. cleanup.

### Task 6 — extend CLI

Add:

```bash
compatlab profiles runtime-presets list
compatlab profiles runtime-presets show PRESET
```

Extend:

```bash
compatlab profiles generate --from-image IMAGE --runtime-preset PRESET ...
compatlab profiles detect --from-image IMAGE --runtime-preset PRESET --json PATH
```

Validation rules:

- `--runtime-preset` with `--from-current` -> error;
- unknown preset -> error;
- no preset -> preserve v0.5 behavior.

### Task 7 — metadata

Ensure generated profile metadata clearly shows:

- source type;
- source image;
- platform;
- runtime preset;
- runtime packages;
- package manager;
- backend name.

Tests:

- generated YAML includes runtime preset metadata;
- non-runtime Docker profile metadata remains unchanged;
- current-system profile metadata remains unchanged.

### Task 8 — optional integration tests

Add Docker integration tests only if the project already has a pattern for
optional external-tool tests.

Suggested gate:

```text
COMPATLAB_RUN_DOCKER_TESTS=1
```

Skip when:

- Docker binary is missing;
- Docker daemon is unavailable;
- image pull is unavailable.

Keep integration tests minimal, for example:

```bash
ubuntu:22.04 + cpp-runtime
```

Do not make CI depend on network or Docker daemon availability unless the project
already does that intentionally.

### Task 9 — documentation and release notes

Update README with:

- runtime preset concept;
- command examples;
- limitations;
- warning that source images are not mutated.

Create release note:

```text
v0.6.md
```

Include:

- summary;
- added;
- changed;
- current behavior;
- not included yet;
- verification;
- next step.

---

## Testing expectations

After each logical block:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Before finalizing:

```bash
make check
```

Target test count should increase from v0.5’s 55 tests.

Coverage should not collapse. Small fluctuations are acceptable, but avoid adding
large untested command orchestration code.

---

## Error handling expectations

Errors should be explicit and useful.

Examples:

```text
Docker is not available or failed to run.
```

```text
Runtime preset 'python-runtime' is not supported for this image.
```

```text
Could not detect a supported package manager in image ubuntu:22.04.
```

```text
Package installation failed in temporary container.
```

Avoid raw Python tracebacks for user-facing CLI failures.

---

## Non-goals for v0.6

Do not implement:

- arbitrary user-provided package installation;
- `--runtime-package PACKAGE` unless explicitly requested later;
- Dockerfile generation;
- Docker image commit/save;
- image mutation;
- Alpine/musl compatibility model;
- recursive dependency resolution;
- local filesystem dependency resolution for scanned artifacts;
- package file scanning for `.rpm`, `.deb`, `.whl`;
- artifact scanning inside a running container;
- HTML reports;
- web UI;
- database;
- daemon/server mode;
- automatic patching through `patchelf`;
- Go helper implementation.

---

## Recommended first commit

The best first commit is not Docker execution.

Recommended first commit:

```text
runtime preset registry + package manager script generation + unit tests
```

This keeps the first step small, deterministic, and reviewable.

---

## Suggested development order for Codex

1. Inspect current codebase.
2. Summarize where relevant v0.5 code lives.
3. Add runtime preset model/registry.
4. Add tests for preset lookup/list/show.
5. Add package manager detection helper.
6. Add install script builder.
7. Add tests.
8. Extend Docker wrapper with temporary runtime container flow.
9. Add mocked Docker orchestration tests.
10. Extend CLI.
11. Add CLI tests.
12. Add metadata tests.
13. Update README and create v0.6 release note.
14. Run full checks.

---

## Final acceptance criteria

v0.6 is complete when the following workflows work:

```bash
uv run compatlab profiles runtime-presets list
```

```bash
uv run compatlab profiles runtime-presets show cpp-runtime
```

```bash
uv run compatlab profiles generate \
  --from-image ubuntu:22.04 \
  --runtime-preset cpp-runtime \
  --name ubuntu-2204-cpp-runtime \
  --output /tmp/ubuntu-2204-cpp-runtime.yaml
```

```bash
uv run compatlab profiles validate /tmp/ubuntu-2204-cpp-runtime.yaml
```

```bash
uv run compatlab compare /bin/bash \
  --target-file /tmp/ubuntu-2204-cpp-runtime.yaml
```

```bash
uv run compatlab profiles detect \
  --from-image ubuntu:22.04 \
  --runtime-preset cpp-runtime \
  --json /tmp/ubuntu-2204-cpp-runtime-facts.json
```

And local quality checks pass:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
make check
```

---

## Message to Codex

Use this instruction when starting the agent:

```text
Read compatlab_codex_handoff_v0_6.md.

We are developing CompatLab ArtifactDoctor v0.6.
The release goal is Docker runtime profile presets: generate profiles from a
temporary Docker container after installing a predefined runtime preset.

Do not redesign the project.
Do not mutate or commit Docker images.
Do not add arbitrary user package installation.
Do not implement RPM/DEB/Wheel scanning or recursive dependency resolution.

First inspect the existing project and identify:
- CLI entrypoint;
- profile commands;
- SystemFacts and TargetProfile models;
- Docker image generation flow from v0.5;
- rootfs tar parser;
- Docker wrapper;
- metadata generation;
- tests.

Before writing code, summarize the plan.
Start implementation with runtime preset registry and install script builder
tests. Keep changes incremental and run pytest/ruff after logical blocks.
```
