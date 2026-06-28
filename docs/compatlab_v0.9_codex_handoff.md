# CompatLab ArtifactDoctor 0.9 — Codex Handoff

## Purpose

This document is the implementation handoff for Codex for the next development
iteration of **CompatLab ArtifactDoctor 0.9**.

The recommended theme for v0.9 is:

> **Static self-contained HTML reports for scan and compare results.**

CompatLab already has actionable diagnostics, CI gates, JSON reports, bundle-aware
dependency graphs, and target profile comparison. The next valuable step is to
turn the existing machine-oriented report model into a readable, shareable HTML
artifact for humans.

Do **not** expand v0.9 into wheel/RPM/DEB package scanning. Do **not** add a web
server, database, daemon, JavaScript application, or vulnerability/SBOM scope.
This release should be a focused reporting layer on top of the existing report
models.

---

## Project Context

CompatLab ArtifactDoctor is a Python-first CLI tool for preflight compatibility
checks of Linux binary artifacts.

The product goal is to explain whether a Linux ELF binary or shipped application
bundle is likely to run on a selected target Linux profile before it is shipped.

The project currently supports:

- ELF scanning through host-side `readelf`;
- compatibility comparison against built-in or generated target profiles;
- generated target profiles from:
  - the current Linux system;
  - Docker image rootfs export;
  - Docker image rootfs export after installing predefined runtime presets;
- bundle-aware local dependency resolution;
- recursive `DT_NEEDED` traversal;
- `$ORIGIN`, `RUNPATH`, and `RPATH`-based local dependency lookup;
- normalized diagnostics with stable issue codes;
- JSON reports;
- CI quality gates through `--fail-on`.

The user is learning through incremental releases. Keep implementation steps
small, testable, and easy to inspect.

---

## Recent Release History

### v0.4

Added automatic target profile generation from the current Linux system.

Important capabilities:

- raw system facts;
- `/etc/os-release` parsing;
- architecture detection;
- glibc detection;
- `ldconfig -p` parsing;
- system library symbol version detection;
- `profiles detect`;
- `profiles generate --from-current`;
- `profiles validate`;
- `compare --target-file`.

### v0.5

Added Docker image target profile generation.

Important capabilities:

- Docker rootfs export through host Docker CLI;
- rootfs tar parsing;
- Docker image facts;
- dynamic linker detection from image rootfs;
- host-side `readelf` over extracted libraries;
- `profiles generate --from-image`;
- `profiles detect --from-image`;
- `--pull`;
- `--platform`.

### v0.6

Added Docker runtime profile presets.

Important capabilities:

- runtime preset registry;
- `cpp-runtime`;
- `python-runtime`;
- package manager detection for `apt-get`, `dnf`, `yum`;
- temporary container install/export/cleanup flow;
- runtime-aware profile generation;
- runtime metadata in generated profiles.

### v0.7

Added bundle-aware dependency resolution.

Important capabilities:

- `--bundle-root`;
- `--recursive`;
- `--max-depth`;
- `--max-files`;
- local dependency graph;
- dependency resolution states:
  - `bundled`;
  - `target`;
  - `missing`;
  - `ambiguous`;
- `$ORIGIN`, `RUNPATH`, and `RPATH` handling;
- dependency graph in JSON;
- bundled ELF comparison against target profile.

### v0.8

Added actionable diagnostics and CI gates.

Important capabilities:

- `DiagnosticIssue`;
- `DiagnosticSummary`;
- `DiagnosticSeverity`;
- `DiagnosticCategory`;
- stable diagnostic codes;
- JSON fields:
  - `summary`;
  - `diagnostics`;
- `--fail-on error`;
- `--fail-on warning`;
- `--fail-on never`;
- Rich diagnostics output;
- dependency-chain attribution for bundle diagnostics.

v0.8 explicitly left HTML reports out of scope and named HTML reports as a
possible next development step after the diagnostic JSON schema becomes stable.

---

## v0.9 Release Goal

Add optional static HTML report generation for `scan` and `compare`.

The HTML report must be:

- generated from existing in-memory report data;
- optionally generated alongside JSON;
- self-contained;
- deterministic enough for tests;
- readable without a server;
- safe by default through HTML escaping;
- dependency-light.

Recommended implementation approach:

- avoid adding Jinja2 unless the project already has it;
- use Python standard library rendering helpers;
- keep CSS embedded in the generated document;
- do not add external fonts, external scripts, CDN links, or runtime network
  dependencies.

---

## User-Facing CLI Contract

Add `--html PATH` to both `scan` and `compare`.

### Scan HTML report

```bash
uv run compatlab scan ./dist/my-app \
  --bundle-root ./dist \
  --recursive \
  --html report.html
```

### Compare HTML report

```bash
uv run compatlab compare ./dist/my-app \
  --target-file /tmp/ubuntu-2204-cpp-runtime.yaml \
  --bundle-root ./dist \
  --recursive \
  --fail-on error \
  --html report.html
```

### JSON and HTML together

```bash
uv run compatlab compare ./dist/my-app \
  --target ubuntu-2204 \
  --bundle-root ./dist \
  --recursive \
  --json report.json \
  --html report.html
```

Expected behavior:

- JSON output must keep working exactly as before.
- `--html` must not change compatibility logic.
- `--html` must not change diagnostic generation.
- `--html` must not change `--fail-on` behavior.
- If report generation fails because the output path is invalid or unwritable,
  the command should fail with a clear CLI error.
- If diagnostics fail the gate, the command should still write the HTML report
  before exiting with the configured non-zero exit code, if the current
  architecture allows this cleanly.

---

## Optional CLI Contract

If easy and clean, add a dedicated report conversion command:

```bash
uv run compatlab reports html report.json --output report.html
```

This is optional. Do it only if it fits the existing CLI structure without
turning v0.9 into a larger refactor.

If implemented, this command should:

- read an existing CompatLab JSON report;
- render it to HTML;
- validate enough structure to fail clearly on unsupported JSON;
- not require rescanning the artifact.

Do **not** delay core `scan --html` and `compare --html` for this optional
command.

---

## HTML Report Content

The report should include these sections.

### 1. Header

Show:

- product name: `CompatLab ArtifactDoctor`;
- report type:
  - `scan`;
  - `compare`;
- generated timestamp;
- artifact path;
- command mode if available;
- target profile name or target file path for compare reports;
- bundle root if present;
- recursive mode if enabled.

### 2. Summary

Show diagnostic summary:

- status;
- errors;
- warnings;
- info;
- total diagnostics;
- issue-code counters.

Suggested visual style:

- `passed`;
- `warning`;
- `failed`.

No JavaScript is required.

### 3. Diagnostics

Show a table with:

- severity;
- code;
- category;
- title;
- affected path;
- dependency name;
- message;
- hint.

Rules:

- include stable diagnostic codes;
- preserve useful text from v0.8 models;
- escape all user-controlled strings;
- keep missing fields readable as `-`.

### 4. Dependency Resolution

If `dependency_graph` exists, show:

- dependency name;
- requester path;
- resolution state;
- resolved path;
- candidates count;
- dependency chain or parent relationship when available.

Useful states:

- `bundled`;
- `target`;
- `missing`;
- `ambiguous`.

This section is especially important for v0.7/v0.8 bundle workflows.

### 5. Compatibility Problems and Warnings

The v0.8 release preserves older `problems` and `warnings` fields. Keep them
visible for backward-compatible reports.

Show:

- existing compatibility problems;
- existing warnings;
- keep this section after normalized diagnostics so the new model remains the
  primary view.

### 6. Raw Metadata / Technical Details

Show compact technical details:

- architecture facts;
- required symbol versions;
- provided target symbol versions;
- dynamic linker/interpreter if available;
- generated profile metadata if included in report;
- report schema version if present.

Keep this section simple. Do not try to expose every object field if that makes
the page unreadable.

---

## HTML Safety Requirements

Every string that can come from:

- artifact paths;
- target profile fields;
- Docker image metadata;
- dependency names;
- diagnostic messages;
- CLI arguments;
- JSON report content;

must be escaped before being inserted into HTML.

Use `html.escape()` or equivalent.

Do not use `mark_safe` style bypasses.

Do not include external scripts.

Do not include external CSS.

Do not include external images.

Do not include user-controlled raw HTML.

---

## Suggested Internal Design

Add a new module, for example:

```text
compatlab/src/reports/
  __init__.py
  html.py
```

or, if the project does not use `src` inside package paths, follow the existing
layout style.

Suggested public function:

```python
def render_html_report(report: object, *, report_type: str) -> str:
    ...
```

Suggested file writer:

```python
def write_html_report(report: object, output_path: Path, *, report_type: str) -> None:
    ...
```

Potential helpers:

```python
def html_escape(value: object) -> str:
    ...

def render_summary(summary: DiagnosticSummary | None) -> str:
    ...

def render_diagnostics(diagnostics: Sequence[DiagnosticIssue]) -> str:
    ...

def render_dependency_graph(graph: DependencyGraph | None) -> str:
    ...

def render_legacy_problems(report: object) -> str:
    ...
```

Keep helpers small and unit-testable.

---

## Report Schema Stability

Do not redesign v0.8 diagnostic models.

Do not rename existing JSON keys.

Do not remove:

- `summary`;
- `diagnostics`;
- `dependency_graph`;
- `problems`;
- `warnings`.

v0.9 should consume these fields, not replace them.

---

## Tests Required

Add unit tests for the HTML renderer:

- report with empty diagnostics;
- report with error/warning/info diagnostics;
- report with dependency graph;
- report with missing dependencies;
- report with ambiguous dependencies;
- report with legacy problems/warnings;
- HTML escaping for suspicious values like:
  - `<script>alert(1)</script>`;
  - paths containing `&`;
  - quotes in diagnostic messages.

Add CLI tests:

- `scan --html report.html` writes a file;
- `compare --html report.html` writes a file;
- `--json` and `--html` work together;
- `--fail-on never --html` writes report and exits successfully for diagnostic
  issues;
- `--fail-on error --html` writes report and exits according to diagnostics;
- invalid HTML output path fails clearly.

If snapshot tests are not already used, do not introduce a heavy snapshot test
framework. Use focused substring checks.

Recommended assertions:

- file exists;
- contains `CompatLab ArtifactDoctor`;
- contains `Diagnostics`;
- contains a known diagnostic code;
- contains dependency graph section when graph is present;
- does not contain unescaped `<script>`.

---

## Documentation Updates

Update `README.md` with a new section:

```markdown
## HTML Reports
```

Include examples:

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

Mention:

- HTML reports are static files;
- no server is required;
- JSON remains the stable machine-readable format;
- HTML is intended for human review in CI artifacts, release checks, and bug
  reports.

Add `docs/ReleaseNotes/v0.9.md`.

---

## Release Notes Draft

Create:

```text
docs/ReleaseNotes/v0.9.md
```

Suggested structure:

```markdown
# CompatLab ArtifactDoctor 0.9

Release date: 2026-06-28

## Summary

CompatLab ArtifactDoctor 0.9 adds static HTML reports for scan and compare
results.

The CLI can now write a self-contained HTML report with diagnostic summary,
stable issue codes, dependency resolution details, and compatibility findings.
The report is intended for human review in CI artifacts and release checks,
while JSON remains the stable machine-readable format.

## Added

- `--html PATH` for `scan`.
- `--html PATH` for `compare`.
- Static self-contained HTML report renderer.
- Summary section based on v0.8 diagnostic summaries.
- Diagnostics table with stable issue codes.
- Dependency resolution section from `dependency_graph`.
- Compatibility problems and warnings section.
- HTML escaping for user-controlled report values.
- Unit and CLI tests for HTML report generation.

## Changed

- `scan` and `compare` can now produce terminal output, JSON output, and HTML
  output in the same run.
- Existing JSON report behavior remains unchanged.

## Current Behavior

[add commands]

## Not Included Yet

- Interactive HTML reports.
- External JavaScript or CSS assets.
- Web interface, database, daemon, or server mode.
- Wheel scanning.
- RPM scanning.
- DEB scanning.
- SBOM generation.
- Vulnerability scanning.
- Automatic patching through `patchelf`.
- Artifact execution inside containers.
- Full dynamic linker emulation.

## Verification

[add final commands and expected test count]

## Next Step

The next development step is to consider package artifact scanning, starting
with Python wheel inspection, or to refine report ergonomics after using HTML
reports in CI.
```

Update expected test count only after running the final test suite.

---

## Development Workflow for Codex

Codex should work in small, reviewable steps.

Recommended sequence:

1. Inspect the current project tree.
2. Find CLI implementations for `scan` and `compare`.
3. Find JSON report model creation.
4. Find diagnostic models and summary calculation from v0.8.
5. Add an HTML report module with pure rendering functions.
6. Add unit tests for renderer functions.
7. Add `--html` CLI option for `scan`.
8. Add `--html` CLI option for `compare`.
9. Add CLI tests.
10. Update README.
11. Add `docs/ReleaseNotes/v0.9.md`.
12. Run formatting, linting, and tests.

Use commands such as:

```bash
find compatlab -maxdepth 4 -type f | sort
find tests -maxdepth 4 -type f | sort
grep -R "fail-on\|DiagnosticIssue\|DiagnosticSummary\|dependency_graph\|json" -n compatlab tests
```

Expected validation commands:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
make check
```

If `make check` already runs the previous commands, still mention its result in
the final handoff.

---

## Implementation Constraints

- Keep the project Python-first.
- Keep the CLI Typer-based if that is the current structure.
- Keep report models Pydantic-based if that is the current structure.
- Do not introduce a web framework.
- Do not introduce frontend build tooling.
- Do not add npm, node, vite, react, or similar.
- Do not add a database.
- Do not run artifacts.
- Do not mutate Docker images.
- Do not add arbitrary package installation.
- Do not perform vulnerability scanning.
- Do not add SBOM generation.
- Do not perform network calls in tests.
- Keep tests deterministic.
- Preserve existing CLI behavior when `--html` is not provided.
- Preserve existing JSON behavior.
- Preserve exit-code behavior from v0.8.

---

## Acceptance Criteria

v0.9 is complete when:

- `scan --html PATH` writes an HTML report.
- `compare --html PATH` writes an HTML report.
- `--json` and `--html` can be used together.
- HTML reports include summary, diagnostics, dependency resolution when present,
  and compatibility findings.
- User-controlled values are escaped.
- CLI exit behavior still follows `--fail-on`.
- Existing tests pass.
- New renderer and CLI tests pass.
- README documents HTML reports.
- `docs/ReleaseNotes/v0.9.md` exists.
- Final checks pass:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
make check
```

---

## What Not To Do in v0.9

Do not implement:

- wheel scanning;
- RPM scanning;
- DEB scanning;
- SBOM;
- vulnerability scanning;
- web UI;
- server mode;
- database;
- interactive report UI;
- JavaScript report app;
- external report assets;
- automatic `patchelf`;
- artifact execution inside containers;
- Docker image mutation;
- full dynamic linker emulation.

These are future release candidates, not v0.9 scope.

---

## Suggested Commit Message

```text
feat(reports): add static HTML reports for scan and compare
```

---

## Final Response Expected From Codex

When implementation is complete, Codex should report:

- files changed;
- new CLI behavior;
- tests added;
- verification commands and results;
- any intentional limitations;
- exact expected test count.
