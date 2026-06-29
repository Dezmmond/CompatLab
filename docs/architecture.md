# CompatLab Architecture

This document records the current module responsibilities and the intended
module boundaries for the next refactoring steps.

## Current State

### CLI and orchestration

CLI logic lives in `compatlab/src/cli.py`.

The module owns Typer command registration, option parsing, Rich console output,
user-facing error handling, and exit-code decisions. It also currently
orchestrates several workflows directly:

- `scan`: calls ELF scanning, optional bundle resolution, diagnostic enrichment,
  JSON/HTML writers, terminal rendering, and `--fail-on` handling.
- `compare`: loads the target profile, scans the artifact, optionally resolves
  bundle dependencies, calls the compare engine for the entrypoint and bundled
  libraries, builds bundle dependency problems, enriches diagnostics, writes
  reports, renders terminal output, and applies `--fail-on`.
- `profiles`: detects/generates/validates profiles from the current system or
  Docker images.

`cli.py` is therefore the largest coupling point today. It imports scanner,
bundle resolver, compare engine, diagnostics, profile loaders/generators, and
report writers.

### ELF scanning

ELF scanning lives in `compatlab/src/elfscan/`.

- `scanner.py` exposes `scan_path(path)` and builds an `ArtifactReport`.
- `command.py` contains the generic external command runner and `run_readelf`.
- `parsers.py` parses `readelf` output for headers, program headers, dynamic
  section data, and symbol version requirements.
- `models.py` defines `ElfInfo` and `SymbolVersion`.

The scanner is responsible for translating partial or failed `readelf` results
into scan warnings. It does not compare against target profiles.

### Compare result construction

Compatibility comparison lives in `compatlab/src/compare/engine.py`.

`compare_report(report, target, assumed_provided_libraries=...)` receives an
already scanned `ArtifactReport` and a `TargetProfile`, then returns a copied
report with `target`, `problems`, and `warnings` populated.

The compare engine owns compatibility checks for:

- architecture mismatch;
- dynamic linker/interpreter availability;
- glibc, GLIBCXX, and CXXABI version requirements;
- missing target libraries;
- absolute or build-time RPATH/RUNPATH values.

Bundle-aware compare behavior is only partially in the compare layer. The
actual bundle traversal is in the bundle resolver, while `cli.py` currently
coordinates comparing bundled ELF reports and merging their problems.

### Diagnostics

Normalized diagnostics live in `compatlab/src/diagnostics.py`.

The module defines:

- `DiagnosticIssue`;
- `DiagnosticSummary`;
- `DiagnosticSeverity`;
- `DiagnosticCategory`;
- `FailOn`;
- `diagnostics_from_report_parts`;
- `summarize_diagnostics`;
- `should_fail_for_diagnostics`.

Diagnostics are generated from legacy `Problem` objects and bundle
`DependencyGraph` unresolved edges. `cli.py` currently calls the private
workflow helper `_with_diagnostics()` to attach `diagnostics` and `summary` to
reports before rendering or writing them.

### Report models and terminal output

Report data models live in `compatlab/src/report/models.py`.

`ArtifactReport` is the central report object. It carries artifact metadata,
optional ELF data, optional target profile, diagnostics summary, diagnostics,
dependency graph, legacy problems, and legacy warnings.

Terminal rendering lives in `compatlab/src/report/pretty.py`.

### JSON reports

JSON report writing lives in `compatlab/src/report/json.py`.

`write_json_report(report, path)` serializes `ArtifactReport` with Pydantic
`model_dump_json`. It does not own report construction or diagnostics.

### HTML reports

HTML report rendering lives in `compatlab/src/report/html.py`.

The module defines:

- `HtmlReportContext`;
- `render_html_report(report, context=...)`;
- `write_html_report(report, output_path, context=...)`;
- small section renderers for summary, diagnostics, dependency graph, legacy
  problems/warnings, and technical metadata.

HTML output is static and self-contained. The renderer escapes report strings
before inserting them into HTML. It does not scan, compare, or generate
diagnostics.

### Bundle resolver

Bundle dependency resolution lives in `compatlab/src/bundle/`.

- `models.py` defines `DependencyGraph`, `DependencyNode`, `DependencyEdge`, and
  `DependencyResolutionKind`.
- `resolver.py` exposes `resolve_bundle_dependencies(...)`.

The resolver indexes files under `--bundle-root`, scans ELF files through
`elfscan.scanner.scan_path`, follows direct or recursive `DT_NEEDED`
dependencies, expands `$ORIGIN` search paths, classifies dependencies as
`bundled`, `target`, `missing`, or `ambiguous`, and returns a
`BundleResolutionResult` with graph, scanned reports, and warnings.

The resolver currently depends on ELF scanning and target profile library facts.
It does not run the compare engine itself.

### Profiles

Profile logic lives in `compatlab/src/profile/`.

- `models.py` defines `SystemFacts`, `TargetProfile`, profile metadata, library
  facts, symbol facts, and warnings.
- `loader.py` loads built-in or external YAML profiles.
- `builtin.py` locates built-in profile files under `compatlab/profiles/`.
- `detect.py` detects facts from the current host using `ldd`, `ldconfig`, and
  `readelf`.
- `generate.py` converts `SystemFacts` into `TargetProfile`.
- `docker_image.py` detects facts from Docker image rootfs exports.
- `docker_cli.py` wraps Docker CLI operations.
- `rootfs_tar.py` parses exported rootfs tar files.
- `runtime_presets.py` defines runtime package presets and install scripts.
- `ldd.py`, `ldconfig.py`, `linkers.py`, and `os_release.py` contain focused
  parsers/helpers.

Profile detection and generation are separate from artifact scanning and
compare, but Docker image detection reuses `readelf` parsing for library symbol
versions.

### External tools

External command execution is concentrated in two places:

- `compatlab/src/elfscan/command.py` runs generic commands and `readelf`.
- `compatlab/src/profile/docker_cli.py` builds Docker CLI commands using the
  shared command runner.

Current direct external tool usage:

- `readelf`: artifact scanning, current-system library symbol detection, Docker
  rootfs library symbol detection.
- `ldd --version`: current-system glibc detection.
- `ldconfig -p`: current-system library inventory.
- `docker`: image inspect, pull, create, start, export, and cleanup.

## Target Module Boundaries

The current architecture is workable, but the next step should reduce workflow
coupling in `cli.py`.

### CLI target responsibility

`compatlab/src/cli.py` should stay a thin adapter:

- parse command-line options;
- call application services;
- render user-facing success/error messages;
- translate service outcomes into exit codes.

It should not assemble compare workflows, merge bundled report problems, or know
the detailed order of scan, bundle, compare, diagnostics, and report writing.

### Application service layer

Introduce a small workflow layer, for example `compatlab/src/app/` or
`compatlab/src/workflows/`, with services such as:

- `scan_artifact(options) -> ArtifactReport`;
- `compare_artifact(options) -> ArtifactReport`;
- `generate_profile(options) -> TargetProfile`;
- `detect_profile_facts(options) -> SystemFacts`;
- `write_requested_reports(report, outputs, context)`.

This layer should own orchestration and keep domain modules focused.

### Domain modules

Keep the existing domain boundaries:

- `elfscan`: extract ELF facts from files.
- `compare`: compare scanned facts to target profiles.
- `bundle`: resolve local dependency graphs.
- `diagnostics`: normalize problems/graphs into stable diagnostic issues and
  summaries.
- `profile`: load, detect, and generate target profiles.
- `report`: data models and renderers/writers.

### External adapters

Keep command execution isolated from domain logic:

- `elfscan.command` remains the generic process runner and readelf adapter.
- `profile.docker_cli` remains the Docker adapter.
- Current-system adapters for `ldd` and `ldconfig` should remain inside
  `profile` or move behind explicit adapter functions if they grow.

Domain code should receive parsed data or adapter results rather than constructing
raw shell commands directly.

### Report pipeline

The target report pipeline should be:

1. Workflow builds an `ArtifactReport`.
2. Workflow attaches diagnostics through `diagnostics`.
3. CLI or workflow writes requested outputs through `report.json` and
   `report.html`.
4. CLI renders terminal output through `report.pretty`.
5. CLI applies the selected `FailOn` gate based on diagnostics.

JSON and HTML should remain renderers of the report model, not places where
compatibility decisions are made.

### Known coupling to address

- `cli.py` currently contains compare orchestration for bundled libraries.
- `cli.py` owns `_dependency_problems`, which converts unresolved bundle edges
  into legacy `Problem` objects.
- `cli.py` owns `_with_diagnostics`, although diagnostic enrichment is a report
  pipeline concern.
- `profile/docker_image.py` reuses compare helpers for version sorting and
  architecture normalization; these helpers may eventually belong in a shared
  normalization module.
- `bundle/resolver.py` scans ELF files directly; this is acceptable for now, but
  a workflow layer could make scanning dependencies explicit and easier to mock.
