# CompatLab + ArtifactDoctor: handoff for Codex agent

Date: 2026-06-28
Target release: `v0.4`
Working language for comments, docs, and release notes: English by default, unless the repository already uses Russian in a specific file.
User-facing explanation style requested by the project owner: simple, practical, no marketing fog.

---

## 1. What this project is

**CompatLab ArtifactDoctor** is a Python-first command-line tool for checking whether a Linux binary artifact is likely to run on a target Linux system before the artifact is shipped.

The project focuses on Linux binary compatibility. It scans an ELF binary or shared library, extracts low-level facts, then compares them with a target system profile.

The product goal is to turn raw ELF/system facts into an explainable diagnosis, for example:

- required `GLIBC_*` version is newer than the target system provides;
- required `GLIBCXX_*` version is newer than the target system provides;
- required `CXXABI_*` version is newer than the target system provides;
- dynamic linker/interpreter is missing or not provided by the target;
- direct `DT_NEEDED` library is missing from the target profile;
- architecture does not match;
- `RPATH`/`RUNPATH` looks suspicious.

This is intentionally a narrow CLI-first MVP. Do not expand it into a web service, database application, security scanner, package scanner, or daemon.

---

## 2. Current state before v0.4

The repository already has three implemented releases.

### v0.1

Implemented the initial Python project skeleton:

- `src`-style Python package layout;
- Typer-based CLI;
- Rich terminal output;
- Pydantic report/profile models;
- JSON output for `scan` and `compare`;
- built-in YAML target profiles;
- basic problem taxonomy;
- smoke tests;
- Ruff and Makefile developer commands.

Existing CLI surface from v0.1:

```bash
compatlab scan PATH
compatlab compare PATH --target TARGET
compatlab profiles list
compatlab profiles show TARGET
```

Built-in target profiles include:

- `ubuntu-1804`
- `ubuntu-2004`
- `ubuntu-2204`
- `ubuntu-2404`
- `rocky-9`
- `astra-17`
- `sberlinux-9`

### v0.2

Replaced the scan placeholder with a real ELF scanner based on system `readelf`.

Implemented:

- safe subprocess runner;
- no `shell=True`;
- timeout support;
- stable `LC_ALL=C` / `LANG=C` environment;
- graceful handling of missing/failing `readelf`;
- parsers for:
  - `readelf -h`
  - `readelf -l`
  - `readelf -d`
  - `readelf --version-info`
- extraction of:
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
  - required `GLIBC_*`, `GLIBCXX_*`, and `CXXABI_*` symbol versions;
- fixture-based parser tests;
- coverage tooling and `make check`.

Important behavior:

```bash
compatlab scan /bin/bash
```

returns real ELF metadata, but scan itself does not decide compatibility. Compatibility is reserved for `compare`, because `compare` has a target profile.

### v0.3

Implemented the first real compatibility comparison engine for ELF artifacts.

`compatlab compare PATH --target TARGET` now:

1. scans the artifact using the existing `readelf` backend;
2. loads the selected target YAML profile;
3. applies compatibility rules;
4. reports explainable problems and warnings;
5. writes JSON when requested;
6. returns CI-friendly exit codes.

Implemented comparison rules/problems:

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

Verified commands from v0.3:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run compatlab compare /bin/bash --target ubuntu-2404
uv run compatlab compare /bin/bash --target ubuntu-1804 --json /tmp/compare.json
jq .problems /tmp/compare.json
make check
```

Expected test result at v0.3: `21 passed`.
Current coverage at v0.3: `TOTAL 88%`.

---

## 3. Why v0.4 exists

The current weak point is target profile creation.

The project already has:

- real ELF scanning;
- real comparison rules;
- built-in YAML profiles.

But target YAML profiles are currently effectively curated manually. That limits practical value because a user must already know what the target system provides.

v0.4 should make the first serious step toward automatic profile generation.

Main v0.4 idea:

> Detect facts from the current Linux system and generate a target YAML profile from those facts.

This allows the practical workflow:

```bash
# On a target or target-like Linux system
compatlab profiles generate --from-current --name local --output local.yaml

# In development or CI
compatlab compare ./dist/my-app --target-file local.yaml
```

---

## 4. v0.4 goal

Implement automatic profile detection/generation from the **current system**.

Primary deliverables:

```bash
compatlab profiles detect
compatlab profiles detect --json system-facts.json
compatlab profiles generate --from-current --name local --output local.yaml
```

Highly recommended deliverable:

```bash
compatlab compare PATH --target-file ./local.yaml
```

This is useful because generated profiles should be usable immediately without copying them into the built-in profiles directory.

---

## 5. v0.4 non-goals

Do **not** implement these in v0.4:

- Docker image scanning;
- rootfs scanning;
- recursive dependency resolution;
- local filesystem dependency resolution for scanned artifacts;
- Wheel/RPM/DEB scanning;
- HTML reports;
- web UI;
- database;
- daemon/server mode;
- Go helper;
- automatic patching via `patchelf`;
- SBOM or security scanning.

Docker is planned later, but only after current-system facts and profile generation are stable.

Recommended roadmap:

```text
v0.4: current-system detection + facts model + YAML generation + fixture tests
v0.5: generate profile from Docker image
v0.6: runtime profiles with installed package presets
```

Do not jump directly into Docker in v0.4.

---

## 6. Core design principle for v0.4

Separate **raw detected facts** from **target profile**.

Do not generate YAML directly from scattered subprocess calls.

Use a two-step flow:

```text
current Linux system
        ↓
SystemFacts model
        ↓
TargetProfile model
        ↓
YAML profile file
```

### SystemFacts

`SystemFacts` means: what was actually observed on the system.

It can contain extra details, warnings, command provenance, library paths, etc.

### TargetProfile

`TargetProfile` means: the normalized compatibility contract used by the existing compare engine.

It should contain only the fields needed by `compatlab compare`.

---

## 7. Suggested data models

Before adding new models, inspect the existing Pydantic models in the repository. Reuse existing naming conventions and field style.

Suggested new models, probably under a profiles or models module:

```python
class OsReleaseFacts(BaseModel):
    id: str | None = None
    name: str | None = None
    version_id: str | None = None
    pretty_name: str | None = None


class LibraryFact(BaseModel):
    soname: str
    path: str | None = None
    arch: str | None = None


class SymbolVersionFacts(BaseModel):
    glibc: list[str] = []
    glibcxx: list[str] = []
    cxxabi: list[str] = []


class FactWarning(BaseModel):
    code: str
    message: str
    source: str | None = None


class SystemFacts(BaseModel):
    os_release: OsReleaseFacts
    architecture: str | None = None
    glibc_version: str | None = None
    dynamic_linkers: list[str] = []
    library_paths: list[str] = []
    libraries: list[LibraryFact] = []
    symbol_versions: SymbolVersionFacts = SymbolVersionFacts()
    detected_by: list[str] = []
    warnings: list[FactWarning] = []
```

Adjust this to fit the repository's existing Pydantic version and style.

Important: avoid mutable defaults if the current Pydantic version/style requires `Field(default_factory=list)`.

---

## 8. Detection sources for v0.4

Use simple, explainable sources.

Minimum useful sources:

| Source | Purpose |
|---|---|
| `/etc/os-release` | Detect OS ID/version/name |
| `platform.machine()` | Detect architecture |
| `ldd --version` | Detect glibc version on glibc systems |
| `ldconfig -p` | Detect available shared libraries and paths |
| `readelf --version-info libc.so.6` | Detect available `GLIBC_*` versions |
| `readelf --version-info libstdc++.so.6` | Detect available `GLIBCXX_*` and `CXXABI_*` versions |
| known dynamic linker paths | Detect interpreters/loaders |

Known dynamic linker candidates to check:

```text
/lib64/ld-linux-x86-64.so.2
/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2
/lib/ld-linux.so.2
/lib/ld-linux-aarch64.so.1
/lib/aarch64-linux-gnu/ld-linux-aarch64.so.1
```

Keep this list small and obvious in v0.4.

---

## 9. Parser implementation notes

### `/etc/os-release`

Implement a small parser that handles lines like:

```text
ID=ubuntu
VERSION_ID="24.04"
PRETTY_NAME="Ubuntu 24.04 LTS"
```

Rules:

- ignore blank lines;
- ignore comments;
- split on the first `=`;
- strip surrounding quotes;
- preserve unknown fields only if useful;
- do not crash on malformed lines.

### `ldd --version`

Use it only as a best-effort glibc version source.

Example expected extraction:

```text
ldd (Ubuntu GLIBC 2.39-0ubuntu8.4) 2.39
```

Result:

```text
2.39
```

If parsing fails, add a warning and continue.

### `ldconfig -p`

Use it to discover library sonames and paths.

Typical line:

```text
libstdc++.so.6 (libc6,x86-64) => /lib/x86_64-linux-gnu/libstdc++.so.6
```

Extract:

- soname: `libstdc++.so.6`
- arch/descriptor: `libc6,x86-64`
- path: `/lib/x86_64-linux-gnu/libstdc++.so.6`

Do not make this parser too clever in v0.4. It should be stable and tested on fixtures.

### Symbol versions

Prefer reusing existing logic from the ELF scanner/version parser introduced in v0.2/v0.3.

Goal:

- find available `GLIBC_*` versions from `libc.so.6`;
- find available `GLIBCXX_*` and `CXXABI_*` versions from `libstdc++.so.6`;
- compute maximum versions using the existing numeric version comparison from v0.3.

Do not duplicate version-comparison logic if it already exists.

---

## 10. Profile generation logic

Implement a function similar to:

```python
def generate_target_profile_from_facts(
    facts: SystemFacts,
    *,
    name: str,
) -> TargetProfile:
    ...
```

Expected mapping:

| `SystemFacts` | `TargetProfile` |
|---|---|
| architecture | target architecture |
| dynamic_linkers | provided interpreters/loaders |
| libraries[*].soname | provided libraries |
| max `GLIBC_*` | target glibc max version |
| max `GLIBCXX_*` | target libstdc++ max GLIBCXX |
| max `CXXABI_*` | target CXXABI max version |
| os_release | profile metadata/name/description if schema supports it |

Important: inspect the existing target profile schema first. Do not invent incompatible YAML field names.

If the existing schema does not support metadata fields like OS name/version, keep them out of the target profile for now or add them in a backward-compatible way.

Generated profile must be loadable by the existing profile loader.

---

## 11. CLI design for v0.4

Recommended CLI:

```bash
compatlab profiles detect
compatlab profiles detect --json system-facts.json
compatlab profiles generate --from-current --name local --output local.yaml
```

Optional but strongly useful:

```bash
compatlab compare ./app --target-file ./local.yaml
```

### `profiles detect`

Purpose: inspect current system and show raw facts.

Expected terminal output should be concise and human-readable:

```text
System profile detected

OS:            Ubuntu 24.04 LTS
Architecture:  x86_64
glibc:         2.39
GLIBC max:     2.39
GLIBCXX max:   3.4.33
CXXABI max:    1.3.15
Interpreters:  1
Libraries:     128
Warnings:      0
```

The exact formatting can follow the existing Rich output style.

### `profiles detect --json`

Writes raw `SystemFacts` to JSON.

This is for debugging and tests, not necessarily for end users.

### `profiles generate --from-current --name local --output local.yaml`

Generates a YAML target profile from the current system.

Expected behavior:

- collect `SystemFacts`;
- convert to `TargetProfile`;
- validate using existing Pydantic model;
- write YAML;
- print output path and a short summary.

### `compare --target-file`

If implemented, it should load a target profile from an explicit YAML path.

Rules:

- keep existing `--target TARGET` behavior unchanged;
- do not break built-in profiles;
- return the same exit codes as normal compare;
- invalid/missing `--target-file` should lead to exit code `2`, consistent with profile loading failures.

---

## 12. Suggested source layout

Do not blindly create this exact layout if the existing repository has a better structure. Inspect first.

Suggested additions:

```text
src/compatlab/
  profiles/
    facts.py
    detect.py
    generate.py
    os_release.py
    ldconfig.py
    linkers.py
```

Possible responsibilities:

```text
facts.py       Pydantic models for raw system facts
os_release.py  parser for /etc/os-release content
ldconfig.py    runner/parser for ldconfig -p
linkers.py     known dynamic linker path detection
detect.py      orchestration: current system -> SystemFacts
generate.py    SystemFacts -> TargetProfile/YAML
```

Reuse existing command runner if available from v0.2. Do not create a second subprocess abstraction unless necessary.

---

## 13. Tests required for v0.4

Use fixture-based tests heavily. Do not rely only on the live host.

Suggested fixtures:

```text
tests/fixtures/profiles_detect/
  ubuntu_2404_os_release.txt
  rocky_9_os_release.txt
  ldconfig_ubuntu_2404.txt
  ldd_ubuntu_2404.txt
  readelf_libc_239.txt
  readelf_libstdcxx_3433.txt
```

Suggested tests:

```text
test_parse_os_release.py
test_parse_ldd_version.py
test_parse_ldconfig.py
test_detect_dynamic_linkers.py
test_generate_profile_from_facts.py
test_profiles_detect_cli.py
test_profiles_generate_cli.py
```

Minimum assertions:

- OS release parser extracts `ID`, `VERSION_ID`, `PRETTY_NAME`;
- malformed os-release lines do not crash parsing;
- `ldd --version` parser extracts glibc version when present;
- `ldconfig -p` parser extracts soname and path;
- duplicate sonames are handled deterministically;
- generated profile includes architecture;
- generated profile includes interpreters;
- generated profile includes library sonames;
- generated profile includes max GLIBC/GLIBCXX/CXXABI versions when facts provide them;
- generated YAML can be loaded by the existing profile loader;
- CLI can generate a profile into a temporary file.

Smoke tests that touch the real host should be guarded/skipped when required tools are missing.

---

## 14. Acceptance criteria for v0.4

The release is acceptable when these commands work:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run compatlab profiles detect
uv run compatlab profiles detect --json /tmp/system-facts.json
uv run compatlab profiles generate --from-current --name local --output /tmp/local.yaml
uv run compatlab profiles show local  # only if generated profiles are registered; otherwise not required
uv run compatlab compare /bin/bash --target-file /tmp/local.yaml  # if --target-file is implemented
make check
```

If `profiles show local` is not supported for arbitrary files, do not force it into v0.4.

The most important end-to-end command is:

```bash
uv run compatlab profiles generate --from-current --name local --output /tmp/local.yaml
```

and, if implemented:

```bash
uv run compatlab compare /bin/bash --target-file /tmp/local.yaml
```

---

## 15. Release notes draft for v0.4

Create `v0.4.md` or the repository's equivalent release notes file.

Suggested summary:

```markdown
# CompatLab ArtifactDoctor 0.4

## Summary

CompatLab ArtifactDoctor 0.4 adds the first automatic target profile generation flow.

This release teaches CompatLab to detect raw facts from the current Linux system,
convert them into a normalized target profile, and write that profile as YAML.
The generated profile can then be used for compatibility checks instead of being
written manually.
```

Suggested Added section:

```markdown
## Added

- Raw `SystemFacts` model for current-system detection.
- `/etc/os-release` parser for OS identity and version facts.
- Current architecture detection.
- Best-effort glibc version detection from `ldd --version`.
- `ldconfig -p` parser for provided shared libraries.
- Dynamic linker path detection for common Linux architectures.
- Available `GLIBC_*`, `GLIBCXX_*`, and `CXXABI_*` extraction from system libraries.
- Target profile generation from detected system facts.
- `compatlab profiles detect` command.
- `compatlab profiles detect --json` output.
- `compatlab profiles generate --from-current --name NAME --output PATH` command.
- Optional `compatlab compare PATH --target-file PROFILE.yaml` support.
- Fixture-based tests for profile detection and generation.
```

Suggested Not Included Yet:

```markdown
## Not Included Yet

- Docker image profile generation.
- Rootfs scanning.
- Recursive dependency resolution.
- Runtime profile presets with installed packages.
- Wheel, RPM, or DEB scanning.
```

---

## 16. Agent working instructions

You are Codex working in an existing repository. Be conservative.

### First actions

1. Inspect repository structure:

```bash
find . -maxdepth 3 -type f | sort | sed 's#^./##'
```

2. Inspect project configuration:

```bash
sed -n '1,240p' pyproject.toml
sed -n '1,240p' Makefile
```

3. Inspect existing CLI and models:

```bash
find src -type f | sort
```

Open the files that define:

- Typer app/commands;
- target profile model;
- profile loading;
- JSON/YAML writing;
- scan report model;
- command runner;
- readelf parsers;
- version comparison helpers.

4. Run the baseline checks before editing:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
make check
```

If baseline fails, report the failure and avoid large changes until the cause is clear.

### Implementation discipline

- Prefer small, isolated changes.
- Do not rewrite existing scanner/comparison architecture.
- Reuse existing helpers.
- Add tests before or together with implementation.
- Keep names boring and explicit.
- Preserve public CLI compatibility.
- Do not add heavy dependencies unless strictly necessary.
- Do not introduce Docker in v0.4.
- Do not introduce network access.
- Do not make tests depend on a specific developer machine.

### Completion behavior

At the end, provide:

- list of changed files;
- implemented commands;
- test results;
- any known limitations;
- exact commands the project owner should run manually.

---

## 17. Recommended implementation order

Follow this order to reduce risk:

### Step 1: Add pure parsers and tests

Implement:

- `/etc/os-release` parser;
- `ldd --version` parser;
- `ldconfig -p` parser.

Add fixture tests. No CLI yet.

### Step 2: Add `SystemFacts` model

Add raw facts model and unit tests for serialization.

### Step 3: Add current-system detector

Implement a detector that calls the parsers and existing command runner.

It should return `SystemFacts`, not YAML.

### Step 4: Add profile generator

Implement `SystemFacts -> TargetProfile` conversion.

Generated profile must validate against existing target profile model.

### Step 5: Add `profiles detect` CLI

Show human-readable summary.

Add `--json` support.

### Step 6: Add `profiles generate --from-current`

Write YAML to a user-provided path.

### Step 7: Add `compare --target-file` if low-risk

This is highly useful, but do not destabilize the project for it.

### Step 8: Update README and release notes

Add examples for the new workflow.

---

## 18. Practical first manual workflow after implementation

The project owner should be able to run:

```bash
uv run compatlab profiles detect
uv run compatlab profiles detect --json /tmp/system-facts.json
jq . /tmp/system-facts.json

uv run compatlab profiles generate --from-current --name local --output /tmp/local.yaml
cat /tmp/local.yaml

uv run compatlab compare /bin/bash --target-file /tmp/local.yaml
```

If `/bin/bash` is not available, use another ELF executable present on the system.

---

## 19. Known technical risks

### Different distributions expose libraries differently

`ldconfig -p` output can differ across distributions and architectures. Use fixture-based parsers and keep parsing tolerant.

### musl systems are not glibc systems

Do not overfit the whole project to Alpine/musl in v0.4. If glibc is not detected, add a warning and continue.

### `libstdc++.so.6` may be absent

C-only systems or minimal containers may not have libstdc++. This should produce a warning, not a crash.

### `readelf` may be missing

v0.2 already handles missing `readelf` for artifact scan. Reuse similar behavior for system library symbol detection.

### Generated profile may be noisy

`ldconfig -p` can produce a large library list. This is acceptable for v0.4. Later versions can minimize profiles.

### Architecture names must stay normalized

Reuse existing architecture normalization from v0.3 if available.

---

## 20. Final v0.4 definition of done

v0.4 is done when CompatLab can:

1. inspect the current Linux system;
2. represent the result as structured `SystemFacts`;
3. generate a valid YAML `TargetProfile` from those facts;
4. save raw facts as JSON;
5. save target profile as YAML;
6. test all parsers on fixtures;
7. keep existing scan/compare behavior working;
8. pass `make check`.

Do not start Docker work until this is complete.
