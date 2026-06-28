# CompatLab ArtifactDoctor — Codex Context for v0.3

Date: 2026-06-28

This document is a handoff/context file for Codex. It describes the next development step for the Python-first project **CompatLab ArtifactDoctor**.

The goal is to implement **v0.3: the first real compatibility comparison engine**.

---

## 1. Project Summary

**CompatLab ArtifactDoctor** is a Python-first CLI tool for preflight compatibility checks of Linux binary artifacts.

The product goal is not to be another raw ELF dumper. The goal is to answer a practical engineering question:

> Will this Linux artifact run on the target Linux system, and if not, why?

The first product direction is intentionally narrow:

- one ELF binary or shared library as input;
- one target Linux profile as compatibility baseline;
- explainable compatibility problems;
- machine-readable JSON reports;
- CLI-first workflow suitable for CI.

Long-term ideas such as wheel/RPM/DEB/rootfs analysis, HTML reports, UI, dependency graphs, SBOM/security scanning, and Go helpers are explicitly outside the current implementation step.

---

## 2. Current State: v0.2 Implemented

Version 0.2 has already been implemented and pushed to GitHub.

Current implemented behavior:

- Python-first project using `uv`.
- Typer-based CLI.
- Rich-based pretty terminal output.
- Pydantic report/profile/problem models.
- YAML target profiles.
- Test setup with pytest, ruff, and pytest-cov.
- `compatlab scan PATH` uses system `readelf` and extracts real ELF metadata.
- `compatlab compare PATH --target TARGET` exists but still does not perform real compatibility rules.

Current `scan` can extract:

- ELF class;
- endianness;
- OS ABI;
- machine/architecture;
- ELF type;
- entry point;
- dynamic/static signal;
- program interpreter from `PT_INTERP`;
- direct `DT_NEEDED` libraries;
- `RPATH`;
- `RUNPATH`;
- required `GLIBC_*`, `GLIBCXX_*`, and `CXXABI_*` symbol versions.

Example current scan output:

```text
Artifact: /bin/bash
Kind: ELF
Size: 1446024 bytes
Class: ELF64
Endianness: little
OS ABI: UNIX - System V
Machine: Advanced Micro Devices X86-64
ELF Type: DYN
Entry point: 0x34360
Dynamic: yes
Interpreter: /lib64/ld-linux-x86-64.so.2
Needed libraries:
  - libtinfo.so.6
  - libc.so.6
RPATH: none
RUNPATH: none
Required versions:
  GLIBC:
    - GLIBC_2.2.5
    - GLIBC_2.3
    - GLIBC_2.3.4
    - GLIBC_2.4
    - GLIBC_2.8
    - GLIBC_2.11
    - GLIBC_2.14
    - GLIBC_2.15
    - GLIBC_2.25
    - GLIBC_2.33
    - GLIBC_2.34
    - GLIBC_2.36
    - GLIBC_2.38
Scan: OK
Problems: 0
Warnings: 0
```

Current quality gate:

```bash
make check
```

Current Makefile has targets such as:

```makefile
test:
	uv run pytest

coverage:
	uv run pytest --cov=compatlab --cov-report=term-missing --cov-report=xml

coverage-html:
	uv run pytest --cov=compatlab --cov-report=term-missing --cov-report=html

check: coverage lint format-check

lint:
	uv run ruff check .

format:
	uv run ruff format .

format-check:
	uv run ruff format --check .

run-scan:
	uv run compatlab scan /bin/bash

run-profiles:
	uv run compatlab profiles list
```

Current test result:

```text
10 passed
TOTAL coverage: 88%
```

---

## 3. v0.3 Goal

Implement the first real compatibility comparison engine.

The command:

```bash
uv run compatlab compare /bin/bash --target ubuntu-1804
```

should no longer return a stub result.

It should:

1. scan the input artifact using the existing ELF scanner;
2. load the selected target profile;
3. compare extracted ELF facts against the target profile;
4. generate compatibility problems/warnings;
5. print real PASS/FAIL output;
6. write real problems to JSON when `--json` is used;
7. return CI-friendly exit codes.

The product shift for v0.3:

```text
v0.1: project skeleton
v0.2: ELF x-ray / scan
v0.3: first diagnosis / compare
```

---

## 4. Scope for v0.3

Implement compatibility checks for:

1. architecture mismatch;
2. dynamic linker / interpreter availability;
3. too-new GLIBC requirements;
4. too-new GLIBCXX requirements;
5. too-new CXXABI requirements;
6. direct `DT_NEEDED` libraries not listed in target profile;
7. suspicious `RPATH` / `RUNPATH` values.

Use the existing scan report model if possible. Avoid duplicating scan logic inside compare.

Recommended flow:

```text
CLI compare command
  -> run existing ELF scanner
  -> load target profile
  -> run compare engine
  -> attach problems/warnings to ArtifactReport
  -> render pretty output or JSON
  -> return proper exit code
```

---

## 5. Explicit Non-Goals for v0.3

Do **not** implement in this step:

- recursive dependency resolver;
- local filesystem library resolution;
- rootfs/container scanning;
- wheel scanning;
- RPM/DEB scanning;
- HTML reports;
- web UI;
- database;
- server/daemon mode;
- `pyelftools` backend;
- Go helper;
- automatic binary patching with `patchelf`;
- SBOM/security scanning;
- vulnerability scanning.

This step is only about checking already extracted ELF facts against target profiles.

---

## 6. Target Profile Requirements

The existing target profile model/YAML may need to be extended.

Keep the schema simple and readable.

Suggested target profile shape:

```yaml
id: ubuntu-2204
name: Ubuntu 22.04
arch: x86_64
libc:
  family: glibc
  version: "2.35"
libstdcxx:
  max_glibcxx: "3.4.30"
  max_cxxabi: "1.3.13"
interpreter_paths:
  - /lib64/ld-linux-x86-64.so.2
  - /lib/x86_64-linux-gnu/ld-linux-x86-64.so.2
provided_libraries:
  - libc.so.6
  - libtinfo.so.6
  - libstdc++.so.6
  - libgcc_s.so.1
  - libm.so.6
  - libdl.so.2
  - libpthread.so.0
  - librt.so.1
```

Alternative flat schema is acceptable if the current codebase is simpler that way:

```yaml
id: ubuntu-2204
name: Ubuntu 22.04
arch: x86_64
glibc: "2.35"
glibcxx: "3.4.30"
cxxabi: "1.3.13"
interpreter_paths:
  - /lib64/ld-linux-x86-64.so.2
provided_libraries:
  - libc.so.6
  - libtinfo.so.6
```

Important: do not over-engineer the profile schema. It can be refined later.

---

## 7. Compatibility Rules

### 7.1 Architecture Compatibility

Compare normalized artifact machine against target profile architecture.

`readelf` machine names may look like:

```text
Advanced Micro Devices X86-64
AArch64
Intel 80386
```

Normalize them to stable internal names:

```text
Advanced Micro Devices X86-64 -> x86_64
x86-64 -> x86_64
AMD X86-64 -> x86_64
Intel 80386 -> x86
i386 -> x86
AArch64 -> aarch64
ARM aarch64 -> aarch64
```

If normalized artifact architecture does not match target profile `arch`, emit:

```text
wrong.architecture
```

Suggested severity:

```text
CRITICAL
```

Example problem:

```json
{
  "id": "wrong.architecture",
  "severity": "CRITICAL",
  "title": "Artifact architecture does not match target profile",
  "details": "Artifact architecture is x86_64, but target profile expects aarch64.",
  "evidence": {
    "artifact_arch": "x86_64",
    "target_arch": "aarch64"
  }
}
```

---

### 7.2 Dynamic Linker / Interpreter Compatibility

If ELF is dynamic and has no interpreter, emit:

```text
missing.interpreter
```

Suggested severity:

```text
HIGH
```

If interpreter is present but not listed in target profile `interpreter_paths`, emit:

```text
profile.interpreter_not_provided
```

Suggested severity:

```text
HIGH
```

Example:

```json
{
  "id": "profile.interpreter_not_provided",
  "severity": "HIGH",
  "title": "Target profile does not provide the required dynamic linker",
  "details": "Artifact expects /lib64/ld-linux-x86-64.so.2, but target ubuntu-1804 does not list it as provided.",
  "evidence": {
    "interpreter": "/lib64/ld-linux-x86-64.so.2",
    "target": "ubuntu-1804"
  }
}
```

---

### 7.3 GLIBC Compatibility

Find the maximum required `GLIBC_*` version from the scan report.

Compare it against target profile glibc version.

If required version is newer than provided version, emit:

```text
glibc.too_new
```

Suggested severity:

```text
HIGH
```

Example:

```json
{
  "id": "glibc.too_new",
  "severity": "HIGH",
  "title": "Artifact requires newer glibc than target provides",
  "details": "Artifact requires GLIBC_2.38, but target ubuntu-1804 provides up to GLIBC_2.27.",
  "evidence": {
    "required": "GLIBC_2.38",
    "provided": "GLIBC_2.27",
    "target": "ubuntu-1804"
  },
  "suggestions": [
    "Rebuild the artifact on an older baseline distribution.",
    "Use a target-compatible build container.",
    "Choose a newer target profile."
  ]
}
```

Important: compare versions numerically, not lexicographically.

Bad:

```python
"2.9" > "2.38"
```

Good:

```python
"2.38" -> (2, 38)
"2.9" -> (2, 9)
```

---

### 7.4 GLIBCXX Compatibility

Find the maximum required `GLIBCXX_*` version from the scan report.

Compare it against target profile `glibcxx` / `libstdcxx.max_glibcxx`.

If required version is newer than provided version, emit:

```text
glibcxx.too_new
```

Suggested severity:

```text
HIGH
```

Example:

```json
{
  "id": "glibcxx.too_new",
  "severity": "HIGH",
  "title": "Artifact requires newer libstdc++ symbols than target provides",
  "details": "Artifact requires GLIBCXX_3.4.30, but target rocky-8 provides up to GLIBCXX_3.4.25.",
  "evidence": {
    "required": "GLIBCXX_3.4.30",
    "provided": "GLIBCXX_3.4.25"
  }
}
```

---

### 7.5 CXXABI Compatibility

Find the maximum required `CXXABI_*` version from the scan report.

Compare it against target profile `cxxabi` / `libstdcxx.max_cxxabi`.

If required version is newer than provided version, emit:

```text
cxxabi.too_new
```

Suggested severity:

```text
HIGH
```

---

### 7.6 Direct Library Availability

Compare direct `DT_NEEDED` entries against target profile `provided_libraries`.

If artifact requires a library that is not listed in the target profile, emit:

```text
profile.library_not_provided
```

Suggested severity:

```text
HIGH
```

Example:

```json
{
  "id": "profile.library_not_provided",
  "severity": "HIGH",
  "title": "Target profile does not list a required shared library",
  "details": "Artifact requires libtinfo.so.6, but target ubuntu-1804 does not list it as provided.",
  "evidence": {
    "library": "libtinfo.so.6",
    "target": "ubuntu-1804"
  }
}
```

Important: this is not recursive dependency resolution. It is only direct `DT_NEEDED` vs profile.

---

### 7.7 Suspicious RPATH/RUNPATH

Check each `RPATH` and `RUNPATH` entry.

Suspicious absolute/build-time paths include:

```text
/home
/tmp
/var/tmp
/build
/workspace
/dist
```

If suspicious RPATH is found, emit one of:

```text
bad.rpath.absolute
bad.rpath.build_path
```

If suspicious RUNPATH is found, emit one of:

```text
bad.runpath.absolute
bad.runpath.build_path
```

Suggested severity:

```text
MEDIUM
```

Example:

```json
{
  "id": "bad.runpath.build_path",
  "severity": "MEDIUM",
  "title": "RUNPATH contains a build-time path",
  "details": "RUNPATH contains /home/user/build/lib, which is unlikely to exist on the target system.",
  "evidence": {
    "runpath": "/home/user/build/lib"
  }
}
```

Absolute paths are not always fatal, so do not make them CRITICAL in v0.3.

---

## 8. Version Utilities

Add small, well-tested utilities for version handling.

Suggested module:

```text
compatlab/src/compare/versions.py
```

Required functions could include:

```python
def parse_numeric_version(version: str) -> tuple[int, ...]:
    ...


def is_version_newer(required: str, provided: str) -> bool:
    ...


def max_required_version(versions: list[SymbolVersion], namespace: str) -> SymbolVersion | None:
    ...
```

Input examples:

```text
GLIBC_2.38 -> namespace GLIBC, version 2.38
GLIBCXX_3.4.30 -> namespace GLIBCXX, version 3.4.30
CXXABI_1.3.13 -> namespace CXXABI, version 1.3.13
```

Potential tricky cases:

```text
2.9 < 2.38
3.4.9 < 3.4.29
1.3 < 1.3.1
```

Keep it simple. Numeric tuple comparison is enough for this step.

---

## 9. Problem Severity and Exit Codes

Recommended severity behavior:

```text
CRITICAL — almost certainly cannot run
HIGH     — high probability of runtime failure
MEDIUM   — portability risk
LOW      — suspicious but not immediately fatal
INFO     — diagnostic note
```

Exit code behavior:

```text
0 — PASS, or no HIGH/CRITICAL problems
1 — HIGH/CRITICAL compatibility problems found
2 — invalid input, missing target profile, scan failure, or command errors
```

For `scan`:

- keep current behavior mostly unchanged;
- return `0` for successful scan even with warnings;
- return `2` for invalid input / scan failure.

For `compare`:

- return `0` if there are no HIGH/CRITICAL problems;
- return `1` if any HIGH/CRITICAL problems exist;
- return `2` for invalid target, failed scan, missing input, etc.

---

## 10. Pretty Output Expectations

`compatlab compare` should clearly show:

- artifact path;
- target profile;
- compatibility status;
- important ELF facts;
- problems grouped/listed with severity;
- warnings if any.

Example PASS:

```text
Artifact: /bin/bash
Target: ubuntu-2404 (Ubuntu 24.04)
Compatibility: PASS

Problems: 0
Warnings: 0
```

Example FAIL:

```text
Artifact: /bin/bash
Target: ubuntu-1804 (Ubuntu 18.04)
Compatibility: FAIL

HIGH glibc.too_new
Artifact requires GLIBC_2.38, but target ubuntu-1804 provides up to GLIBC_2.27.

Problems: 1
Warnings: 0
```

Do not overcomplicate the Rich output. Clarity is more important than visual decoration.

---

## 11. JSON Output Expectations

`compare --json` should include:

- artifact metadata;
- extracted ELF facts;
- target profile information or target ID;
- generated compatibility problems;
- warnings if any.

Example command:

```bash
uv run compatlab compare /bin/bash --target ubuntu-1804 --json /tmp/compare.json
jq '.problems' /tmp/compare.json
```

The JSON should be stable enough for future CI usage.

---

## 12. Testing Strategy

Add tests for comparison logic without depending on exact host `/bin/bash` versions.

Prefer model-based fixtures.

Recommended test files/modules:

```text
compatlab/tests/test_compare_versions.py
compatlab/tests/test_compare_architecture.py
compatlab/tests/test_compare_rules.py
compatlab/tests/test_compare_cli.py
```

Test cases to add:

1. version parsing:
   - `2.38` -> `(2, 38)`;
   - `3.4.29` -> `(3, 4, 29)`;
   - `2.9 < 2.38`;

2. max required version:
   - choose `GLIBC_2.38` from several GLIBC versions;
   - ignore other namespaces;

3. architecture normalization:
   - `Advanced Micro Devices X86-64` -> `x86_64`;
   - `AArch64` -> `aarch64`;

4. glibc too-new rule:
   - artifact requires `GLIBC_2.38`, target provides `2.27` -> problem;
   - artifact requires `GLIBC_2.27`, target provides `2.38` -> no problem;

5. glibcxx too-new rule;

6. cxxabi too-new rule;

7. missing interpreter rule;

8. interpreter not provided rule;

9. direct library not provided rule;

10. suspicious RPATH/RUNPATH rules;

11. CLI compare smoke behavior:
   - target profile loads;
   - command returns a meaningful result;
   - JSON file is written;
   - avoid relying on exact host symbol versions.

Keep coverage reasonably high. Current coverage is about 88%, so avoid a large drop.

---

## 13. Acceptance Criteria

After implementation, the following commands should work:

```bash
uv run compatlab compare /bin/bash --target ubuntu-2404
uv run compatlab compare /bin/bash --target ubuntu-1804
uv run compatlab compare /bin/bash --target ubuntu-1804 --json /tmp/compare.json
jq '.problems' /tmp/compare.json
make check
```

Expected behavior:

- `compare` uses the real scan backend;
- `compare` loads the target profile;
- `compare` produces real PASS/FAIL result;
- too-new GLIBC should be detected when the artifact requires newer GLIBC than target provides;
- JSON contains real problems;
- tests pass;
- ruff check passes;
- ruff format check passes;
- coverage remains healthy.

---

## 14. Suggested Implementation Order

1. Inspect current profile models and YAML files.
2. Extend profile schema minimally if needed.
3. Add version utility functions with tests.
4. Add architecture normalization with tests.
5. Add compare rule functions with model-based tests.
6. Update compare engine to use existing scan report.
7. Update CLI compare command output and exit codes.
8. Update JSON report if needed.
9. Add CLI smoke tests.
10. Update README / release notes draft if appropriate.
11. Run:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
make check
```

---

## 15. Ready-to-Use Codex Prompt

Use this prompt when starting the v0.3 implementation:

```text
We continue the Python-first CompatLab ArtifactDoctor project.

Current state:
- v0.2 is implemented and pushed to GitHub.
- `compatlab scan PATH` now uses system `readelf` and extracts real ELF metadata:
  - ELF class
  - endianness
  - OS ABI
  - machine
  - ELF type
  - entry point
  - dynamic/static signal
  - program interpreter
  - DT_NEEDED libraries
  - RPATH
  - RUNPATH
  - required GLIBC, GLIBCXX and CXXABI symbol versions
- `compatlab compare PATH --target TARGET` still does not implement real compatibility rules yet.
- Target profiles already exist as YAML files.
- Tests, Ruff and coverage are configured.
- `make check` should remain green.

Goal for this step:
Implement v0.3: the first real compatibility comparison engine.

Scope:
- Make `compatlab compare PATH --target TARGET` scan the artifact using the existing ELF scanner.
- Load the selected target profile.
- Run compatibility checks against the profile.
- Attach generated problems/warnings to the report.
- Render real PASS/FAIL output.
- Write real comparison problems to JSON when `--json` is used.
- Add tests for comparison rules.

Compatibility rules to implement:
1. Architecture compatibility:
   - Normalize readelf machine names to profile architecture names.
   - Detect mismatch as `wrong.architecture`.

2. Dynamic linker/interpreter compatibility:
   - If dynamic ELF has no interpreter, emit `missing.interpreter`.
   - If interpreter is present but not listed in the profile, emit `profile.interpreter_not_provided`.

3. GLIBC compatibility:
   - Find the maximum required GLIBC version from the scan report.
   - Compare it with target profile glibc version.
   - If required > provided, emit `glibc.too_new`.

4. GLIBCXX compatibility:
   - Find the maximum required GLIBCXX version.
   - Compare it with target profile GLIBCXX/libstdc++ capability.
   - If required > provided, emit `glibcxx.too_new`.

5. CXXABI compatibility:
   - Find the maximum required CXXABI version.
   - Compare it with target profile CXXABI capability.
   - If required > provided, emit `cxxabi.too_new`.

6. Required library availability:
   - Compare direct DT_NEEDED entries with libraries listed in the target profile.
   - If a required library is not listed, emit `profile.library_not_provided`.
   - Do not implement recursive dependency resolution yet.

7. Suspicious RPATH/RUNPATH:
   - Warn about absolute build-time paths such as `/home`, `/tmp`, `/build`, `/workspace`, `/var/tmp`.
   - Use existing problem IDs such as `bad.rpath.absolute`, `bad.rpath.build_path`, `bad.runpath.absolute`, `bad.runpath.build_path`.

Version comparison:
- Do not compare version strings lexicographically.
- Implement tuple-based numeric comparison:
  - `2.38` -> `(2, 38)`
  - `3.4.29` -> `(3, 4, 29)`

Exit code behavior:
- `compatlab compare` should return:
  - `0` when no HIGH/CRITICAL problems are found;
  - `1` when HIGH/CRITICAL compatibility problems are found;
  - `2` for invalid input, missing target profile, failed scan, or command errors.
- Keep `scan` behavior unchanged except if shared report logic requires small adjustments.

Profile updates:
- Extend target profile models/YAML if needed to include:
  - interpreter paths
  - provided libraries
  - max GLIBCXX version
  - max CXXABI version
- Keep profile schema simple and readable.

Testing:
- Add unit tests for:
  - version parsing/comparison
  - max required version selection
  - architecture normalization
  - glibc too-new rule
  - glibcxx too-new rule
  - cxxabi too-new rule
  - missing interpreter rule
  - library not provided rule
  - suspicious RPATH/RUNPATH rule
- Avoid tests depending on exact host `/bin/bash` symbol versions.
- Use model fixtures where possible.

Do not implement in this step:
- dependency resolver
- recursive graph
- rootfs/container scan
- wheel/RPM/DEB scan
- HTML report
- web UI
- database
- server/daemon mode
- pyelftools backend
- Go helper
- automatic patching with patchelf

Acceptance criteria:
- `uv run compatlab compare /bin/bash --target ubuntu-2404` produces a real compatibility result.
- `uv run compatlab compare /bin/bash --target ubuntu-1804` detects too-new GLIBC on modern hosts when applicable.
- `uv run compatlab compare /bin/bash --target ubuntu-1804 --json /tmp/compare.json` writes real problems to JSON.
- `jq '.problems' /tmp/compare.json` works.
- `uv run pytest` passes.
- `uv run ruff check .` passes.
- `uv run ruff format --check .` passes.
- `make check` passes.
```

---

## 16. Product Reminder

Do not lose the main product idea.

CompatLab is not just an ELF inspector.

The value is:

> Show what the artifact needs. Show what the target provides. Explain where they do not match. Make the failure understandable before delivery.

For v0.3, this means:

```text
/bin/bash requires GLIBC_2.38
ubuntu-1804 provides GLIBC_2.27
=> compatibility FAIL
=> rebuild on older baseline or use newer target
```

That is the first real ArtifactDoctor moment.
