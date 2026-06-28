# CompatLab + ArtifactDoctor: handoff for Codex agent

Date: 2026-06-28
Target release: `v0.5`
Working language for code comments, docs, README, and release notes: English by default, unless the touched file already uses Russian.
Project owner preference: keep the project practical, CLI-first, narrow, and testable. Avoid architectural heroism.

---

## 1. What this project is

**CompatLab ArtifactDoctor** is a Python-first command-line tool for checking whether a Linux binary artifact is likely to run on a target Linux system before it is shipped.

The tool scans Linux ELF artifacts, extracts low-level facts, then compares them with a target profile. The diagnosis should explain problems such as:

- required `GLIBC_*` version is newer than the target provides;
- required `GLIBCXX_*` version is newer than the target provides;
- required `CXXABI_*` version is newer than the target provides;
- wrong architecture;
- missing dynamic linker/interpreter;
- direct `DT_NEEDED` library is absent from the target profile;
- suspicious `RPATH` / `RUNPATH` values.

The project is intentionally CLI-first. Do not turn it into a web service, daemon, database-backed application, package manager, security scanner, SBOM tool, or automatic patching tool.

---

## 2. Existing release history

### v0.1: project skeleton

Implemented:

- `src`-style Python package layout;
- Typer-based CLI;
- Rich terminal output;
- Pydantic models for artifact reports, ELF facts, target profiles, and compatibility problems;
- JSON output for `scan` and `compare`;
- built-in YAML target profiles:
  - `ubuntu-1804`
  - `ubuntu-2004`
  - `ubuntu-2204`
  - `ubuntu-2404`
  - `rocky-9`
  - `astra-17`
  - `sberlinux-9`
- basic tests;
- Ruff and Makefile developer commands.

Initial CLI:

```bash
compatlab scan PATH
compatlab compare PATH --target TARGET
compatlab profiles list
compatlab profiles show TARGET
```

### v0.2: real ELF scanner

Implemented a real scanner based on system `readelf`.

Important implementation details:

- safe subprocess runner;
- no `shell=True`;
- timeout support;
- captured stdout/stderr/return code;
- stable `LC_ALL=C` / `LANG=C` command environment;
- graceful behavior when a command is missing or fails;
- parsers for:
  - `readelf -h`
  - `readelf -l`
  - `readelf -d`
  - `readelf --version-info`

Extracted ELF facts include:

- ELF class;
- endianness;
- OS ABI;
- machine/architecture;
- ELF type;
- entry point;
- dynamic/static signal;
- program interpreter from `PT_INTERP`;
- `DT_NEEDED` libraries;
- `RPATH`;
- `RUNPATH`;
- required `GLIBC_*`, `GLIBCXX_*`, and `CXXABI_*` symbol versions.

Important behavior:

```bash
compatlab scan /bin/bash
```

returns scan facts only. It does not decide compatibility. Compatibility belongs to `compare`, where a target profile is available.

### v0.3: compatibility comparison engine

Implemented real compatibility comparison for ELF artifacts.

`compatlab compare PATH --target TARGET` now:

1. scans the artifact with the existing `readelf` backend;
2. loads the target YAML profile;
3. applies compatibility rules;
4. reports explainable problems/warnings;
5. writes JSON when requested;
6. returns CI-friendly exit codes.

Implemented problems:

- `wrong.architecture`
- `missing.interpreter`
- `profile.interpreter_not_provided`
- `glibc.too_new`
- `glibcxx.too_new`
- `cxxabi.too_new`
- `profile.library_not_provided`

Implemented warnings:

- `bad.rpath.absolute`
- `bad.rpath.build_path`
- `bad.runpath.absolute`
- `bad.runpath.build_path`

Exit codes:

- `0` when no `HIGH` or `CRITICAL` compatibility problems are found;
- `1` when a `HIGH` or `CRITICAL` compatibility problem is found;
- `2` when the profile is invalid/missing or the artifact cannot be scanned as ELF.

### v0.4: automatic profile generation from current Linux system

Implemented current-system detection and YAML profile generation.

Important features now available:

```bash
compatlab profiles detect
compatlab profiles detect --json PATH
compatlab profiles generate --from-current --name NAME --output PATH
compatlab profiles validate PROFILE.yaml
compatlab profiles validate PROFILE.yaml --json PATH
compatlab compare PATH --target-file PROFILE.yaml
```

v0.4 added:

- raw `SystemFacts` model;
- `/etc/os-release` parser;
- current architecture detection;
- best-effort glibc detection from `ldd --version`;
- `ldconfig -p` parser;
- dynamic linker detection;
- available symbol-version extraction from system libraries:
  - `GLIBC_*` from `libc.so.6`;
  - `GLIBCXX_*` from `libstdc++.so.6`;
  - `CXXABI_*` from `libstdc++.so.6`;
- target profile generation from `SystemFacts`;
- optional metadata in generated YAML;
- explicit external profile comparison through `--target-file`;
- profile validation command;
- fixture and CLI tests.

Verified at v0.4:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run compatlab profiles detect
uv run compatlab profiles detect --json /tmp/system-facts.json
uv run compatlab profiles generate --from-current --name local --output /tmp/local.yaml
uv run compatlab profiles validate /tmp/local.yaml
uv run compatlab compare /bin/bash --target-file /tmp/local.yaml
make check
```

Expected v0.4 test result: `38 passed`.
Current v0.4 coverage: `TOTAL 81%`.

---

## 3. Why v0.5 exists

v0.4 made profile generation work for the **current host system**.

The next useful step is generating target profiles from **Docker images**.

Main v0.5 idea:

> Generate a CompatLab target YAML profile from a Docker image, without requiring the user to manually write profile fields and without requiring the Docker image to contain Python, `readelf`, or development tooling.

Example target workflow:

```bash
uv run compatlab profiles generate \
  --from-image ubuntu:22.04 \
  --name ubuntu-2204-docker \
  --output /tmp/ubuntu-2204.yaml

uv run compatlab profiles validate /tmp/ubuntu-2204.yaml
uv run compatlab compare ./dist/my-app --target-file /tmp/ubuntu-2204.yaml
```

This makes the product much more practical: users can generate profiles for common Linux baselines from container images and then use those profiles in CI.

---

## 4. v0.5 primary goal

Implement Docker image target profile generation.

Primary deliverable:

```bash
compatlab profiles generate --from-image IMAGE --name NAME --output PATH
```

Recommended deliverable:

```bash
compatlab profiles detect --from-image IMAGE --json PATH
```

Optional but useful CLI options:

```bash
--platform linux/amd64
--pull
--timeout SECONDS
--facts-json PATH
```

Do not implement all optional flags if they make the release too large. The required goal is one reliable image-to-YAML flow with tests.

---

## 5. Important design decision for v0.5

Do **not** assume the Docker image contains:

- Python;
- `readelf`;
- `ldconfig`;
- `ldd`;
- `find`;
- package manager tools;
- shell utilities beyond the absolute minimum.

The safest v0.5 approach is:

1. Use the host Docker CLI to create a temporary container from the image.
2. Export the container filesystem as a rootfs tar archive.
3. Parse the rootfs tar archive from Python.
4. Extract selected libraries to temporary host files.
5. Run the existing host-side `readelf` logic on extracted libraries.
6. Convert discovered facts into `SystemFacts`.
7. Reuse the existing v0.4 `SystemFacts -> TargetProfile -> YAML` flow.

This avoids installing anything inside the image and keeps the detection logic deterministic.

Suggested internal flow:

```text
Docker image
  -> docker image inspect
  -> docker create temporary container
  -> docker export temporary container to rootfs tar
  -> docker rm temporary container in finally block
  -> parse /etc/os-release from tar
  -> list libraries and dynamic linkers from tar entries
  -> extract libc.so.6 / libstdc++.so.6 candidates to temp dir
  -> host readelf --version-info on extracted libraries
  -> SystemFacts(source_type=docker-image)
  -> TargetProfile
  -> YAML
```

---

## 6. Proposed CLI behavior

### Required command

```bash
compatlab profiles generate --from-image IMAGE --name NAME --output PATH
```

Example:

```bash
uv run compatlab profiles generate \
  --from-image ubuntu:22.04 \
  --name ubuntu-2204-docker \
  --output /tmp/ubuntu-2204.yaml
```

Expected behavior:

- image exists locally: use it;
- image does not exist locally: report a clear error unless `--pull` is implemented and provided;
- Docker CLI missing/unavailable: report clear error;
- Docker daemon unavailable: report clear error;
- profile generation fails validation: report clear error;
- temporary container is removed even when detection fails.

### Recommended debug command

```bash
compatlab profiles detect --from-image IMAGE --json PATH
```

Example:

```bash
uv run compatlab profiles detect \
  --from-image ubuntu:22.04 \
  --json /tmp/ubuntu-2204-facts.json
```

This should export raw facts for debugging Docker-image detection.

If extending `profiles detect` is awkward, implement this as a separate internal path first and expose only `profiles generate --from-image` in v0.5. But raw facts export is strongly recommended because it makes failures easier to understand.

### Optional `--pull`

If implemented:

```bash
compatlab profiles generate --from-image ubuntu:22.04 --pull --name ubuntu-2204 --output ubuntu-2204.yaml
```

Suggested behavior:

- without `--pull`, do not pull images automatically;
- with `--pull`, call `docker pull IMAGE` before `docker create`;
- keep error messages clean and concise.

### Optional `--platform`

If implemented:

```bash
compatlab profiles generate \
  --from-image ubuntu:22.04 \
  --platform linux/amd64 \
  --name ubuntu-2204-amd64 \
  --output ubuntu-2204-amd64.yaml
```

Use the platform value for Docker create/pull when supported by the existing command wrapper.

Do not over-engineer multi-architecture support in v0.5. A simple pass-through platform option is enough.

---

## 7. Metadata expected in generated profiles

Generated YAML profiles already support optional metadata from v0.4. Extend it for Docker source information.

Suggested metadata fields:

```yaml
metadata:
  generator: compatlab
  generated_at: "2026-06-28T00:00:00Z"
  source_type: docker-image
  source_image: ubuntu:22.04
  source_image_id: sha256:...
  source_os_id: ubuntu
  source_os_version_id: "22.04"
  detection_backend: docker-rootfs-export
  platform: linux/amd64
```

Do not break built-in profiles that do not have metadata.

If the current metadata model has different field names, reuse the existing naming style instead of inventing a parallel schema.

---

## 8. Implementation guidance

### First inspect the repository

Before coding, inspect:

```bash
find src -type f | sort
find tests -type f | sort
```

Find existing locations for:

- Typer CLI app;
- `profiles` subcommands;
- `SystemFacts` model;
- `TargetProfile` model;
- YAML profile loader/validator;
- current-system detector;
- generator `SystemFacts -> TargetProfile`;
- command runner introduced/generalized in v0.4;
- `readelf --version-info` parser;
- version comparison helpers;
- fixture layout.

Reuse existing code. Do not create a second profile model, second YAML loader, second version parser, or second command runner.

### Suggested new modules

Adjust names to match the actual project structure.

Possible layout:

```text
src/compatlab/profiles/
  docker_image.py       # high-level Docker image detection flow
  docker_cli.py         # small Docker CLI wrapper around existing command runner
  rootfs_tar.py         # parse exported rootfs tar archive
  rootfs_facts.py       # rootfs -> SystemFacts helpers, if useful
```

Potential tests:

```text
tests/test_docker_cli.py
tests/test_rootfs_tar.py
tests/test_profiles_generate_from_image.py
tests/test_profiles_detect_from_image.py
```

Fixture examples:

```text
tests/fixtures/docker_rootfs/
  ubuntu_2204_rootfs.tar
  rocky_9_rootfs.tar
  docker_image_inspect_ubuntu_2204.json
```

Do not add huge binary fixtures. If tar fixtures become too large, build minimal tar archives dynamically in tests using Python `tarfile`.

### Docker CLI wrapper

Use the existing safe command runner if possible.

Rules:

- no `shell=True`;
- pass command as list of arguments;
- support timeout;
- capture stdout/stderr/return code;
- make error messages user-readable;
- do not leak temporary container IDs unless useful for debugging;
- always clean up temporary containers.

Suggested Docker commands:

```bash
docker image inspect IMAGE
# optional:
docker pull IMAGE

docker create IMAGE
# optional platform:
docker create --platform linux/amd64 IMAGE

docker export CONTAINER_ID --output /tmp/compatlab-rootfs.tar
docker rm CONTAINER_ID
```

Use `finally` to remove the container:

```text
create container
try:
    export rootfs
    parse facts
finally:
    docker rm -f container_id
```

### Rootfs tar parsing

Use Python `tarfile`.

Parse these from the exported rootfs:

- `/etc/os-release`
- common dynamic linker paths:
  - `/lib64/ld-linux-x86-64.so.2`
  - `/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2`
  - `/lib/ld-linux.so.2`
  - `/lib/ld-linux-aarch64.so.1`
- library entries under common directories:
  - `/lib`
  - `/lib64`
  - `/usr/lib`
  - `/usr/lib64`
  - architecture-specific subdirectories such as `/lib/x86_64-linux-gnu`

Candidate libraries for symbol extraction:

- `libc.so.6`
- `libstdc++.so.6`

Important: tar entries may be regular files or symlinks. Preserve enough information to list provided library basenames and resolve symlink targets where practical.

Keep v0.5 best-effort. It does not need to perfectly emulate a dynamic linker.

### Symbol version extraction

Prefer this approach:

1. Extract `libc.so.6` candidate from rootfs tar to a temporary host file.
2. Run host `readelf --version-info` on that extracted file.
3. Reuse existing symbol-version parser.
4. Extract max `GLIBC_*`.
5. Repeat for `libstdc++.so.6` and extract max `GLIBCXX_*` and `CXXABI_*`.

Do not require `readelf` inside the Docker image.

If host `readelf` is missing, report a clear warning/error consistent with current scanner behavior.

### Architecture detection

Prefer Docker image metadata first:

```bash
docker image inspect IMAGE
```

Expected useful fields:

- `Architecture`
- `Os`
- possibly `RepoDigests`
- image ID

Normalize architecture through existing normalization helpers where possible.

Fallback: derive architecture from extracted ELF files with existing `readelf -h` parser, if easy.

Do not spend too much v0.5 time on perfect multi-arch behavior.

---

## 9. Tests required for v0.5

### Unit tests without Docker

Must be possible to run the main test suite without Docker installed.

Required tests should mock command execution and use tar fixtures/dynamic tar creation.

Test cases:

1. Docker command wrapper builds expected argument lists.
2. Temporary container is removed when export succeeds.
3. Temporary container is removed when export fails.
4. Missing Docker produces a clear failure path.
5. Image inspect JSON is parsed into source metadata.
6. Rootfs tar parser extracts `/etc/os-release`.
7. Rootfs tar parser lists library basenames.
8. Rootfs tar parser detects common dynamic linker paths.
9. Rootfs tar parser extracts `libc.so.6` candidate for host readelf analysis.
10. Docker image facts convert into a valid `TargetProfile`.
11. Generated YAML from image validates through existing `profiles validate` path.
12. CLI test for `profiles generate --from-image` with mocked backend.
13. CLI test for clear error when Docker image detection fails.

### Optional integration test with Docker

If a test is added that really calls Docker, it must be skipped automatically when Docker is unavailable.

Suggested command for manual verification, not mandatory CI:

```bash
uv run compatlab profiles generate \
  --from-image ubuntu:22.04 \
  --name ubuntu-2204-docker \
  --output /tmp/ubuntu-2204-docker.yaml

uv run compatlab profiles validate /tmp/ubuntu-2204-docker.yaml
```

If `--pull` is implemented:

```bash
uv run compatlab profiles generate \
  --from-image ubuntu:22.04 \
  --pull \
  --name ubuntu-2204-docker \
  --output /tmp/ubuntu-2204-docker.yaml
```

---

## 10. User-facing output expectations

For successful image generation, output should be compact and useful:

```text
Docker image profile generated

Image:        ubuntu:22.04
Name:         ubuntu-2204-docker
Architecture: x86_64
OS:           Ubuntu 22.04
Output:       /tmp/ubuntu-2204-docker.yaml
```

For failure, avoid Python tracebacks in normal CLI use:

```text
Error: Docker is not available. Install Docker or run this command on a host with access to Docker daemon.
```

or:

```text
Error: Docker image 'ubuntu:22.04' is not available locally. Pull it first or rerun with --pull.
```

Keep errors actionable.

---

## 11. v0.5 non-goals

Do **not** implement these in v0.5:

- runtime profile presets with package installation;
- installing packages inside Docker images;
- mutating Docker images;
- generating custom Dockerfiles;
- rootfs scanning as a public standalone feature;
- scanning artifacts inside Docker containers;
- recursive dependency resolution;
- local filesystem dependency resolution for scanned artifacts;
- Wheel/RPM/DEB package scanning;
- HTML reports;
- web UI;
- database;
- daemon/server mode;
- `patchelf` automatic patching;
- Go helper implementation.

Runtime profiles with installed typical packages should be a later release, likely v0.6.

---

## 12. Recommended task breakdown for Codex

Work in small commits/steps. After each meaningful step, run tests and Ruff.

### Step 1: inspect current code

No code changes yet.

Find the existing CLI, profile models, current-system detection code, YAML validation, command runner, and `readelf` parser.

Produce a short implementation plan before editing.

### Step 2: add rootfs tar parsing helpers

Implement pure functions/classes for reading an exported rootfs tar archive:

- read file content by path;
- parse `/etc/os-release` from tar;
- list library basenames;
- detect dynamic linker paths;
- extract candidate libraries to a temp directory.

Add unit tests using dynamically created tar fixtures.

Run:

```bash
uv run pytest tests/test_rootfs_tar.py
uv run ruff check .
uv run ruff format --check .
```

### Step 3: add Docker CLI wrapper

Implement a small wrapper over existing safe command runner:

- image inspect;
- optional pull;
- create container;
- export container rootfs;
- remove container.

Add tests with mocked command runner.

Run relevant tests.

### Step 4: add Docker image detection flow

Implement high-level detection:

```text
image -> exported rootfs -> SystemFacts -> TargetProfile
```

Reuse existing v0.4 generator logic.

Add metadata fields for Docker image source.

### Step 5: add CLI support

Add:

```bash
compatlab profiles generate --from-image IMAGE --name NAME --output PATH
```

Prefer making `--from-current` and `--from-image` mutually exclusive.

If adding `profiles detect --from-image IMAGE --json PATH`, keep output consistent with current-system detection.

### Step 6: documentation and release notes

Update README with Docker image generation example.

Create or update release notes for v0.5.

Mention clearly what is not included yet.

### Step 7: full verification

Run:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
make check
```

Manual Docker verification if Docker is available:

```bash
uv run compatlab profiles generate \
  --from-image ubuntu:22.04 \
  --name ubuntu-2204-docker \
  --output /tmp/ubuntu-2204-docker.yaml

uv run compatlab profiles validate /tmp/ubuntu-2204-docker.yaml
```

If `--pull` exists:

```bash
uv run compatlab profiles generate \
  --from-image ubuntu:22.04 \
  --pull \
  --name ubuntu-2204-docker \
  --output /tmp/ubuntu-2204-docker.yaml
```

---

## 13. Definition of done for v0.5

v0.5 is done when:

- `profiles generate --from-image IMAGE --name NAME --output PATH` exists;
- generated Docker-image profiles validate with `profiles validate`;
- generated Docker-image profiles can be passed to `compare --target-file`;
- Docker interaction is isolated behind a small wrapper;
- temporary containers are always cleaned up;
- main tests do not require Docker to be installed;
- optional Docker integration tests are skipped when Docker is unavailable;
- README contains a concise Docker image profile generation example;
- release notes describe v0.5 behavior and non-goals;
- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, and `make check` pass.

---

## 14. First message suggestion from project owner to Codex

Use this as the first message when starting the v0.5 development session:

```text
Read compatlab_codex_handoff_v0_5.md carefully.
We are developing CompatLab ArtifactDoctor v0.5.
The goal is Docker image profile generation.

Do not start by editing code.
First inspect the repository structure, find the existing v0.4 current-system detection, SystemFacts, TargetProfile generation, profile validation, command runner, and readelf parser.
Then propose a short implementation plan.

Important constraints:
- do not require Python/readelf/ldconfig inside Docker images;
- prefer docker create + docker export + host-side tar parsing/readelf;
- do not implement runtime package presets in v0.5;
- do not implement package scanning, web UI, database, daemon, or patchelf patching;
- tests must not require Docker by default.

Start with rootfs tar parser helpers and unit tests.
```
