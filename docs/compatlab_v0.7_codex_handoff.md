# CompatLab ArtifactDoctor 0.7 — Codex Development Handoff

## 1. Purpose of This Document

This document is a full handoff for the Codex agent to continue development of the educational project **CompatLab ArtifactDoctor** and implement the next version: **0.7**.

The project has already passed versions **0.4**, **0.5**, and **0.6**. The next version should extend the product in a practical direction: from checking a single ELF artifact against a target profile to understanding a local application bundle with bundled shared libraries and recursive ELF dependencies.

Recommended release title:

```text
CompatLab ArtifactDoctor 0.7 — Bundle-aware recursive dependency resolution
```

Short product meaning:

> CompatLab should learn to check not only one binary file, but also the local directory that is shipped with it, resolve `DT_NEEDED` libraries inside that bundle, follow transitive dependencies, and compare all discovered ELF artifacts against the selected target profile.

---

## 2. Current Project Context

### 2.1 Product Summary

CompatLab ArtifactDoctor is a Python-first CLI tool for preflight compatibility checks of Linux binary artifacts.

Its goal is to answer a practical question before shipping a binary:

> Is this Linux binary artifact likely to run on the target Linux system?

The tool currently works with ELF facts such as:

- architecture;
- dynamic linker path;
- `DT_NEEDED` libraries;
- required `GLIBC_*` symbol versions;
- required `GLIBCXX_*` symbol versions;
- required `CXXABI_*` symbol versions;
- `RPATH` / `RUNPATH` values;
- target profile capabilities.

The project is intentionally narrow and CLI-oriented. It is not a package manager, not a security scanner, not an SBOM generator, and not a web service.

### 2.2 Existing CLI Style

Current user-facing commands include examples like:

```bash
uv run compatlab scan ./app
uv run compatlab scan ./app --json report.json
uv run compatlab compare ./app --target ubuntu-1804
uv run compatlab compare ./app --target-file ./local.yaml
uv run compatlab compare ./app --target ubuntu-1804 --json report.json

uv run compatlab profiles list
uv run compatlab profiles show ubuntu-1804
uv run compatlab profiles detect
uv run compatlab profiles detect --json system-facts.json
uv run compatlab profiles generate --from-current --name local --output local.yaml
uv run compatlab profiles generate --from-image ubuntu:22.04 --name ubuntu-2204-docker --output ubuntu-2204.yaml
uv run compatlab profiles generate --from-image ubuntu:22.04 --runtime-preset cpp-runtime --name ubuntu-2204-cpp --output ubuntu-2204-cpp.yaml
uv run compatlab profiles validate ubuntu-2204.yaml
```

When adding v0.7 functionality, preserve the current style:

- Typer-based CLI;
- Rich-based pretty output;
- Pydantic-based report models;
- JSON report support where the existing commands already support JSON;
- `uv run ...` execution examples;
- tests first or at least tests alongside implementation;
- small, incremental changes.

---

## 3. Summary of Previous Versions

### 3.1 Version 0.4

Version 0.4 added automatic target profile generation from the current Linux system.

Main capabilities:

- raw `SystemFacts` model;
- `/etc/os-release` parsing;
- current architecture detection;
- best-effort glibc detection through `ldd --version`;
- `ldconfig -p` parsing;
- dynamic linker detection;
- symbol version extraction from system libraries;
- YAML target profile generation;
- profile validation;
- comparison using explicit YAML profile through `--target-file`.

Important design result:

> CompatLab learned to describe the target system instead of relying only on manually written profiles.

### 3.2 Version 0.5

Version 0.5 added Docker image target profile generation.

Main capabilities:

- Docker CLI orchestration;
- `docker image inspect`;
- optional `docker pull`;
- temporary container creation;
- `docker export` rootfs flow;
- tar-based rootfs parsing from Python;
- `/etc/os-release` parsing from exported rootfs;
- dynamic linker detection inside rootfs;
- library basename discovery inside common library directories;
- extraction of selected libraries to host temp files;
- host-side `readelf` analysis;
- Docker metadata in generated profiles.

Important design result:

> CompatLab can generate target profiles from Docker images without requiring Python, `readelf`, `ldconfig`, or development tools inside the image.

### 3.3 Version 0.6

Version 0.6 added Docker runtime profile presets.

Main capabilities:

- built-in runtime preset registry;
- current presets: `cpp-runtime`, `python-runtime`;
- runtime preset inspection commands;
- package manager detection for Docker rootfs exports: `apt-get`, `dnf`, `yum`;
- install script generation for supported package managers;
- temporary Docker container runtime export flow;
- runtime metadata in generated profiles.

Important design result:

> CompatLab can generate a target profile from a temporary Docker runtime environment after installing predefined runtime packages, without mutating the source image.

---

## 4. Why Version 0.7 Should Focus on Bundles

Versions 0.4–0.6 strengthened the **target environment side**:

- current system profile;
- Docker image profile;
- Docker image plus runtime preset profile.

The next weak point is the **artifact side**.

Current MVP scope is centered around one ELF binary or shared library as input. That is useful, but real Linux applications are often shipped as a directory:

```text
dist/
  my-app
  lib/
    libfoo.so
    libbar.so
```

A single binary check is not enough because:

- the main executable may depend on local `.so` files;
- local `.so` files may have their own transitive dependencies;
- some dependencies may be bundled;
- some dependencies may be expected from the target system;
- `RPATH` and `RUNPATH` may alter lookup paths;
- `$ORIGIN` is common in real application bundles;
- missing transitive dependencies are hard to diagnose manually.

Therefore v0.7 should teach CompatLab to understand a local application bundle.

---

## 5. Main Goal for v0.7

Implement bundle-aware recursive dependency resolution for ELF artifacts.

The desired command shape:

```bash
uv run compatlab compare ./dist/my-app \
  --target-file /tmp/ubuntu-2204-cpp-runtime.yaml \
  --bundle-root ./dist \
  --recursive
```

Expected high-level behavior:

```text
OK: libfoo.so resolved from ./dist/lib/libfoo.so
OK: libbar.so resolved from ./dist/lib/libbar.so
OK: libc.so.6 provided by target profile
FAIL: libssl.so.3 not found in bundle or target profile
WARN: bundled libstdc++.so.6 requires GLIBCXX_3.4.30, target provides GLIBCXX_3.4.29
```

The central product improvement:

> CompatLab should explain where each dependency is expected to come from: the local bundle, the target profile, or nowhere.

---

## 6. Scope of Version 0.7

### 6.1 Must Have

Implement the following capabilities:

1. Accept a local bundle root in `scan` and `compare` commands.
2. Resolve direct `DT_NEEDED` dependencies of the entrypoint artifact.
3. Resolve transitive dependencies recursively when `--recursive` is provided.
4. Search for bundled shared libraries inside `--bundle-root`.
5. Use `RPATH` / `RUNPATH` information during local dependency lookup.
6. Support `$ORIGIN` expansion for common bundle layouts.
7. Detect dependencies provided by the target profile.
8. Detect missing dependencies.
9. Detect ambiguous bundled dependency candidates.
10. Compare every resolved bundled ELF against the selected target profile.
11. Include dependency resolution results in terminal output.
12. Include dependency graph / dependency resolution data in JSON reports.
13. Add unit and CLI tests.
14. Update README and release notes style documentation for v0.7 behavior.

### 6.2 Should Have

Implement if this can be done without destabilizing the release:

1. Add `--max-depth` to limit recursive dependency traversal.
2. Add `--max-files` to avoid scanning huge bundles accidentally.
3. Add clearer diagnostics for absolute `RPATH` / `RUNPATH` entries.
4. Add resolution explanation mode, for example `--explain-resolution`.
5. Print a Rich table with resolved and unresolved dependencies.

### 6.3 Nice to Have

Only implement after must-have and should-have items are stable:

1. Print dependency tree output.
2. Add a small `compatlab scan --bundle-root ... --recursive` summary table.
3. Add profile-aware suggestions such as “bundle this library or use a newer target profile”.

---

## 7. Explicit Non-Goals for Version 0.7

Do not implement these in v0.7:

- wheel scanning;
- RPM scanning;
- DEB scanning;
- SBOM generation;
- vulnerability scanning;
- web UI;
- database;
- daemon/server mode;
- automatic patching with `patchelf`;
- Docker image mutation;
- Dockerfile generation;
- arbitrary package installation;
- running artifacts inside containers;
- Go helper implementation;
- full dynamic linker emulation.

Important:

> Do not turn CompatLab into a package manager frontend or a full runtime emulator. v0.7 should stay a static preflight compatibility checker.

---

## 8. Proposed CLI Contract

### 8.1 Scan Command

Add optional bundle-related flags:

```bash
uv run compatlab scan PATH \
  --bundle-root DIR \
  --recursive \
  --json report.json
```

Expected behavior:

- Without `--bundle-root`, keep existing behavior.
- With `--bundle-root` but without `--recursive`, resolve only direct dependencies where practical.
- With `--bundle-root --recursive`, build a recursive dependency graph.
- The entrypoint `PATH` must be inside `--bundle-root` or must be allowed explicitly if current project conventions permit external entrypoints.
- Prefer clear validation errors over surprising behavior.

### 8.2 Compare Command

Add optional bundle-related flags:

```bash
uv run compatlab compare PATH \
  --target ubuntu-2204 \
  --bundle-root DIR \
  --recursive \
  --json report.json
```

```bash
uv run compatlab compare PATH \
  --target-file ./target.yaml \
  --bundle-root DIR \
  --recursive \
  --json report.json
```

Expected behavior:

- Preserve the existing requirement that exactly one target selector is provided:
  - `--target TARGET`;
  - `--target-file PROFILE.yaml`.
- Without `--bundle-root`, keep existing compare behavior.
- With `--bundle-root`, compare the entrypoint and every resolved bundled ELF file against the target profile.
- A missing dependency should be reported with enough context:
  - who required it;
  - whether it was searched in bundle paths;
  - whether the target profile provides it.

### 8.3 Optional Flags

Recommended optional flags:

```bash
--max-depth 10
--max-files 500
--explain-resolution
```

Default values should be conservative and documented.

---

## 9. Proposed Domain Models

Adapt names to the actual codebase if existing naming conventions differ.
Do not force exact class names if the current architecture suggests better names.

### 9.1 Bundle Model

```python
class ArtifactBundle(BaseModel):
    root_path: Path
    entrypoint_path: Path
    discovered_elf_files: list[Path]
```

Purpose:

- represents a local directory that is shipped with the artifact;
- knows the entrypoint artifact;
- provides discovered ELF candidates.

### 9.2 Dependency Resolution Kind

```python
class DependencyResolutionKind(str, Enum):
    BUNDLED = "bundled"
    TARGET = "target"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"
    INCOMPATIBLE = "incompatible"
```

Meaning:

- `bundled`: dependency found inside `--bundle-root`;
- `target`: dependency is expected from selected target profile;
- `missing`: dependency not found in bundle and not provided by target;
- `ambiguous`: several local candidates match the same needed name;
- `incompatible`: candidate was found but cannot be used safely.

### 9.3 Dependency Node

```python
class DependencyNode(BaseModel):
    artifact_id: str
    path: str | None = None
    soname: str | None = None
    needed_libraries: list[str] = []
    rpath: list[str] = []
    runpath: list[str] = []
    required_glibc_versions: list[str] = []
    required_glibcxx_versions: list[str] = []
    required_cxxabi_versions: list[str] = []
```

Purpose:

- describes one scanned ELF file or target-provided dependency placeholder.

### 9.4 Dependency Edge

```python
class DependencyEdge(BaseModel):
    from_artifact_id: str
    needed_name: str
    resolution_kind: DependencyResolutionKind
    resolved_artifact_id: str | None = None
    resolved_path: str | None = None
    candidates: list[str] = []
    message: str | None = None
```

Purpose:

- describes one `DT_NEEDED` edge and how it was resolved.

### 9.5 Dependency Graph

```python
class DependencyGraph(BaseModel):
    entrypoint_artifact_id: str
    nodes: list[DependencyNode]
    edges: list[DependencyEdge]
    unresolved_dependencies: list[DependencyEdge]
```

Purpose:

- becomes part of JSON reports;
- powers terminal summaries;
- can later support HTML reports or CI gates.

---

## 10. Resolution Algorithm

### 10.1 High-Level Flow

For `compatlab compare PATH --target-file PROFILE --bundle-root DIR --recursive`:

1. Validate input paths.
2. Scan the entrypoint ELF using the existing scanner.
3. Build a local bundle index from `DIR`.
4. For each `DT_NEEDED` entry:
   1. Try to resolve from local bundle paths using `RPATH` / `RUNPATH`.
   2. If not found locally, check whether the target profile provides the library basename.
   3. If not found in either source, mark as missing.
5. If resolved from bundle and recursive mode is enabled:
   1. scan that local `.so`;
   2. process its own `DT_NEEDED` entries;
   3. continue until graph is complete or limits are reached.
6. Compare all scanned local ELF files against target profile compatibility rules.
7. Return combined diagnostics and JSON report.

### 10.2 Lookup Order

Do not attempt a perfect dynamic linker implementation in v0.7. Implement a useful deterministic approximation.

Recommended local lookup order:

1. directories from `RUNPATH`, with `$ORIGIN` expanded;
2. directories from `RPATH`, with `$ORIGIN` expanded;
3. common bundle library directories:
   - entrypoint directory;
   - `bundle_root/lib`;
   - `bundle_root/lib64`;
   - `bundle_root/usr/lib`;
   - `bundle_root/usr/lib64`;
   - architecture-specific subdirectories when easy to support;
4. fallback bundle index by basename / soname.

If current project already treats `RPATH` and `RUNPATH` differently, preserve that behavior.

### 10.3 `$ORIGIN` Handling

Implement at least:

```text
$ORIGIN
$ORIGIN/lib
$ORIGIN/../lib
```

Where `$ORIGIN` means the directory containing the ELF file whose dependency is being resolved.

Example:

```text
bundle root: /project/dist
artifact:    /project/dist/bin/my-app
RUNPATH:     $ORIGIN/../lib
resolved:    /project/dist/lib
```

### 10.4 Cycle Protection

The resolver must avoid infinite recursion.

Use one or more of these identifiers:

- resolved real path;
- inode if convenient;
- normalized absolute path;
- scanner artifact ID.

Repeated libraries should be scanned once and reused in the graph.

### 10.5 Limits

Recommended defaults:

```text
max_depth = 10
max_files = 500
```

Behavior when a limit is reached:

- do not crash;
- add a warning diagnostic;
- stop expanding deeper dependencies;
- preserve already collected graph data.

---

## 11. Compatibility Rules for Bundled Libraries

When a dependency resolves to a local bundled ELF file, treat it as part of the shipped artifact.

For each local scanned ELF:

- check architecture compatibility with target profile;
- check dynamic linker requirements where applicable;
- check required `GLIBC_*` versions against target profile;
- check required `GLIBCXX_*` versions against target profile;
- check required `CXXABI_*` versions against target profile;
- check its own `DT_NEEDED` libraries;
- report which file caused the issue.

Important diagnostic distinction:

```text
main binary incompatible
bundled dependency incompatible
dependency missing from bundle and target
ambiguous dependency inside bundle
```

This distinction matters because the fix differs:

- rebuild the main binary;
- rebuild or replace a bundled `.so`;
- add a missing library to the bundle;
- install/use a different target runtime;
- clean duplicated libraries from the bundle.

---

## 12. JSON Report Contract

Extend existing scan/compare JSON reports without breaking existing fields.

Recommended new block:

```json
{
  "dependency_graph": {
    "entrypoint_artifact_id": "artifact:dist/my-app",
    "nodes": [],
    "edges": [],
    "unresolved_dependencies": []
  },
  "bundle_resolution": {
    "bundle_root": "./dist",
    "recursive": true,
    "max_depth": 10,
    "max_files": 500,
    "resolved_count": 0,
    "missing_count": 0,
    "ambiguous_count": 0
  }
}
```

If the existing report model has a more suitable structure, adapt this shape while preserving the semantics.

Backward compatibility requirement:

> Existing JSON consumers should not break when `--bundle-root` is not used.

Recommended approach:

- make new fields optional;
- omit or set to `null` when bundle resolution is not requested;
- preserve existing top-level fields.

---

## 13. Terminal Output Requirements

Keep output practical and readable.

For `scan --bundle-root --recursive`, show:

```text
Bundle root: ./dist
Entrypoint: ./dist/my-app
Scanned ELF files: 3
Resolved bundled dependencies: 2
Target-provided dependencies: 5
Missing dependencies: 1
Ambiguous dependencies: 0
```

For `compare --bundle-root --recursive`, show compatibility issues grouped by source:

```text
Entrypoint compatibility
  OK ./dist/my-app

Bundled libraries
  OK ./dist/lib/libfoo.so
  FAIL ./dist/lib/libbar.so
       requires GLIBCXX_3.4.30, target provides up to GLIBCXX_3.4.29

Missing dependencies
  FAIL libssl.so.3 required by ./dist/lib/libfoo.so

Resolution summary
  bundled: 2
  target: 5
  missing: 1
  ambiguous: 0
```

If the current project already has a diagnostics table, extend it instead of creating a separate competing output style.

---

## 14. Testing Plan

### 14.1 Unit Tests

Add tests for:

1. `$ORIGIN` expansion;
2. simple local library resolution;
3. fallback basename / soname index;
4. missing dependency detection;
5. ambiguous dependency detection;
6. recursive dependency traversal;
7. cycle protection;
8. max depth behavior;
9. max files behavior;
10. JSON model serialization.

### 14.2 CLI Tests

Add tests for:

```bash
uv run compatlab scan ./fixtures/bundles/simple-ok/my-app --bundle-root ./fixtures/bundles/simple-ok --recursive
```

```bash
uv run compatlab compare ./fixtures/bundles/simple-ok/my-app --target ubuntu-2204 --bundle-root ./fixtures/bundles/simple-ok --recursive
```

```bash
uv run compatlab compare ./fixtures/bundles/missing-transitive/my-app --target ubuntu-2204 --bundle-root ./fixtures/bundles/missing-transitive --recursive --json /tmp/report.json
```

Exact target profile names should match the actual repository fixtures.

### 14.3 Fixture Layout

Recommended test fixture directories:

```text
tests/fixtures/bundles/simple-ok/
  bin/my-app
  lib/libfoo.so

tests/fixtures/bundles/missing-transitive/
  bin/my-app
  lib/libfoo.so

tests/fixtures/bundles/origin-runpath/
  bin/my-app
  lib/libfoo.so

tests/fixtures/bundles/ambiguous-lib/
  bin/my-app
  lib/libfoo.so
  alt-lib/libfoo.so

tests/fixtures/bundles/cycle/
  lib/liba.so
  lib/libb.so
```

If the repository currently avoids binary fixtures, use small generated or mocked ELF scan results in unit tests. Do not add heavy binaries.

### 14.4 Test Philosophy

Prefer fast, deterministic tests.

Do not require Docker for v0.7 tests unless an existing Docker test marker already exists and is optional.

Use mocks/fakes for scanner behavior where binary fixtures would be too brittle.

---

## 15. Suggested Implementation Plan for Codex

### Step 1 — Inspect Current Architecture

Before editing, inspect the repository structure:

```bash
find . -maxdepth 3 -type f | sort
```

Then inspect likely modules:

```bash
grep -R "class .*Report\|def .*scan\|def .*compare\|Typer\|readelf\|DT_NEEDED\|RUNPATH\|RPATH" -n compatlab tests pyproject.toml README.md
```

Identify:

- scanner models;
- compare models;
- target profile models;
- CLI modules;
- Rich output module;
- JSON report serialization path;
- current test fixture strategy.

### Step 2 — Add Models First

Add dependency graph and bundle resolution models in the most suitable existing module.

Avoid over-engineering. The first version should be simple and serializable.

Run model tests:

```bash
uv run pytest tests/path/to/new_model_tests.py
```

### Step 3 — Add Bundle Index

Implement a local bundle index that can discover candidate `.so` files under `--bundle-root`.

Minimum functionality:

- walk directory tree;
- skip non-files;
- skip obviously irrelevant files by extension/name where safe;
- use existing ELF scanner or a lightweight check to confirm candidates;
- index by basename;
- index by `SONAME` if the scanner already extracts it or if it is easy to add.

### Step 4 — Add Path Resolver

Implement helper functions for:

- `$ORIGIN` expansion;
- relative path normalization;
- safe path handling inside bundle root;
- candidate lookup by search directories;
- ambiguous candidate reporting.

### Step 5 — Add Recursive Resolver

Implement the graph traversal.

Keep it independent from CLI so tests can call it directly.

Suggested input:

- entrypoint path;
- bundle root;
- target profile or target library set;
- scanner interface;
- recursion flag;
- max depth;
- max files.

Suggested output:

- dependency graph;
- list of scanned local artifacts;
- resolution summary;
- warnings.

### Step 6 — Integrate with `scan`

Add CLI flags to `scan`.

When bundle flags are absent, do not change behavior.

When bundle flags are present:

- scan entrypoint;
- resolve graph;
- include graph in JSON report;
- show summary in terminal.

### Step 7 — Integrate with `compare`

Add CLI flags to `compare`.

When bundle flags are absent, do not change behavior.

When bundle flags are present:

- perform normal compare for entrypoint;
- resolve bundled dependencies;
- compare each bundled local ELF against target profile;
- merge diagnostics into final report;
- preserve existing exit behavior if tests define it.

### Step 8 — Add Tests Iteratively

After each block, run focused tests.

Before finalizing, run:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
make check
```

If coverage is tracked in the project, also run:

```bash
make coverage
```

### Step 9 — Update Documentation

Update README with:

- new CLI examples;
- bundle-aware behavior;
- explicit limitations;
- JSON report example if useful.

Add or update release note for 0.7, matching previous release note style.

Suggested file name:

```text
v0.7.md
```

---

## 16. Acceptance Criteria

Version 0.7 is complete when all of the following are true:

1. Existing v0.4–v0.6 behavior remains compatible.
2. `scan PATH` still works without bundle flags.
3. `compare PATH --target ...` still works without bundle flags.
4. `compare PATH --target-file ...` still works without bundle flags.
5. `scan PATH --bundle-root DIR --recursive` produces dependency resolution output.
6. `compare PATH --target-file PROFILE --bundle-root DIR --recursive` compares entrypoint and resolved bundled libraries.
7. Missing direct dependencies are reported.
8. Missing transitive dependencies are reported.
9. `$ORIGIN` in `RPATH` / `RUNPATH` works for common layouts.
10. Ambiguous local dependency candidates are reported clearly.
11. Recursive traversal is protected from cycles.
12. Recursive traversal respects max depth / max file limits if implemented.
13. JSON report contains dependency graph information when bundle resolution is enabled.
14. Tests cover core resolver behavior and CLI integration.
15. README documents the new workflow.
16. Release note for v0.7 exists.
17. `uv run pytest` passes.
18. `uv run ruff check .` passes.
19. `uv run ruff format --check .` passes.
20. `make check` passes.

---

## 17. Practical Examples for Expected Behavior

### 17.1 Simple Bundle OK

Input:

```text
dist/
  bin/my-app
  lib/libfoo.so
```

`my-app` needs `libfoo.so`.
`libfoo.so` is found in `dist/lib`.
All other libraries are available in target profile.

Expected result:

```text
Compatibility: OK
Resolved from bundle: libfoo.so -> dist/lib/libfoo.so
Missing dependencies: none
```

### 17.2 Missing Transitive Dependency

Input:

```text
dist/
  bin/my-app
  lib/libfoo.so
```

`my-app` needs `libfoo.so`.
`libfoo.so` needs `libbar.so`.
`libbar.so` is not in the bundle and not in target profile.

Expected result:

```text
Compatibility: FAIL
Missing dependency: libbar.so required by dist/lib/libfoo.so
```

### 17.3 `$ORIGIN` RUNPATH

Input:

```text
dist/
  bin/my-app
  lib/libfoo.so
```

`my-app` has `RUNPATH=$ORIGIN/../lib`.

Expected result:

```text
$ORIGIN/../lib expands to dist/lib
libfoo.so resolved from dist/lib/libfoo.so
```

### 17.4 Ambiguous Candidate

Input:

```text
dist/
  bin/my-app
  lib/libfoo.so
  alt-lib/libfoo.so
```

If lookup by exact search path does not disambiguate and fallback index finds both candidates:

Expected result:

```text
Ambiguous dependency: libfoo.so
Candidates:
  dist/lib/libfoo.so
  dist/alt-lib/libfoo.so
```

---

## 18. Development Constraints for Codex

Follow these constraints carefully:

1. Do not rewrite the project from scratch.
2. Preserve existing public CLI behavior.
3. Keep changes small and reviewable.
4. Prefer adding focused modules over growing huge functions.
5. Use existing scanner and profile models where possible.
6. Do not introduce heavy external dependencies unless already present or clearly justified.
7. Do not require Docker for the new v0.7 core tests.
8. Keep file and path handling safe and deterministic.
9. Keep JSON output stable and Pydantic-serializable.
10. Keep terminal output readable and concise.
11. Prefer explicit diagnostics over silent fallback behavior.
12. If exact architecture differs from this handoff, adapt to the actual codebase while preserving the intended product behavior.

---

## 19. Recommended Order of Work

Use this order to reduce risk:

```text
1. Inspect existing scanner/report/profile/CLI structure.
2. Add dependency graph models.
3. Add unit tests for graph model serialization.
4. Add bundle file discovery/indexing.
5. Add $ORIGIN path expansion tests.
6. Add local dependency resolution for direct DT_NEEDED.
7. Add recursive traversal and cycle protection.
8. Add target-profile fallback resolution.
9. Integrate with scan JSON and terminal output.
10. Integrate with compare diagnostics.
11. Add CLI tests.
12. Update README.
13. Add v0.7 release note.
14. Run full quality checks.
```

---

## 20. Definition of Done

The v0.7 development pass is done when a user can run this workflow:

```bash
uv run compatlab profiles generate \
  --from-image ubuntu:22.04 \
  --runtime-preset cpp-runtime \
  --name ubuntu-2204-cpp-runtime \
  --output /tmp/ubuntu-2204-cpp-runtime.yaml

uv run compatlab compare ./dist/my-app \
  --target-file /tmp/ubuntu-2204-cpp-runtime.yaml \
  --bundle-root ./dist \
  --recursive \
  --json /tmp/compatlab-v0.7-report.json
```

And CompatLab can explain:

- which dependencies came from the local bundle;
- which dependencies are expected from the target profile;
- which dependencies are missing;
- which bundled libraries are incompatible with the target;
- where in the dependency graph each problem originated.

This is the main value of v0.7.
