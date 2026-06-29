# CompatLab ArtifactDoctor v0.10 — Codex Development Handoff

## 1. Purpose of this handoff

This document is a complete development handoff for the Codex agent.
It describes the next implementation step for **CompatLab ArtifactDoctor v0.10**.

The requested version is an **intermediate architecture refactoring release** before adding support for new binary/package artifact types such as:

- Python wheel files;
- RPM packages;
- DEB packages.

The main goal of v0.10 is **not** to implement wheel/RPM/DEB scanning yet.
The main goal is to prepare the codebase so those features can be added later without spreading package-specific logic across the CLI, ELF scanner, diagnostics, reports, and compatibility comparison code.

In short:

```text
v0.10 = architecture stabilization before package artifact scanning
```

---

## 2. Current project context

Project name:

```text
CompatLab ArtifactDoctor
```

Product idea:

```text
A Python-first CLI tool that checks whether Linux binary artifacts are likely to run on a selected target Linux profile before shipping.
```

Current core domain:

- ELF binary inspection;
- shared library dependency analysis;
- target Linux profile comparison;
- compatibility diagnostics;
- CI-friendly JSON reports;
- human-friendly terminal and HTML reports;
- profile generation from the current system or Docker image/rootfs/runtime preset.

Current CLI examples from the README:

```bash
compatlab scan ./app
compatlab scan ./dist/my-app --bundle-root ./dist --recursive
compatlab compare ./app --target ubuntu-1804
compatlab compare ./app --target-file ./local.yaml
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

Important project principle:

```text
JSON remains the stable machine-readable report format.
HTML and terminal output are human-readable renderers over the same analysis result.
```

---

## 3. Previous release state

### v0.7

v0.7 added bundle-aware recursive dependency resolution.

Important features:

- `--bundle-root DIR` for `scan` and `compare`;
- `--recursive` dependency traversal;
- bundle indexing;
- `$ORIGIN` expansion for common `RUNPATH` and `RPATH` layouts;
- local dependency lookup through bundle directories;
- dependency states:
  - `bundled`;
  - `target`;
  - `missing`;
  - `ambiguous`;
- `dependency_graph` in JSON reports;
- compare mode checks recursively resolved bundled ELF files against the selected target profile.

### v0.8

v0.8 added normalized diagnostics and CI gates.

Important features:

- stable diagnostic models:
  - `DiagnosticIssue`;
  - `DiagnosticSummary`;
  - `DiagnosticSeverity`;
  - `DiagnosticCategory`;
- JSON report fields:
  - `summary`;
  - `diagnostics`;
- stable issue codes such as:
  - `CL_ARCH_MISMATCH`;
  - `CL_INTERP_MISSING`;
  - `CL_LIB_MISSING`;
  - `CL_SYMBOL_GLIBC_TOO_NEW`;
  - `CL_SYMBOL_GLIBCXX_TOO_NEW`;
  - `CL_SYMBOL_CXXABI_TOO_NEW`;
  - `CL_BUNDLE_AMBIGUOUS_LIB`;
  - `CL_BUNDLE_MAX_DEPTH_REACHED`;
  - `CL_BUNDLE_MAX_FILES_REACHED`;
  - `CL_RPATH_ABSOLUTE`;
  - `CL_RPATH_ESCAPES_BUNDLE`;
  - `CL_RPATH_UNRESOLVED_TOKEN`;
  - `CL_ELF_SCAN_FAILED`;
- `--fail-on error|warning|never` for `scan` and `compare`;
- diagnostic summary calculation;
- dependency-chain attribution for dependency diagnostics;
- rich terminal diagnostic output.

### v0.9

v0.9 added static HTML reports.

Important features:

- `--html PATH` for `scan`;
- `--html PATH` for `compare`;
- static self-contained HTML renderer;
- no external scripts, fonts, images, CDN links, server, database, or daemon;
- HTML sections for:
  - report header;
  - command context;
  - diagnostic summary;
  - normalized diagnostics;
  - bundle dependency resolution;
  - compatibility problems and warnings;
  - compact ELF, target profile, and schema metadata;
- HTML escaping for report data;
- error handling for invalid/unwritable HTML output paths;
- tests for renderer escaping, diagnostics rendering, dependency graph rendering, legacy issue rendering, CLI `--html`, combined JSON/HTML output, and `--fail-on` behavior with HTML output.

---

## 4. Scope of v0.10

### Main goal

Refactor the codebase into clear, modular, extensible internal layers before adding package artifact support.

### Desired result

After v0.10, the codebase should make this future development path realistic:

```text
Add WHEEL support = add wheel detector/extractor/scanner tests + minimal registration.
Add RPM support   = add rpm detector/extractor/scanner tests + minimal registration.
Add DEB support   = add deb detector/extractor/scanner tests + minimal registration.
```

It should not require large changes in:

- CLI command handlers;
- diagnostics model definitions;
- JSON report writing;
- HTML renderer;
- ELF parsing internals;
- bundle resolver internals;
- profile loading;
- CI gate logic.

---

## 5. Explicit non-goals for v0.10

Do **not** implement these in v0.10:

- wheel scanning;
- RPM scanning;
- DEB scanning;
- SBOM generation;
- vulnerability scanning;
- automatic `patchelf` fixes;
- execution of artifacts in containers;
- Docker image mutation, commit, save, or push;
- web UI;
- database;
- daemon/server mode;
- public plugin system through Python entry points;
- arbitrary package installation outside the already existing runtime preset flow;
- breaking JSON schema changes;
- breaking CLI changes.

The refactor must preserve existing user-facing behavior.

---

## 6. Development rules for Codex

Follow these rules strictly.

### 6.1 Inspect before changing

Before editing code:

1. inspect the repository layout;
2. identify existing modules and tests;
3. locate CLI handlers;
4. locate current scanner/comparison/reporting logic;
5. locate models and diagnostics;
6. locate bundle resolver code;
7. locate profile generation and Docker-related code;
8. run the existing tests if the environment allows it.

Do not assume file names from this handoff are exact. Treat suggested module names as target architecture guidance and adapt them to the actual repository.

### 6.2 Preserve behavior

This is a refactoring release. Existing behavior must remain compatible.

Do not intentionally change:

- CLI command names;
- CLI option names;
- default exit behavior;
- `--fail-on` semantics;
- JSON report fields;
- diagnostic issue codes;
- profile YAML format;
- HTML output availability;
- current bundle resolution behavior.

If a small change is unavoidable, document it clearly in the release note and tests.

### 6.3 Work incrementally

Prefer small, verifiable changes.

Recommended order:

1. move code without changing behavior;
2. add request/result models;
3. introduce service/use-case classes;
4. isolate adapters;
5. isolate renderers;
6. add tests after each meaningful extraction;
7. run the verification commands frequently.

Avoid a massive rewrite in one patch.

### 6.4 Keep public schemas stable

The following should be treated as public or semi-public compatibility surfaces:

- JSON reports for `scan` and `compare`;
- diagnostic issue codes;
- diagnostic summary fields;
- dependency graph fields;
- profile YAML schema;
- CLI options documented in README.

### 6.5 Prefer explicit models

Use explicit request/result/config models instead of passing large argument lists across layers.

Recommended models:

- `ScanRequest`;
- `ScanResult`;
- `CompareRequest`;
- `CompareResult`;
- `ArtifactRef`;
- `ArtifactKind`;
- possibly `ReportWriteRequest` or equivalent if useful.

If the project already uses Pydantic models, keep using the same style.
If the project uses dataclasses in a specific area, keep local consistency.

### 6.6 Keep CLI thin

Typer command functions should not perform deep business logic.

They should mainly:

1. parse CLI options;
2. build request/config objects;
3. call application/use-case services;
4. render terminal output;
5. write JSON/HTML if requested;
6. return/raise the correct exit code.

### 6.7 Keep external tools behind adapters

Calls to external tools or the operating system should be easy to mock and test.

Examples:

- `readelf` invocation;
- Docker CLI invocation;
- filesystem traversal;
- process execution;
- temporary directory/rootfs export handling.

Do not let low-level subprocess calls leak into high-level domain logic.

---

## 7. Target architecture

The exact final structure may differ from this proposal, but the codebase should move toward the following logical layers.

### 7.1 CLI layer

Suggested responsibility:

```text
User input/output boundary.
```

Possible package:

```text
compatlab/cli/
  app.py
  scan.py
  compare.py
  profiles.py
```

The CLI layer should not parse ELF, resolve bundles, build diagnostics directly, or know HTML internals.

### 7.2 Application/use-case layer

Suggested responsibility:

```text
Coordinates complete user scenarios.
```

Possible package:

```text
compatlab/app/
  scan.py
  compare.py
  profiles.py
```

Possible classes/functions:

```python
class ScanUseCase:
    def run(self, request: ScanRequest) -> ScanResult: ...

class CompareUseCase:
    def run(self, request: CompareRequest) -> CompareResult: ...
```

This layer may coordinate:

- artifact detection;
- ELF scanning;
- bundle resolving;
- target profile loading;
- comparison;
- diagnostic building;
- summary calculation.

It should not format terminal tables or write HTML by itself.

### 7.3 Artifact layer

Suggested responsibility:

```text
Represents input artifacts and their type.
```

Possible package:

```text
compatlab/artifacts/
  models.py
  detection.py
  registry.py
```

Suggested model:

```python
class ArtifactKind(str, Enum):
    ELF = "elf"
    DIRECTORY = "directory"
    BUNDLE = "bundle"
    WHEEL = "wheel"
    RPM = "rpm"
    DEB = "deb"
    UNKNOWN = "unknown"

class ArtifactRef(BaseModel):
    path: Path
    kind: ArtifactKind
    display_name: str
```

For v0.10, wheel/RPM/DEB can exist only as enum values or documented future kinds. Do not implement their actual scanning.

### 7.4 Extractor layer

Suggested responsibility:

```text
Turns an artifact into one or more scan candidates.
```

Possible package:

```text
compatlab/extractors/
  base.py
  single_file.py
  directory.py
```

Future package modules may be added later:

```text
compatlab/extractors/wheel.py
compatlab/extractors/rpm.py
compatlab/extractors/deb.py
```

Do not implement wheel/RPM/DEB extraction in v0.10 unless the user explicitly asks later.

### 7.5 ELF layer

Suggested responsibility:

```text
Everything specific to ELF binaries and shared libraries.
```

Possible package:

```text
compatlab/elf/
  models.py
  scanner.py
  parser.py
  dynamic.py
  symbols.py
  rpath.py
```

This layer owns:

- ELF file identification;
- `readelf` output parsing;
- architecture extraction;
- interpreter extraction;
- `DT_NEEDED` extraction;
- `RPATH`/`RUNPATH` extraction;
- symbol version extraction;
- ELF scan errors.

This layer should not know how to render HTML, parse Typer options, or decide CI exit codes.

### 7.6 Bundle layer

Suggested responsibility:

```text
Resolves local shared-library dependencies inside application bundles.
```

Possible package:

```text
compatlab/bundles/
  models.py
  index.py
  resolver.py
  graph.py
  limits.py
```

This layer owns:

- bundle root indexing;
- recursive dependency traversal;
- max files and max depth limits;
- `$ORIGIN` expansion;
- `RUNPATH`/`RPATH` lookup;
- common bundle library directories;
- bundled/target/missing/ambiguous resolution states;
- dependency graph model.

This layer should not render Rich tables or write JSON directly.

### 7.7 Profiles layer

Suggested responsibility:

```text
Loads, validates, detects, and generates target system profiles.
```

Possible package:

```text
compatlab/profiles/
  models.py
  loader.py
  validator.py
  generator.py
  docker_image.py
  runtime_presets.py
```

This may already exist. Refactor only where it improves boundaries.
Do not rewrite working profile generation just for aesthetics.

### 7.8 Diagnostics layer

Suggested responsibility:

```text
Converts facts and comparison results into stable normalized diagnostics.
```

Possible package:

```text
compatlab/diagnostics/
  models.py
  summary.py
  builders/
    elf.py
    bundle.py
    compare.py
```

This layer owns:

- `DiagnosticIssue`;
- `DiagnosticSummary`;
- `DiagnosticSeverity`;
- `DiagnosticCategory`;
- issue code constants;
- summary calculation;
- diagnostic builder functions/classes.

Diagnostics should not be created randomly across the whole codebase.
Prefer builder functions/classes with clear inputs.

### 7.9 Reports layer

Suggested responsibility:

```text
Turns result models into user-facing formats.
```

Possible package:

```text
compatlab/reports/
  models.py
  json_writer.py
  html_renderer.py
  terminal_renderer.py
```

This layer owns:

- terminal rendering;
- JSON writing;
- HTML rendering;
- report escaping rules;
- stable report model conversion.

Reports should consume `ScanResult`/`CompareResult` or a normalized report model.
Reports should not scan files or resolve dependencies.

### 7.10 Adapter layer

Suggested responsibility:

```text
Isolates interaction with the operating system and external tools.
```

Possible package:

```text
compatlab/adapters/
  process.py
  readelf.py
  docker.py
  filesystem.py
```

This layer owns:

- subprocess calls;
- Docker CLI calls;
- readelf execution;
- filesystem wrappers if useful;
- temporary directories if useful.

---

## 8. Concrete v0.10 task list

### Task 1 — Repository audit

Inspect the current repository and identify:

- current package layout;
- CLI modules;
- scanner modules;
- comparison modules;
- profile modules;
- bundle resolver modules;
- diagnostics modules;
- report/HTML modules;
- tests layout.

Create or update a short internal architecture document:

```text
docs/internal-architecture.md
```

The document should describe:

- current high-level layers;
- where CLI ends and application logic begins;
- where ELF-specific logic lives;
- where bundle logic lives;
- where diagnostics live;
- where reports live;
- how future package artifact scanning should plug in.

Acceptance criteria:

- document exists;
- document is short enough to be useful;
- document matches the actual repository, not an imaginary one.

---

### Task 2 — Introduce request/result models

Add explicit models for main operations.

Recommended:

```python
ScanRequest
ScanResult
CompareRequest
CompareResult
```

These models should collect inputs and outputs currently passed between CLI and internal functions.

Acceptance criteria:

- `scan` use case can be called without Typer;
- `compare` use case can be called without Typer;
- tests can construct request objects directly;
- no CLI behavior changes.

---

### Task 3 — Extract scan and compare use cases

Create an application/use-case layer for main workflows.

Recommended:

```text
compatlab/app/scan.py
compatlab/app/compare.py
```

or equivalent names matching the current project style.

The use cases should coordinate existing logic but avoid direct terminal formatting.

Acceptance criteria:

- CLI calls scan/compare use cases;
- use cases return result objects;
- terminal/JSON/HTML rendering is performed outside deep scanning logic;
- existing CLI tests still pass.

---

### Task 4 — Make CLI command handlers thin

Refactor Typer command functions so they mainly:

1. parse arguments;
2. create request objects;
3. call use cases;
4. call renderers/writers;
5. apply `--fail-on` exit behavior.

Acceptance criteria:

- CLI modules contain little or no ELF parsing/comparison logic;
- CLI remains readable;
- existing commands and options are preserved;
- `--json`, `--html`, and `--fail-on` still work as before.

---

### Task 5 — Isolate ELF-specific code

Move or clarify ELF-specific logic into a dedicated ELF module/package.

This includes:

- readelf parsing;
- ELF metadata models;
- dynamic section data;
- needed libraries;
- symbol versions;
- interpreter;
- architecture;
- runtime paths;
- ELF scan failures.

Acceptance criteria:

- ELF logic is reusable from non-CLI code;
- future package extractors can feed extracted ELF files into the same ELF scanner;
- ELF module does not import CLI modules;
- tests still cover current ELF scan behavior.

---

### Task 6 — Isolate bundle resolver

Ensure bundle resolution is implemented as a standalone component.

It should expose clear request/result models or functions.

It should own:

- bundle indexing;
- recursive dependency traversal;
- limit handling;
- `$ORIGIN` handling;
- resolution candidates;
- dependency graph construction.

Acceptance criteria:

- bundle resolver can be unit tested without CLI;
- compare/scan use cases call the resolver through a clean interface;
- JSON `dependency_graph` output remains compatible;
- existing v0.7 behavior is preserved.

---

### Task 7 — Centralize diagnostics builders

Diagnostics were stabilized in v0.8 and must now be treated as a first-class layer.

Refactor diagnostic construction into clear builder functions/classes.

Recommended split:

- ELF diagnostics;
- bundle diagnostics;
- comparison diagnostics;
- summary calculation.

Acceptance criteria:

- stable issue codes remain unchanged;
- diagnostics are not built ad hoc in unrelated modules;
- `summary` calculation remains deterministic;
- `--fail-on error|warning|never` behavior remains unchanged.

---

### Task 8 — Separate report renderers/writers

Ensure terminal, JSON, and HTML report handling are separated from scan/compare logic.

Recommended:

```text
compatlab/reports/json_writer.py
compatlab/reports/html_renderer.py
compatlab/reports/terminal_renderer.py
```

or equivalent current-style module names.

Acceptance criteria:

- HTML renderer remains static and self-contained;
- HTML escaping tests still pass;
- JSON report writing remains stable;
- terminal rendering remains human-friendly;
- scan/compare business logic does not format HTML directly.

---

### Task 9 — Add artifact abstraction

Introduce a small artifact model layer to prepare for future package support.

Recommended:

```python
ArtifactKind
ArtifactRef
ArtifactDetector
```

Initial supported kinds may include:

- ELF/single file;
- directory/bundle;
- unknown.

Future reserved kinds may include:

- wheel;
- rpm;
- deb.

Acceptance criteria:

- current scan/compare input can be represented as `ArtifactRef` or equivalent;
- future package kinds have a clear place to be added;
- current CLI behavior remains unchanged;
- no actual wheel/RPM/DEB scanning is implemented in v0.10.

---

### Task 10 — Add minimal internal registry if useful

If it fits the current architecture, add a simple internal registry for artifact handlers.

Example idea:

```python
registry.register(ArtifactKind.ELF, elf_handler)
registry.register(ArtifactKind.DIRECTORY, directory_handler)
```

Do not implement a public plugin system yet.

Acceptance criteria:

- registry is internal and simple;
- no entry point plugin system;
- adding a future package handler has an obvious place;
- current behavior remains unchanged.

---

### Task 11 — Isolate external adapters

Move external command interactions into adapter modules where practical.

Priority:

1. `readelf` adapter;
2. Docker adapter;
3. process execution helper;
4. filesystem helper only if it reduces coupling.

Acceptance criteria:

- high-level logic does not directly call `subprocess.run` for `readelf` or Docker if avoidable;
- adapters are easy to mock in tests;
- existing profile generation from Docker image still works;
- existing readelf-based ELF scan still works.

---

### Task 12 — Add import-boundary tests

Add lightweight tests that prevent obvious architecture regressions.

Suggested checks:

- `compatlab/elf` must not import `compatlab/cli`;
- `compatlab/bundles` must not import `compatlab/cli`;
- `compatlab/diagnostics` must not import HTML renderer;
- `compatlab/reports` must not invoke scanners;
- CLI modules should depend on app/use-case layer, not the other way around.

These tests can be simple static source/import checks.
Do not add a heavy dependency unless already present or clearly justified.

Acceptance criteria:

- import-boundary tests exist;
- tests are simple and maintainable;
- tests prevent the worst coupling mistakes.

---

### Task 13 — Add golden/compatibility tests

Because this is a refactoring release, add tests that prove behavior did not change.

Cover at least:

- `scan` for a known ELF sample;
- `compare` for a known ELF sample;
- `scan --bundle-root --recursive`;
- `compare --bundle-root --recursive`;
- `--json` report output;
- `--html` report output;
- `--fail-on error`;
- `--fail-on warning`;
- `--fail-on never`.

If such tests already exist, strengthen them instead of duplicating.

Acceptance criteria:

- existing behavior is protected;
- report fields remain stable;
- exit-code behavior remains stable.

---

### Task 14 — Update README and release note

Update project documentation to mention v0.10 architecture stabilization.

README should make clear:

- current user-facing commands are unchanged;
- project remains ELF/bundle focused for now;
- wheel/RPM/DEB are still not implemented;
- architecture is now prepared for future package artifact support.

Add release note:

```text
v0.10.md
```

Suggested title:

```text
CompatLab ArtifactDoctor 0.10 — Architecture Refactor
```

Acceptance criteria:

- release note exists;
- non-goals are explicit;
- verification commands are listed;
- no false claim that wheel/RPM/DEB scanning works.

---

## 9. Suggested final repository shape

This is a target direction, not a mandatory exact tree.
Adapt it to the actual repository.

```text
compatlab/
  cli/
    app.py
    scan.py
    compare.py
    profiles.py

  app/
    scan.py
    compare.py
    profiles.py

  artifacts/
    models.py
    detection.py
    registry.py

  extractors/
    base.py
    single_file.py
    directory.py

  elf/
    models.py
    scanner.py
    parser.py
    dynamic.py
    symbols.py
    rpath.py

  bundles/
    models.py
    index.py
    resolver.py
    graph.py
    limits.py

  diagnostics/
    models.py
    summary.py
    builders/
      elf.py
      bundle.py
      compare.py

  profiles/
    models.py
    loader.py
    validator.py
    generator.py
    docker_image.py
    runtime_presets.py

  reports/
    models.py
    json_writer.py
    html_renderer.py
    terminal_renderer.py

  adapters/
    process.py
    readelf.py
    docker.py
    filesystem.py

  errors.py
```

Do not force this exact layout if the current repository already has a good structure.
The goal is clear responsibility boundaries, not folder choreography.

---

## 10. Compatibility requirements

### CLI compatibility

These command patterns must continue to work:

```bash
uv run compatlab scan ./app
uv run compatlab scan ./dist/my-app --bundle-root ./dist --recursive
uv run compatlab scan ./dist/my-app --bundle-root ./dist --recursive --json report.json
uv run compatlab scan ./dist/my-app --bundle-root ./dist --recursive --html report.html

uv run compatlab compare ./app --target ubuntu-1804
uv run compatlab compare ./app --target-file ./local.yaml
uv run compatlab compare ./dist/my-app --target-file ./local.yaml --bundle-root ./dist --recursive
uv run compatlab compare ./dist/my-app --target-file ./local.yaml --bundle-root ./dist --recursive --fail-on warning
uv run compatlab compare ./dist/my-app --target-file ./local.yaml --bundle-root ./dist --recursive --json report.json --html report.html
```

### JSON compatibility

Do not remove or rename existing public report fields.

Especially preserve:

- `summary`;
- `diagnostics`;
- `dependency_graph`;
- legacy `problems` and `warnings` fields if they are still present;
- target/ELF/schema metadata currently emitted by the project.

### Diagnostic compatibility

Do not rename existing issue codes.

Existing codes from v0.8 must remain valid.

### HTML compatibility

HTML reports must remain:

- static;
- self-contained;
- escaped;
- free of external scripts, fonts, images, CDN links, server requirements, database requirements, or daemon requirements.

### Exit-code compatibility

Preserve `--fail-on` behavior:

- `error`: fail on error diagnostics;
- `warning`: fail on warning or error diagnostics;
- `never`: do not fail because of diagnostics if command execution completed.

---

## 11. Testing and verification commands

Run these commands before considering the implementation done:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
make check
```

If coverage commands exist and work in the repository, also run:

```bash
make coverage
```

If formatting changes are needed:

```bash
uv run ruff format .
```

Manual smoke checks:

```bash
uv run compatlab scan /bin/bash
uv run compatlab scan /bin/bash --json /tmp/compatlab-scan.json
uv run compatlab scan /bin/bash --html /tmp/compatlab-scan.html
uv run compatlab profiles list
uv run compatlab profiles detect
```

If a suitable target profile exists:

```bash
uv run compatlab compare /bin/bash --target-file ./local.yaml
```

---

## 12. Definition of done

v0.10 is complete when all of the following are true:

1. Existing CLI behavior is preserved.
2. Existing JSON report compatibility is preserved.
3. Existing HTML report behavior is preserved.
4. Existing diagnostics and issue codes are preserved.
5. `scan` and `compare` are available as callable use cases independent of Typer.
6. CLI command handlers are thinner than before.
7. ELF-specific logic is isolated and reusable.
8. Bundle resolver is isolated and unit-testable.
9. Diagnostics construction is centralized.
10. Report rendering/writing is separated from scanning/comparison logic.
11. Artifact abstraction exists or is clearly prepared.
12. Future wheel/RPM/DEB support has an obvious extension point.
13. Import-boundary or equivalent architecture tests exist.
14. Compatibility/golden tests protect current behavior.
15. README and release note are updated.
16. `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, and `make check` pass.

---

## 13. Recommended implementation sequence

Use this order to minimize risk.

### Phase 0 — Baseline

1. Inspect repository.
2. Run current tests.
3. Record current test count and any existing failures.
4. Identify current public report models.
5. Identify current CLI entry points.

### Phase 1 — Request/result models

1. Add `ScanRequest` and `CompareRequest`.
2. Add `ScanResult` and `CompareResult` or adapt existing models.
3. Update tests to call internal logic through these models where easy.

### Phase 2 — Use cases

1. Add scan use case.
2. Add compare use case.
3. Move orchestration logic out of CLI.
4. Keep CLI behavior unchanged.

### Phase 3 — ELF and adapters

1. Isolate readelf invocation.
2. Isolate readelf parsing.
3. Ensure ELF scanner can be called from future package extractors.

### Phase 4 — Bundle layer

1. Isolate bundle index/resolver/graph models.
2. Keep JSON graph compatibility.
3. Preserve v0.7 resolution behavior.

### Phase 5 — Diagnostics layer

1. Centralize diagnostic builders.
2. Keep issue codes stable.
3. Keep summary stable.
4. Keep fail-on behavior stable.

### Phase 6 — Reports layer

1. Separate terminal rendering.
2. Separate JSON writing.
3. Separate HTML rendering.
4. Keep HTML escaping tests.

### Phase 7 — Artifact abstraction

1. Add `ArtifactKind` and `ArtifactRef`.
2. Add basic detector if useful.
3. Add minimal internal registry only if it makes the code simpler.
4. Do not implement package scanning.

### Phase 8 — Tests and docs

1. Add architecture/import-boundary tests.
2. Add or strengthen golden tests.
3. Update README.
4. Add `v0.10.md` release note.
5. Run full verification.

---

## 14. Notes for future v0.11+

v0.10 should prepare the ground for future package artifact versions.

Possible future roadmap:

### v0.11 — Wheel scanning

- detect `.whl`;
- extract wheel safely into temp directory;
- find ELF `.so` files inside the wheel;
- scan extracted ELF files using existing ELF scanner;
- report Python package metadata if useful;
- compare included native extensions against target profile.

### v0.12 — DEB scanning

- detect `.deb`;
- extract package contents safely;
- find ELF binaries/libraries;
- scan and compare them;
- report package metadata.

### v0.13 — RPM scanning

- detect `.rpm`;
- extract package contents safely;
- find ELF binaries/libraries;
- scan and compare them;
- report package metadata.

These future versions should reuse v0.10 architecture instead of duplicating ELF scan logic.

---

## 15. Final instruction to Codex

Implement v0.10 as a disciplined refactoring release.

Do not chase new product features.
Do not implement wheel/RPM/DEB scanning yet.
Do not break existing CLI/report behavior.

Focus on clear internal boundaries, reusable use cases, isolated ELF and bundle logic, centralized diagnostics, separated renderers, and extension points for future package artifact support.

The best v0.10 outcome is boring from the user's perspective and much cleaner from the developer's perspective.
That is the point.
