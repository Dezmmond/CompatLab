# CompatLab ArtifactDoctor 1.1 — Codex Development Specification

## 0. Purpose of this document

This document is a handoff package for a Codex agent that will continue development of the CompatLab ArtifactDoctor project.

The target release is **CompatLab ArtifactDoctor 1.1**.

The main goal of this release is to add first-class support for **Python wheel (`.whl`) artifacts** by detecting native ELF extensions inside wheel packages and reusing the existing ELF compatibility, diagnostics, JSON report, HTML report, and CI gate pipeline.

The intended development mode is **fast and pragmatic**. Do not over-optimize the design. Keep caution at approximately **20-30%**: protect the repository from obvious breakage, unsafe archive extraction, and public CLI/JSON regressions, but prefer completing the feature over endlessly polishing abstractions.

---

## 1. Project context

CompatLab ArtifactDoctor is a Python-first CLI tool for checking whether Linux binary artifacts are likely to run on a selected target Linux profile before shipment.

The current product focus is static compatibility diagnosis for Linux artifacts:

- ELF metadata extraction;
- target Linux profile comparison;
- glibc / libstdc++ / CXXABI version checks;
- dynamic linker checks;
- `DT_NEEDED` shared library checks;
- architecture mismatch checks;
- suspicious `RPATH` / `RUNPATH` checks;
- bundle-aware dependency resolution;
- JSON and HTML reports;
- diagnostics suitable for CI quality gates.

The project has already passed through several important releases:

### v0.7

Added bundle-aware recursive dependency resolution:

- `--bundle-root DIR`;
- `--recursive`;
- bundle indexing;
- `RUNPATH` / `RPATH` / `$ORIGIN` lookup;
- dependency states: `bundled`, `target`, `missing`, `ambiguous`;
- `dependency_graph` in JSON;
- recursive compatibility comparison for bundled ELF files.

### v0.8

Added normalized diagnostics and CI gates:

- stable diagnostic models;
- stable diagnostic issue codes;
- `summary` and `diagnostics` fields in JSON;
- `--fail-on error|warning|never`;
- terminal diagnostic summaries;
- tests for diagnostics, gates, and JSON output.

### v0.9

Added static self-contained HTML reports:

- `--html PATH` for `scan`;
- `--html PATH` for `compare`;
- embedded CSS;
- no external scripts, fonts, images, CDN links, server, database, or daemon;
- diagnostic summary section;
- normalized diagnostic section;
- bundle dependency section;
- legacy problems/warnings section;
- compact ELF/target/schema metadata sections;
- HTML escaping tests.

### v0.10

Performed internal architecture refactoring:

- replaced previous `compatlab/src/...` package layout with direct `compatlab/...` layout;
- replaced Typer CLI with `argparse`;
- split CLI orchestration into service modules:
  - `compatlab.services.artifacts`;
  - `compatlab.services.profiles`;
  - `compatlab.services.reports`;
  - `compatlab.services.exceptions`;
- moved shared Pydantic models into `compatlab.models`;
- replaced dynamic package export discovery with explicit `__init__.py` imports and `__all__` definitions;
- reorganized `compatlab.profile` into focused modules;
- preserved existing CLI behavior;
- explicitly prepared the codebase for future artifact scanners such as wheel, RPM, and DEB.

---

## 2. Target release summary

Release name:

```text
CompatLab ArtifactDoctor 1.1
```

Suggested release subtitle:

```text
Python Wheel Compatibility Scanning
```

Primary user-facing capability:

```bash
uv run compatlab scan ./dist/example-1.0.0-cp311-cp311-linux_x86_64.whl
uv run compatlab compare ./dist/example-1.0.0-cp311-cp311-linux_x86_64.whl --target ubuntu-2204
uv run compatlab compare ./dist/example-1.0.0-cp311-cp311-linux_x86_64.whl \
  --target-file ./profiles/prod.yaml \
  --fail-on warning \
  --json report.json \
  --html report.html
```

CompatLab should inspect a wheel package, identify native ELF files inside it, run the existing ELF scanner and compatibility comparison logic for each native entry, and aggregate the result into one wheel-level report.

---

## 3. Product goal

The user should be able to check a built Python wheel before publishing or deploying it.

The key question CompatLab 1.1 should answer is:

> Does this Python wheel contain native Linux binaries, and if yes, are those binaries compatible with the selected target Linux profile?

Example expected output meaning:

```text
Wheel: example-1.0.0-cp311-cp311-linux_x86_64.whl
Package: example 1.0.0
Native entries: 2

OK   example/_fastjson.cpython-311-x86_64-linux-gnu.so
FAIL example/_crypto.cpython-311-x86_64-linux-gnu.so
     CL_SYMBOL_GLIBCXX_TOO_NEW: requires GLIBCXX_3.4.30, target has GLIBCXX_3.4.28

Summary: failed, errors=1, warnings=0
```

This is not a Python dependency checker, not a vulnerability scanner, and not a package installer. It is a static binary compatibility preflight check for native files embedded in wheels.

---

## 4. Scope for version 1.1

### 4.1 In scope

Implement support for `.whl` input artifacts in existing `scan` and `compare` workflows.

Required capabilities:

1. Detect artifact kind automatically:
   - ELF;
   - wheel;
   - unknown / unsupported.

2. Parse wheel metadata:
   - package name;
   - package version;
   - wheel tags;
   - `Root-Is-Purelib`;
   - `Generator`, if easy;
   - `Build`, if present.

3. Safely inspect the wheel archive:
   - validate that it is a zip archive;
   - locate `.dist-info/WHEEL`;
   - locate `.dist-info/METADATA`;
   - locate `.dist-info/RECORD` when present;
   - reject or diagnose path traversal entries;
   - avoid unsafe extraction.

4. Discover native entries:
   - files ending with `.so`;
   - files containing `.so.`;
   - files that look like ELF by magic bytes even without normal extension;
   - native extensions such as `*.cpython-311-x86_64-linux-gnu.so`;
   - `*.abi3.so`.

5. Extract only necessary native entries into a temporary directory.

6. Reuse the existing ELF scanner for extracted native entries.

7. Reuse the existing compatibility comparison rules for each native entry.

8. Aggregate diagnostics:
   - wheel-level diagnostics;
   - entry-level ELF diagnostics;
   - existing diagnostic summary counters;
   - `--fail-on` behavior.

9. Extend JSON reports without breaking existing ELF report consumers.

10. Extend HTML reports to show wheel metadata and native entries.

11. Extend terminal output to make wheel results readable.

12. Add tests:
   - unit tests;
   - CLI tests;
   - JSON tests;
   - HTML tests;
   - error handling tests;
   - unsafe archive tests.

13. Update README and add release notes for v1.1.

### 4.2 Out of scope

Do not implement these in v1.1:

- RPM scanning;
- DEB scanning;
- SBOM generation;
- vulnerability scanning;
- `auditwheel repair`;
- automatic `patchelf` mutation;
- wheel installation into virtualenv;
- importing Python modules from the wheel;
- executing wheel code;
- running artifacts inside Docker;
- Docker image mutation, commit, save, or push;
- arbitrary package installation;
- Python dependency resolution from `Requires-Dist`;
- PyPI integration;
- public plugin system;
- server mode;
- web UI;
- database;
- breaking CLI changes;
- breaking JSON schema changes.

---

## 5. Development principle for Codex

Use this release to make real progress.

Do not behave like a scared intern protecting every line of code from sunlight. The repository has just been refactored specifically to support new artifact types. Use that structure.

Acceptable risk level:

```text
20-30% cautious, 70-80% implementation-oriented.
```

Meaning:

- Keep existing commands working.
- Keep existing tests passing.
- Add tests for the new behavior.
- Avoid unsafe zip extraction.
- Do not silently swallow serious errors.
- But do not postpone implementation because a perfect artifact abstraction could exist someday.
- Do not build a plugin framework unless the current code almost forces it.
- Do not split every 40 lines into five files just to look architectural.
- Prefer small, understandable modules with direct data flow.

The agent may refactor internals when needed, but must preserve user-facing behavior for existing ELF and bundle workflows.

---

## 6. Expected architecture

The exact current project structure may differ. Inspect the repository first.

Suggested target shape:

```text
compatlab/
  artifacts/
    __init__.py
    detect.py
    kinds.py
    wheel.py
  scanners/
    __init__.py
    elf.py                  # existing or current equivalent
    wheel.py                # new wheel inspection/scanning logic
  services/
    artifacts.py            # existing scan/compare orchestration, extend carefully
    reports.py              # existing report writing/enrichment, extend carefully
  reports/
    html.py                 # existing or equivalent, extend carefully
  models.py                 # existing central Pydantic models, extend carefully
```

If the repository already has better names, follow the existing style instead of forcing this exact tree.

### 6.1 Artifact kind detection

Add an internal artifact kind enum/model.

Suggested values:

```python
class ArtifactKind(str, Enum):
    ELF = "elf"
    WHEEL = "wheel"
    UNKNOWN = "unknown"
```

Detection should be pragmatic:

1. If path suffix is `.whl` and file is a zip archive, treat as wheel.
2. If file starts with ELF magic bytes, treat as ELF.
3. Otherwise return unsupported/unknown diagnostic or command error using existing exception handling style.

Optional CLI override:

```bash
--artifact-kind auto|elf|wheel
```

If adding this flag becomes noisy, skip it for v1.1. Automatic detection is enough for the first pass.

### 6.2 Wheel metadata models

Add Pydantic models to `compatlab.models` or a focused model module if the project already separates report models.

Suggested models:

```python
class WheelPackageMetadata(BaseModel):
    name: str | None = None
    version: str | None = None
    build: str | None = None
    generator: str | None = None
    root_is_purelib: bool | None = None
    tags: list[str] = Field(default_factory=list)
    dist_info_dir: str | None = None

class WheelNativeEntry(BaseModel):
    path: str
    size: int | None = None
    extracted_path: str | None = None  # Do not expose absolute temp path in final JSON if avoidable.
    elf: ElfFacts | None = None        # Use actual existing ELF facts model name.
    diagnostics: list[DiagnosticIssue] = Field(default_factory=list)

class WheelScanResult(BaseModel):
    artifact_kind: Literal["wheel"] = "wheel"
    path: str
    package: WheelPackageMetadata
    native_entries: list[WheelNativeEntry] = Field(default_factory=list)
    summary: DiagnosticSummary | None = None
    diagnostics: list[DiagnosticIssue] = Field(default_factory=list)
```

Do not expose temp filesystem paths in stable JSON unless the project already exposes scanner internals. Prefer paths inside the wheel archive.

### 6.3 Wheel scanner module

Implement a module responsible for wheel archive inspection.

Suggested responsibilities:

- open zip safely;
- list archive entries;
- validate entry names;
- parse metadata files;
- identify native ELF candidates;
- extract native candidates to temporary files for existing ELF scanner;
- return structured wheel scan data.

Suggested implementation notes:

- Use Python standard library: `zipfile`, `email.parser`, `tempfile`, `pathlib`, `hashlib` if needed.
- Avoid new dependencies unless truly necessary.
- Never call wheel code.
- Never import package code from the wheel.
- Never add the wheel to `sys.path`.
- Never extract archive entries with raw `ZipFile.extractall()`.
- Use controlled extraction: read selected file bytes and write to a normalized temp path.

Safe archive path check:

```python
def is_safe_archive_path(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        name
        and not path.is_absolute()
        and ".." not in path.parts
        and "" not in path.parts
    )
```

This does not need to be perfect like a hardened sandbox, but it must block obvious zip-slip paths.

---

## 7. CLI behavior

### 7.1 Existing behavior to preserve

These commands must continue working:

```bash
uv run compatlab scan ./app
uv run compatlab scan ./dist/my-app --bundle-root ./dist --recursive
uv run compatlab compare ./app --target ubuntu-1804
uv run compatlab compare ./app --target-file ./local.yaml
uv run compatlab compare ./dist/my-app --target-file ./local.yaml --bundle-root ./dist --recursive
uv run compatlab profiles list
uv run compatlab profiles show ubuntu-1804
uv run compatlab profiles detect
uv run compatlab profiles generate --from-current --name local --output local.yaml
uv run compatlab profiles generate --from-image ubuntu:22.04 --name ubuntu-2204-docker --output ubuntu-2204.yaml
uv run compatlab profiles runtime-presets list
uv run compatlab profiles validate ubuntu-2204.yaml
```

### 7.2 New behavior

Add wheel support to existing commands:

```bash
uv run compatlab scan ./dist/demo-1.0.0-py3-none-any.whl
uv run compatlab scan ./dist/demo-1.0.0-cp311-cp311-linux_x86_64.whl
uv run compatlab scan ./dist/demo-1.0.0-cp311-cp311-linux_x86_64.whl --json report.json
uv run compatlab scan ./dist/demo-1.0.0-cp311-cp311-linux_x86_64.whl --html report.html
```

```bash
uv run compatlab compare ./dist/demo-1.0.0-cp311-cp311-linux_x86_64.whl --target ubuntu-2204
uv run compatlab compare ./dist/demo-1.0.0-cp311-cp311-linux_x86_64.whl --target-file ./profiles/prod.yaml
uv run compatlab compare ./dist/demo-1.0.0-cp311-cp311-linux_x86_64.whl \
  --target ubuntu-2204 \
  --fail-on warning \
  --json report.json \
  --html report.html
```

### 7.3 Optional new limits

Add only if straightforward:

```bash
--max-wheel-files 1000
--max-wheel-size 200M
--max-wheel-extracted-size 500M
```

If the current CLI does not have a parser for human-readable sizes, use integer bytes:

```bash
--max-wheel-files 1000
--max-wheel-size-bytes 209715200
--max-wheel-extracted-size-bytes 524288000
```

Do not get stuck building a fancy size parser.

---

## 8. Diagnostics

Add wheel-specific diagnostic issue codes.

Suggested codes:

```text
CL_WHEEL_INVALID_ARCHIVE
CL_WHEEL_METADATA_MISSING
CL_WHEEL_WHEEL_METADATA_MISSING
CL_WHEEL_RECORD_MISSING
CL_WHEEL_UNSAFE_PATH
CL_WHEEL_TOO_MANY_FILES
CL_WHEEL_TOO_LARGE
CL_WHEEL_EXTRACTED_TOO_LARGE
CL_WHEEL_NO_NATIVE_EXTENSIONS
CL_WHEEL_NATIVE_ENTRY_SCAN_FAILED
CL_WHEEL_PLATFORM_TAG_UNSUPPORTED
CL_WHEEL_PURELIB_WITH_NATIVE_CODE
CL_WHEEL_NO_DIST_INFO
CL_WHEEL_MULTIPLE_DIST_INFO
```

Recommended severities:

```text
CL_WHEEL_INVALID_ARCHIVE              error
CL_WHEEL_METADATA_MISSING             warning
CL_WHEEL_WHEEL_METADATA_MISSING       warning
CL_WHEEL_RECORD_MISSING               warning
CL_WHEEL_UNSAFE_PATH                  error
CL_WHEEL_TOO_MANY_FILES               error
CL_WHEEL_TOO_LARGE                    error
CL_WHEEL_EXTRACTED_TOO_LARGE          error
CL_WHEEL_NO_NATIVE_EXTENSIONS         info
CL_WHEEL_NATIVE_ENTRY_SCAN_FAILED     error
CL_WHEEL_PLATFORM_TAG_UNSUPPORTED     warning
CL_WHEEL_PURELIB_WITH_NATIVE_CODE     warning
CL_WHEEL_NO_DIST_INFO                 warning
CL_WHEEL_MULTIPLE_DIST_INFO           warning
```

Do not create duplicate diagnostics if existing ELF diagnostics already explain the same concrete problem. For example, if an extracted `.so` requires a too-new `GLIBCXX`, reuse the existing `CL_SYMBOL_GLIBCXX_TOO_NEW` diagnostic instead of inventing a wheel-specific duplicate.

Wheel diagnostics should provide useful context:

```json
{
  "code": "CL_WHEEL_PURELIB_WITH_NATIVE_CODE",
  "severity": "warning",
  "category": "package",
  "message": "Wheel declares Root-Is-Purelib=true but contains native ELF entries.",
  "location": "example/_native.cpython-311-x86_64-linux-gnu.so"
}
```

Use the existing diagnostic model shape. Do not redesign diagnostics.

---

## 9. JSON report expectations

JSON must remain useful for CI and automation.

### 9.1 For pure Python wheel

Example shape:

```json
{
  "artifact": {
    "kind": "wheel",
    "path": "./dist/demo-1.0.0-py3-none-any.whl"
  },
  "package": {
    "type": "wheel",
    "name": "demo",
    "version": "1.0.0",
    "tags": ["py3-none-any"],
    "root_is_purelib": true
  },
  "native_entries": [],
  "summary": {
    "status": "passed",
    "errors": 0,
    "warnings": 0,
    "infos": 1,
    "issue_codes": {
      "CL_WHEEL_NO_NATIVE_EXTENSIONS": 1
    }
  },
  "diagnostics": []
}
```

### 9.2 For native wheel

Example shape:

```json
{
  "artifact": {
    "kind": "wheel",
    "path": "./dist/demo-1.0.0-cp311-cp311-linux_x86_64.whl"
  },
  "package": {
    "type": "wheel",
    "name": "demo",
    "version": "1.0.0",
    "tags": ["cp311-cp311-linux_x86_64"],
    "root_is_purelib": false
  },
  "native_entries": [
    {
      "path": "demo/_native.cpython-311-x86_64-linux-gnu.so",
      "size": 123456,
      "elf": {
        "arch": "x86_64"
      },
      "diagnostics": []
    }
  ],
  "summary": {
    "status": "passed",
    "errors": 0,
    "warnings": 0,
    "infos": 0,
    "issue_codes": {}
  },
  "diagnostics": []
}
```

The exact field names may follow existing project style. The important part is to provide:

- artifact kind;
- wheel metadata;
- native entries;
- per-entry ELF facts or compact reference to existing ELF facts;
- aggregated diagnostics;
- summary compatible with `--fail-on` behavior.

### 9.3 Backward compatibility

Do not remove existing JSON fields used by ELF and bundle reports.

If adding new fields to existing models is required, make them optional or additive.

---

## 10. HTML report expectations

Extend the existing static HTML report renderer.

Add sections for wheel input:

```text
Wheel metadata
  - file path
  - package name
  - version
  - tags
  - Root-Is-Purelib
  - dist-info directory

Native entries
  - path inside wheel
  - size
  - scan status
  - compatibility status
  - diagnostic counts

Native compatibility details
  - existing ELF metadata
  - existing compatibility problems/warnings
  - existing normalized diagnostics
```

Keep HTML self-contained.

Requirements:

- no CDN;
- no external JS;
- no external CSS;
- no external fonts;
- escape all paths, names, messages, metadata fields, and diagnostics;
- write HTML before exiting with non-zero code if diagnostics fail the selected `--fail-on` threshold, preserving v0.9 behavior.

---

## 11. Terminal output expectations

The terminal output must be readable, but do not spend half the release making it gorgeous.

Expected scan output for pure Python wheel:

```text
Wheel package
  Path: dist/demo-1.0.0-py3-none-any.whl
  Name: demo
  Version: 1.0.0
  Tags: py3-none-any
  Native entries: 0

Diagnostics
  info CL_WHEEL_NO_NATIVE_EXTENSIONS: Wheel does not contain native ELF entries.
```

Expected compare output for native wheel:

```text
Wheel package
  Path: dist/demo-1.0.0-cp311-cp311-linux_x86_64.whl
  Name: demo
  Version: 1.0.0
  Tags: cp311-cp311-linux_x86_64
  Native entries: 2

Native compatibility
  OK   demo/_fast.cpython-311-x86_64-linux-gnu.so
  FAIL demo/_crypto.cpython-311-x86_64-linux-gnu.so
       CL_SYMBOL_GLIBCXX_TOO_NEW: requires GLIBCXX_3.4.30, target has GLIBCXX_3.4.28

Summary: failed, errors=1, warnings=0, infos=0
```

Follow existing Rich formatting conventions if the project uses Rich tables.

---

## 12. Tests

Do not rely on external internet access.

Prefer generating tiny wheel fixtures in tests using Python standard library.

### 12.1 Fixture strategy

Create test wheels dynamically in `tmp_path`:

```text
demo-1.0.0.dist-info/
  WHEEL
  METADATA
  RECORD

demo/
  __init__.py
  _native.cpython-311-x86_64-linux-gnu.so
```

For ELF content, prefer reusing an existing tiny fixture from the current test suite if one exists.

If no tiny ELF fixture exists, generate or copy a known simple ELF fixture from current project tests. Do not add large binary blobs.

If needed, use `/bin/true` or `/bin/echo` in integration tests only when the test environment reasonably guarantees them. Unit tests should avoid host-specific assumptions where possible.

### 12.2 Required unit tests

Add tests for:

- artifact kind detection:
  - ELF;
  - wheel;
  - unknown;
- valid wheel metadata parsing;
- missing `WHEEL` metadata;
- missing `METADATA`;
- missing `RECORD`;
- pure Python wheel with no native entries;
- native wheel with one `.so`;
- native wheel with multiple `.so` files;
- unsafe archive path: `../evil.so`;
- absolute archive path: `/evil.so`;
- too many files limit;
- archive size limit if implemented;
- extracted size limit if implemented;
- `Root-Is-Purelib: true` with native `.so` warning;
- malformed zip file diagnostic.

### 12.3 Required CLI tests

Add tests for:

```bash
compatlab scan ./demo.whl
compatlab scan ./demo.whl --json report.json
compatlab scan ./demo.whl --html report.html
compatlab compare ./demo.whl --target ubuntu-2204
compatlab compare ./demo.whl --target-file profile.yaml
compatlab compare ./demo.whl --fail-on never --json report.json --html report.html
compatlab compare ./demo.whl --fail-on warning
```

Use actual available built-in profiles or generated temporary profiles, following current test conventions.

### 12.4 Regression tests

Existing ELF and bundle tests must still pass.

Run:

```bash
uv run python -m compileall -q compatlab
uv run pytest -q
uv run ruff check compatlab
uv run ruff format --check compatlab
make check
```

If the project uses `ruff check .` instead of `ruff check compatlab`, follow repository convention.

---

## 13. Suggested implementation sequence

Follow this order to avoid getting lost.

### Step 1 — Baseline inspection

Run:

```bash
git status --short
find compatlab -maxdepth 3 -type f | sort
uv run pytest -q
uv run ruff check compatlab
```

Read these areas first:

```text
compatlab/services/artifacts.py
compatlab/services/reports.py
compatlab/models.py
compatlab/scanner or compatlab/scanners modules
compatlab/reports or HTML renderer modules
tests for scan/compare CLI
tests for diagnostics
tests for HTML reports
```

### Step 2 — Add artifact detection

Implement `ArtifactKind` and `detect_artifact_kind(path)`.

Wire it into `scan` first.

Make sure plain ELF input still follows the old path.

### Step 3 — Add wheel metadata reader

Implement wheel archive reader that can parse metadata and list entries.

At this stage, do not compare anything. Just return structured wheel metadata and native candidate paths.

### Step 4 — Add native entry extraction and ELF scanning

Extract native entries into a temp directory and call the existing ELF scanner.

Do not duplicate ELF parsing.

### Step 5 — Add `scan ./pkg.whl`

Produce terminal output and JSON for wheel scan.

Add tests.

### Step 6 — Add `compare ./pkg.whl`

For every native entry:

- scan ELF facts;
- compare against target profile;
- collect existing diagnostics;
- aggregate result.

Add tests.

### Step 7 — Wire fail-on behavior

Use existing diagnostic summary and exit-code behavior.

Do not invent a separate wheel exit mechanism.

### Step 8 — Extend HTML report

Render wheel metadata and native entry table.

Keep escaping tests.

### Step 9 — Update docs

Update README with:

- wheel scan example;
- wheel compare example;
- pure Python wheel behavior;
- native wheel behavior;
- JSON/HTML examples.

Add release note file:

```text
v1.1.md
```

### Step 10 — Final verification

Run all checks.

---

## 14. Acceptance criteria

Version 1.1 is complete when all criteria below are met.

### 14.1 Functional criteria

The following must work:

```bash
uv run compatlab scan ./dist/demo-1.0.0-py3-none-any.whl
```

Expected result:

- command succeeds;
- package metadata is shown;
- native entries count is zero;
- diagnostic summary includes info-level no-native-code message or equivalent.

```bash
uv run compatlab scan ./dist/demo-1.0.0-cp311-cp311-linux_x86_64.whl
```

Expected result:

- command succeeds;
- native ELF entries are found;
- each native entry is scanned;
- terminal output is readable.

```bash
uv run compatlab compare ./dist/demo-1.0.0-cp311-cp311-linux_x86_64.whl --target ubuntu-2204
```

Expected result:

- all native ELF entries are compared against the selected target profile;
- compatible wheel exits with success;
- incompatible wheel exits according to `--fail-on` rules.

```bash
uv run compatlab compare ./dist/demo-1.0.0-cp311-cp311-linux_x86_64.whl \
  --target ubuntu-2204 \
  --fail-on warning \
  --json report.json \
  --html report.html
```

Expected result:

- JSON report is created;
- HTML report is created;
- diagnostics are included;
- exit code follows `--fail-on warning`.

### 14.2 Regression criteria

Existing ELF and bundle workflows must still work:

```bash
uv run compatlab scan /bin/bash
uv run compatlab compare /bin/bash --target ubuntu-2204
uv run compatlab scan ./dist/my-app --bundle-root ./dist --recursive
uv run compatlab compare ./dist/my-app --target-file ./local.yaml --bundle-root ./dist --recursive
```

Use actual test fixtures if `/bin/bash` or `ubuntu-2204` are not available in the test environment.

### 14.3 Quality criteria

Run:

```bash
uv run python -m compileall -q compatlab
uv run pytest -q
uv run ruff check compatlab
uv run ruff format --check compatlab
make check
```

Expected result:

- all tests pass;
- no lint failures;
- no formatting failures;
- no obvious regressions in CLI output.

---

## 15. Recommended release note for v1.1

Create `v1.1.md` using this structure:

```markdown
# CompatLab ArtifactDoctor 1.1

Release date: YYYY-MM-DD

## Summary

CompatLab ArtifactDoctor 1.1 adds Python wheel scanning and compatibility comparison.

The release allows `scan` and `compare` to accept `.whl` files, inspect package metadata, discover native ELF entries inside the wheel archive, and reuse the existing ELF diagnostics/reporting pipeline for every native extension.

## Added

- Wheel artifact detection.
- Wheel metadata parsing.
- Native ELF entry discovery inside wheel archives.
- Safe extraction of native entries for static scanning.
- `scan ./package.whl` support.
- `compare ./package.whl --target ...` support.
- Wheel metadata in JSON reports.
- Native entry details in JSON reports.
- Wheel metadata and native entry sections in HTML reports.
- Wheel-specific diagnostic codes.
- CLI, unit, JSON, and HTML tests for wheel workflows.

## Changed

- `scan` and `compare` now dispatch input artifacts by kind while preserving existing ELF behavior.
- Diagnostic summary and `--fail-on` behavior now apply to wheel-level reports.

## Not Included Yet

- RPM scanning.
- DEB scanning.
- SBOM generation.
- Vulnerability scanning.
- Automatic `auditwheel repair`.
- Automatic `patchelf` fixes.
- Wheel installation or import execution.
- Running artifacts inside containers.
- Public plugin system.
- Breaking JSON schema changes.
- Breaking CLI changes.

## Verification

```bash
uv run python -m compileall -q compatlab
uv run pytest -q
uv run ruff check compatlab
uv run ruff format --check compatlab
make check
```
```

---

## 16. Final instruction to Codex

Build the feature. Do not stop at preparing interfaces.

A useful partial result is better than a perfectly abstract skeleton. The release must end with working wheel scan and wheel compare commands, tests, and documentation.

If you must choose between two designs, choose the one that:

1. reuses existing ELF scanner/comparator/diagnostics/reporting;
2. preserves current CLI behavior;
3. requires fewer new dependencies;
4. is easier for a human maintainer to read;
5. can be completed in this release.

Do not implement RPM/DEB in this release. Wheel is enough.
