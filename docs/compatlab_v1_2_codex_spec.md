# CompatLab ArtifactDoctor 1.2 — Codex Development Specification

## 0. Purpose of this document

This document is a handoff specification for the Codex agent.

The project is **CompatLab ArtifactDoctor**, a Python-first CLI tool for preflight compatibility checks of Linux binary artifacts. The current version is **1.1**. The goal of the next development cycle is **version 1.2**.

Codex must use this document as the main development brief, but must still inspect the repository before editing. If repository structure differs from names used here, adapt to the real codebase instead of forcing the exact paths from this document.

The expected result is not a sketch, not preparatory scaffolding, and not a TODO-only refactor. The expected result is a working implementation with tests, documentation updates, and release notes.

---

## 1. Current project state

### 1.1 What CompatLab already does

CompatLab ArtifactDoctor currently supports:

- scanning local ELF binaries and shared libraries;
- comparing ELF artifacts against target Linux profiles;
- recursive bundle dependency resolution through `--bundle-root` and `--recursive`;
- normalized diagnostics with stable issue codes;
- configurable CI gates through `--fail-on error|warning|never`;
- JSON reports for machine consumption;
- static HTML reports for human review;
- target profile generation from the current host;
- target profile generation from Docker image rootfs exports;
- runtime profile presets for Docker images;
- Python wheel scanning and compatibility comparison, introduced in version 1.1.

### 1.2 What version 1.1 added

Version 1.1 added Python wheel support:

- artifact kind detection for wheels;
- wheel metadata parsing;
- native ELF entry discovery inside `.whl` archives;
- safe extraction of native entries;
- `compatlab scan ./package.whl`;
- `compatlab compare ./package.whl --target ...`;
- wheel metadata in JSON reports;
- native entry details in JSON reports;
- wheel metadata and native entry sections in HTML reports;
- wheel-specific diagnostic codes;
- CLI, unit, JSON, and HTML tests for wheel workflows.

Version 1.1 also changed `scan` and `compare` so they dispatch input artifacts by kind while preserving existing ELF behavior.

### 1.3 Important constraints preserved from previous releases

Keep these stable unless there is a strong reason and tests/docs are updated accordingly:

- Existing ELF CLI behavior must remain compatible.
- Existing wheel CLI behavior from 1.1 must remain compatible.
- JSON reports must remain backward-compatible where possible.
- HTML reports must remain static and self-contained.
- Diagnostics must remain stable and machine-readable.
- `--fail-on` behavior must remain consistent across artifact kinds.
- Do not introduce a web server, database, daemon, public plugin framework, vulnerability scanner, or automatic patching system in this release.

---

## 2. Version 1.2 product goal

## Add first-class RPM package scanning and compatibility comparison

Version 1.2 must allow CompatLab to accept `.rpm` files in the same high-level workflows that already support ELF and wheel artifacts:

```bash
compatlab scan ./dist/example-1.0.0-1.x86_64.rpm
compatlab compare ./dist/example-1.0.0-1.x86_64.rpm --target ubuntu-2204
compatlab compare ./dist/example-1.0.0-1.x86_64.rpm --target-file ./profiles/prod.yaml
compatlab compare ./dist/example-1.0.0-1.x86_64.rpm --target-file ./profiles/prod.yaml --json report.json --html report.html
```

The RPM scanner must inspect package metadata, discover native ELF files inside the RPM payload, safely extract those native files, reuse the existing ELF scanning/comparison pipeline, and aggregate the result into the existing terminal, JSON, HTML, diagnostics, and CI gate flows.

The high-level user value:

> “Before shipping an RPM package, CompatLab can tell whether native binaries and shared libraries inside that package are likely to run on the target Linux profile.”

This is especially useful for enterprise Linux delivery workflows, SberLinux/RHEL-like packaging, OpenStack component packaging, and CI release checks.

---

## 3. Development stance for Codex

Move fast, but do not be reckless.

Use roughly this balance:

- **70–80% implementation speed**: prefer a working vertical slice over excessive abstractions.
- **20–30% caution**: preserve public behavior, keep tests green, avoid unsafe archive extraction, and avoid breaking report schemas.

Practical guidance:

- Do not spend the whole iteration designing a perfect universal package framework.
- Do not block RPM support on DEB support.
- Do not implement a public plugin system.
- Do not rewrite the project architecture just because RPM support needs adapters.
- It is acceptable to add a small, focused dependency for RPM reading if that is the fastest robust path.
- It is acceptable to refactor internal service/report code where needed, as long as CLI behavior and tests remain stable.
- Prefer small adapters and direct reuse of existing ELF/wheel patterns.

---

## 4. Recommended implementation approach

### 4.1 Artifact dispatch

Extend existing artifact kind detection introduced for wheel support.

Add RPM as a first-class artifact kind:

```text
ELF
WHEEL
RPM
UNKNOWN
```

Expected behavior:

- `.rpm` files should be detected as RPM artifacts.
- Detection should not rely only on extension if there is already a safer detection mechanism.
- If the repository has `--artifact-kind auto|elf|wheel`, extend it to include `rpm`.
- If no explicit artifact-kind option exists, preserve the current model and add RPM to auto-dispatch.

Expected CLI examples:

```bash
compatlab scan ./package.rpm
compatlab compare ./package.rpm --target ubuntu-2204
compatlab compare ./package.rpm --target-file ./target.yaml --json report.json --html report.html
```

### 4.2 RPM reader strategy

Do not hand-write a full RPM parser unless the project already has one.

Preferred path:

1. Inspect current dependency policy in `pyproject.toml`.
2. If acceptable, add a focused RPM reader dependency such as `rpmfile`.
3. Wrap the dependency behind CompatLab’s own adapter module so the rest of the codebase does not depend on third-party API details.

Suggested internal module names, adapt to the actual repository:

```text
compatlab/artifacts/rpm.py
compatlab/scanners/rpm.py
compatlab/package/rpm.py
compatlab/services/artifacts.py
```

The exact names are less important than the separation of responsibilities:

- artifact kind detection;
- RPM metadata reading;
- safe payload entry discovery;
- safe extraction of native ELF payload entries;
- scan/compare orchestration;
- report rendering.

### 4.3 RPM metadata to collect

Collect at least:

- package name;
- epoch, if present;
- version;
- release;
- architecture;
- summary, if available;
- license, if available;
- payload file count;
- native ELF entry count.

Nice to have if easy through the RPM reader:

- vendor;
- group;
- build time;
- source RPM;
- provides;
- requires.

Do not make `requires/provides` mandatory for the first working version. Native ELF compatibility is the main product value for 1.2.

### 4.4 Native ELF discovery inside RPM payload

The RPM scanner must inspect payload entries and find native ELF candidates.

Candidate rules:

- regular files under common binary/library paths are candidates:
  - `/usr/bin/*`;
  - `/usr/sbin/*`;
  - `/bin/*`;
  - `/sbin/*`;
  - `/usr/lib/*`;
  - `/usr/lib64/*`;
  - `/lib/*`;
  - `/lib64/*`;
  - `/opt/**`;
- files ending with `.so` or containing `.so.` are candidates;
- files with no extension may still be candidates if their first bytes are ELF magic;
- Python native extensions inside RPM payload should also be discovered:
  - `*.cpython-*.so`;
  - `*.abi3.so`;
  - package-local `.so` files.

Important: do not rely only on filename. A real ELF magic check is needed before running the ELF scanner.

### 4.5 Safe extraction

RPM payload extraction must be safe.

Required safety rules:

- reject or ignore entries with unsafe paths;
- no path traversal through `../`;
- no absolute-path writes into the real filesystem;
- no extraction outside a temporary directory;
- no symlink traversal that escapes the temporary root;
- enforce configurable or internal limits:
  - maximum RPM file size;
  - maximum payload file count;
  - maximum extracted bytes;
  - maximum native entry count if needed.

Suggested CLI options if the project already has similar limits for wheel/bundle:

```bash
--max-rpm-files 5000
--max-rpm-size 500M
--max-rpm-extracted-size 1G
```

If the existing style uses different option naming, follow the project style.

### 4.6 Reuse existing ELF scanner and compare pipeline

Do not create a separate RPM compatibility engine.

The expected pipeline:

```text
RPM file
  -> detect artifact kind: rpm
  -> read RPM metadata
  -> inspect payload entries
  -> safely extract native ELF entries into temp root
  -> run existing ELF scanner for each native entry
  -> compare every native ELF entry against target profile when compare is used
  -> aggregate diagnostics and summary
  -> render terminal/JSON/HTML reports
  -> apply --fail-on consistently
```

If existing wheel implementation already has a multi-entry artifact scan model, reuse it.

If existing wheel implementation duplicated too much logic, this is a good moment to introduce a small internal shared helper for archive-like artifacts. Keep it practical, not theoretical.

### 4.7 RPM payload as bundle root

Preferred behavior for 1.2:

When comparing an RPM, CompatLab should treat extracted RPM payload as a local bundle root where practical. This lets bundled shared libraries inside the RPM satisfy `DT_NEEDED` dependencies for other files in the same RPM.

Example:

```text
/usr/bin/myapp
/usr/lib64/libprivate.so.1
```

If `/usr/bin/myapp` needs `libprivate.so.1`, CompatLab should be able to resolve it from the extracted RPM payload instead of incorrectly reporting it as missing from the target.

Implementation hint:

- extract native entries and enough local library files to a temporary payload root;
- reuse the existing bundle resolver against that temp root;
- preserve original RPM payload paths in user-facing reports.

If full payload-root resolution becomes too large for this release, implement at least direct per-entry ELF comparison and clearly document that full intra-RPM dependency resolution is partial. But the preferred target is to reuse bundle resolution.

---

## 5. Required CLI behavior

### 5.1 Scan RPM

Command:

```bash
compatlab scan ./dist/example-1.0.0-1.x86_64.rpm
```

Expected output:

- identify artifact kind as `rpm`;
- show package metadata;
- show number of payload files inspected;
- show number of native ELF entries found;
- show per-entry scan status;
- show diagnostics summary.

Pure metadata-only RPMs or no-native RPMs should not be treated as compatibility failures by default.

If there are no native ELF files:

- produce an info diagnostic such as `CL_RPM_NO_ELF_ENTRIES`;
- summary should not be failed unless the project’s existing diagnostic policy says otherwise.

### 5.2 Compare RPM

Command:

```bash
compatlab compare ./dist/example-1.0.0-1.x86_64.rpm --target ubuntu-2204
```

Expected output:

- identify artifact kind as `rpm`;
- load the target profile;
- compare every discovered native ELF entry against the target profile;
- report compatibility problems by original RPM payload path;
- aggregate diagnostics across entries;
- fail according to `--fail-on`.

If one ELF entry is incompatible, the whole RPM report should be considered failed.

### 5.3 JSON and HTML output

Commands:

```bash
compatlab scan ./dist/example.rpm --json scan.json --html scan.html
compatlab compare ./dist/example.rpm --target-file ./target.yaml --json compare.json --html compare.html
```

Expected behavior:

- JSON and HTML are written before exiting because of `--fail-on`, matching existing behavior from previous releases.
- JSON remains stable and parseable.
- HTML remains static, self-contained, escaped, and suitable for CI artifacts.

---

## 6. Report model requirements

### 6.1 JSON report extension

Extend existing report models without breaking existing ELF/wheel fields.

Suggested shape:

```json
{
  "artifact": {
    "kind": "rpm",
    "path": "./dist/example-1.0.0-1.x86_64.rpm"
  },
  "package": {
    "type": "rpm",
    "name": "example",
    "epoch": null,
    "version": "1.0.0",
    "release": "1",
    "architecture": "x86_64",
    "summary": "Example package",
    "license": "MIT"
  },
  "entries": [
    {
      "path": "/usr/bin/example",
      "kind": "elf",
      "scan": {},
      "diagnostics": []
    },
    {
      "path": "/usr/lib64/libexample.so.1",
      "kind": "elf",
      "scan": {},
      "diagnostics": []
    }
  ],
  "summary": {},
  "diagnostics": []
}
```

Adapt this to the actual existing 1.1 report model. Do not introduce a totally separate JSON format for RPM.

### 6.2 Terminal report

Terminal output should be concise but useful.

Include:

```text
RPM: example-1.0.0-1.x86_64.rpm
Package: example 1.0.0-1 x86_64
Native ELF entries: 2

✓ /usr/bin/example
✗ /usr/lib64/libexample.so.1
  CL_SYMBOL_GLIBC_TOO_NEW: requires GLIBC_2.34, target has GLIBC_2.28

Summary: failed, errors=1, warnings=0, infos=0
```

Follow existing Rich/terminal style in the repository.

### 6.3 HTML report

Extend the existing static HTML report with RPM sections:

- RPM metadata;
- payload summary;
- native ELF entries;
- per-entry diagnostics;
- package-level diagnostics;
- existing compatibility problems/warnings where applicable;
- dependency graph if bundle resolution is reused.

Escape all user/package/path text before rendering.

---

## 7. New diagnostics

Add RPM-specific diagnostics where useful.

Recommended codes:

```text
CL_RPM_INVALID_ARCHIVE
CL_RPM_METADATA_MISSING
CL_RPM_PAYLOAD_UNSUPPORTED
CL_RPM_PAYLOAD_READ_FAILED
CL_RPM_UNSAFE_PATH
CL_RPM_TOO_LARGE
CL_RPM_TOO_MANY_FILES
CL_RPM_EXTRACTED_TOO_LARGE
CL_RPM_NO_ELF_ENTRIES
CL_RPM_ARCH_MISMATCH
CL_RPM_ELF_ENTRY_SCAN_FAILED
```

Severity suggestions:

- `CL_RPM_INVALID_ARCHIVE`: error
- `CL_RPM_METADATA_MISSING`: error or warning depending on recoverability
- `CL_RPM_PAYLOAD_UNSUPPORTED`: error
- `CL_RPM_PAYLOAD_READ_FAILED`: error
- `CL_RPM_UNSAFE_PATH`: error or warning depending on whether the entry was skipped safely
- `CL_RPM_TOO_LARGE`: error
- `CL_RPM_TOO_MANY_FILES`: error
- `CL_RPM_EXTRACTED_TOO_LARGE`: error
- `CL_RPM_NO_ELF_ENTRIES`: info
- `CL_RPM_ARCH_MISMATCH`: warning or error; choose based on current architecture diagnostic policy
- `CL_RPM_ELF_ENTRY_SCAN_FAILED`: error

Existing ELF diagnostics such as missing libraries, too-new symbols, architecture mismatch, interpreter issues, and RPATH/RUNPATH issues should still be reused for native files inside RPMs.

---

## 8. Architecture guidance

### 8.1 Avoid duplication with wheel support

After 1.1, wheel support probably introduced concepts like:

- archive metadata;
- native entries;
- safe extraction;
- multi-entry scanning;
- package-level report sections.

RPM support should reuse those ideas. If the wheel implementation has duplicated logic that can be shared cleanly, introduce a small internal helper such as:

```text
ArchiveNativeEntry
ExtractedNativeEntry
ArchiveScanContext
MultiEntryScanResult
```

But keep the refactor limited. Do not derail 1.2 into a giant framework extraction.

### 8.2 Suggested internal layout

Adapt to real project structure.

Possible modules:

```text
compatlab/artifacts/detect.py
compatlab/artifacts/rpm.py
compatlab/scanners/rpm.py
compatlab/reports/html.py
compatlab/services/artifacts.py
compatlab/models.py
```

Responsibilities:

- `artifacts/detect.py`: detect `rpm` kind.
- `artifacts/rpm.py` or `scanners/rpm.py`: RPM reader, metadata, payload/native discovery.
- `services/artifacts.py`: dispatch `scan` and `compare` workflows.
- `models.py`: RPM metadata and entry models if the project centralizes Pydantic models there.
- `reports/html.py`: RPM HTML context and rendering sections.

### 8.3 Dependency handling

If adding `rpmfile` or a similar dependency:

- add it to project dependencies in the correct file;
- update lock file if the project uses one;
- keep it isolated behind an internal adapter;
- avoid leaking third-party objects into public report models;
- add useful error messages if RPM parsing fails.

Do not require system `rpm`, `rpm2cpio`, or `cpio` commands unless there is no viable Python path. CompatLab should remain easy to run in Python-first CI environments.

---

## 9. Tests required for 1.2

### 9.1 Unit tests

Add tests for:

- RPM artifact detection;
- metadata parsing;
- invalid RPM handling;
- unsupported payload handling;
- unsafe payload paths;
- payload file count limits;
- extracted-size limits;
- native ELF candidate discovery;
- no-native RPM behavior;
- package architecture mismatch behavior, if implemented.

### 9.2 CLI tests

Add tests for:

```bash
compatlab scan ./package.rpm
compatlab scan ./package.rpm --json report.json
compatlab scan ./package.rpm --html report.html
compatlab compare ./package.rpm --target ubuntu-2204
compatlab compare ./package.rpm --target-file ./target.yaml --json report.json --html report.html
compatlab compare ./package.rpm --target-file ./target.yaml --fail-on warning
```

### 9.3 Report tests

Add tests for:

- JSON includes `artifact.kind = rpm` or equivalent existing model field;
- JSON includes RPM package metadata;
- JSON includes native entries using original RPM payload paths;
- diagnostics are aggregated correctly;
- HTML escapes package metadata and payload paths;
- HTML includes RPM metadata and native entry sections;
- HTML is still written before non-zero exit when `--fail-on` fails.

### 9.4 Fixture strategy

Prefer deterministic fixtures.

Options:

1. If the repository already has binary fixture patterns, add a tiny RPM fixture there.
2. If adding a real RPM fixture is acceptable, keep it tiny and harmless.
3. If the repository avoids binary fixtures, create test doubles for the RPM adapter and keep one integration test guarded behind existing test utilities.

Do not make the normal test suite depend on host `rpmbuild` being installed unless the project already has this convention.

The preferred result is a normal `uv run pytest -q` that passes on a clean developer machine without requiring RPM build tools.

---

## 10. Documentation updates

Update README with a new section:

```markdown
## RPM Package Scanning
```

Include examples:

```bash
uv run compatlab scan ./dist/example-1.0.0-1.x86_64.rpm
uv run compatlab compare ./dist/example-1.0.0-1.x86_64.rpm --target ubuntu-2204
uv run compatlab compare ./dist/example-1.0.0-1.x86_64.rpm --target-file ./profiles/prod.yaml --json report.json --html report.html
```

Explain briefly:

- CompatLab reads RPM metadata;
- discovers native ELF files in the payload;
- reuses ELF compatibility checks;
- reports package-level and file-level diagnostics;
- does not install the RPM;
- does not execute package scripts;
- does not run binaries inside containers;
- does not do vulnerability scanning.

Add or update release notes:

```text
# CompatLab ArtifactDoctor 1.2

Summary: adds RPM package scanning and compatibility comparison.
```

---

## 11. Not in scope for 1.2

Do not implement these in this release:

- DEB scanning;
- SBOM generation;
- vulnerability scanning;
- package installation into Docker;
- running RPM scripts;
- running binaries from RPM payload;
- automatic `patchelf` fixes;
- automatic package rebuilding;
- RPM signing/verification workflows;
- repository metadata parsing;
- YUM/DNF dependency solving;
- public plugin system;
- web UI, database, daemon, server mode;
- breaking CLI changes;
- breaking JSON schema changes.

If a small amount of RPM `requires/provides` metadata is easy to expose, it can be added as passive report metadata. Do not turn 1.2 into a package dependency solver.

---

## 12. Definition of Done

Version 1.2 is complete when all of the following are true:

### 12.1 User workflows work

```bash
uv run compatlab scan ./dist/example.rpm
```

- detects RPM artifact;
- displays RPM metadata;
- displays native ELF entries or no-native info diagnostic.

```bash
uv run compatlab compare ./dist/example.rpm --target ubuntu-2204
```

- compares native ELF entries against target profile;
- reports compatibility problems per RPM payload path;
- exits according to diagnostics and default `--fail-on error`.

```bash
uv run compatlab compare ./dist/example.rpm \
  --target-file ./profiles/prod.yaml \
  --fail-on warning \
  --json report.json \
  --html report.html
```

- writes JSON;
- writes HTML;
- applies `--fail-on warning` consistently.

### 12.2 Existing workflows still work

These must remain functional:

```bash
uv run compatlab scan ./app
uv run compatlab compare ./app --target ubuntu-1804
uv run compatlab scan ./dist/package.whl
uv run compatlab compare ./dist/package.whl --target ubuntu-2204
uv run compatlab profiles list
uv run compatlab profiles detect
uv run compatlab profiles validate ./profile.yaml
```

### 12.3 Verification commands pass

Run:

```bash
uv run python -m compileall -q compatlab
uv run pytest -q
uv run ruff check compatlab
uv run ruff format --check compatlab
make check
```

If the repository uses slightly different commands, use the repository’s canonical commands and update docs accordingly.

---

## 13. Suggested development order

Follow this order for fastest useful progress:

1. Inspect current 1.1 repository structure and wheel implementation.
2. Add RPM artifact kind detection.
3. Add RPM reader adapter and metadata model.
4. Add payload file listing and native ELF candidate detection.
5. Add safe extraction of native ELF entries into a temporary root.
6. Reuse existing ELF scanner for extracted RPM entries.
7. Wire `compatlab scan ./package.rpm`.
8. Wire `compatlab compare ./package.rpm --target ...`.
9. Add diagnostics and `--fail-on` aggregation.
10. Add JSON report fields for RPM.
11. Add HTML sections for RPM.
12. Add CLI/unit/report tests.
13. Update README.
14. Add release notes for 1.2.
15. Run full verification.

At every stage, prefer making a thin working vertical slice before polishing.

---

## 14. First implementation slice

The first useful PR/commit should do only this:

- detect `.rpm` as `ArtifactKind.RPM`;
- parse basic RPM metadata;
- list payload entries;
- return a simple scan result with package metadata and native entry count;
- add tests for RPM detection and metadata parsing.

After that, add ELF scanning and compare behavior.

This prevents the task from turning into a huge invisible refactor with no runnable result.

---

## 15. Final note for Codex

The main theme of 1.2 is:

> RPM is a package container. CompatLab must inspect the container, find native Linux binaries inside it, and reuse the existing ELF compatibility engine instead of inventing a second engine.

Do not overcomplicate this.

Make RPM a first-class artifact kind, keep reports consistent with ELF/wheel behavior, keep archive extraction safe, and ship a working release.
