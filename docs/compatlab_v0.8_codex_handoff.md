# CompatLab ArtifactDoctor 0.8 — Codex Handoff

## 1. Purpose of this handoff

This document is a complete implementation handoff for the Codex agent. It describes the expected development work for **CompatLab ArtifactDoctor 0.8**.

The agent must use this document as the main specification for the next release. The goal is to implement v0.8 without breaking the behavior delivered in v0.4–v0.7.

The preferred release theme is:

> **Actionable diagnostics and CI quality gates.**

In simple terms: v0.7 taught CompatLab to understand a local bundle dependency graph. v0.8 must make the diagnosis clearer, more stable, more machine-readable, and more useful in CI/CD pipelines.

---

## 2. Project overview

CompatLab ArtifactDoctor is a Python-first CLI tool for checking whether Linux binary artifacts are likely to run on a target Linux profile before they are shipped.

The product goal is to turn low-level ELF facts into a useful compatibility diagnosis:

- missing dynamic linker;
- missing `DT_NEEDED` shared libraries;
- architecture mismatch;
- too-new `glibc` requirements;
- too-new `libstdc++` / `GLIBCXX_*` requirements;
- too-new `CXXABI_*` requirements;
- suspicious `RPATH` / `RUNPATH` values;
- local bundle dependency resolution problems.

CompatLab is intentionally a static preflight checker. It should not execute artifacts, mutate Docker images, patch binaries, scan vulnerabilities, or become a package manager frontend.

---

## 3. Historical context

### v0.4 — current-system profile generation

v0.4 added profile generation from the current Linux system:

- raw system facts detection;
- `/etc/os-release` parsing;
- architecture detection;
- glibc detection;
- `ldconfig -p` parsing;
- dynamic linker detection;
- symbol-version extraction from system libraries;
- YAML target profile generation;
- profile validation;
- compare against an explicit YAML target profile.

### v0.5 — Docker image profile generation

v0.5 added target profile generation from a Docker image rootfs export:

- Docker CLI orchestration;
- rootfs tar parsing;
- `/etc/os-release` parsing from image rootfs;
- library discovery inside exported rootfs;
- host-side `readelf` over extracted libraries;
- `profiles generate --from-image IMAGE`;
- `profiles detect --from-image IMAGE --json PATH`;
- Docker source metadata in generated profiles.

### v0.6 — Docker runtime presets

v0.6 added temporary runtime profile generation from Docker images with predefined package presets:

- built-in runtime preset registry;
- `cpp-runtime` and `python-runtime` presets;
- `profiles runtime-presets list`;
- `profiles runtime-presets show PRESET`;
- package manager detection for `apt-get`, `dnf`, and `yum`;
- temporary container installation flow;
- runtime-aware profile generation and raw facts export.

### v0.7 — bundle-aware recursive dependency resolution

v0.7 added local bundle dependency resolution:

- new `compatlab/src/bundle/` module;
- `DependencyGraph`, `DependencyNode`, `DependencyEdge` models;
- bundle resolver;
- `scan` and `compare` flags:
  - `--bundle-root`;
  - `--recursive`;
  - `--max-depth`;
  - `--max-files`;
- `$ORIGIN` expansion;
- `RUNPATH` and `RPATH` lookup;
- lookup in common bundle directories:
  - `lib/`;
  - `lib64/`;
  - `usr/lib/`;
  - `usr/lib64/`;
- fallback lookup by filename;
- resolution states:
  - `bundled`;
  - `target`;
  - `missing`;
  - `ambiguous`;
- `dependency_graph` in JSON reports;
- Rich dependency resolution table in terminal reports;
- `compare` checks recursively resolved bundled ELF libraries against the target profile;
- resolver tests, CLI JSON tests, and compare suppression tests for bundled libraries.

The reported v0.7 verification result:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Expected test result from the latest release note:

```text
87 passed
```

---

## 4. v0.8 product decision

Do **not** implement package scanning in v0.8.

Do **not** implement HTML reports in v0.8 unless all required diagnostic and CI work is finished first.

The strongest next step is to improve the usefulness of existing compatibility results.

v0.7 can now build a dependency graph, but users still need answers to practical questions:

- What exactly failed?
- Which artifact caused the failure?
- Which dependency chain led to it?
- Is it an error or only a warning?
- Can CI fail only on errors?
- Can CI fail on warnings too?
- What should I try next?
- Is the JSON stable enough for scripts?

v0.8 must answer these questions.

---

## 5. v0.8 release title

Use one of these names in docs and release notes:

```text
CompatLab ArtifactDoctor 0.8 — Actionable diagnostics and CI gates
```

or shorter:

```text
CompatLab ArtifactDoctor 0.8 — Diagnostic quality gates
```

Preferred title:

```text
CompatLab ArtifactDoctor 0.8 — Actionable diagnostics and CI gates
```

---

## 6. Main v0.8 goals

### Goal 1 — stable diagnostic issue model

Add a normalized diagnostic issue model used by `scan`, `compare`, pretty output, and JSON output.

The model should make compatibility problems explicit and stable.

Recommended model shape:

```python
class DiagnosticSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

class DiagnosticCategory(str, Enum):
    ARTIFACT = "artifact"
    TARGET = "target"
    BUNDLE = "bundle"
    SYMBOLS = "symbols"
    LOADER = "loader"
    RPATH = "rpath"
    LIMITS = "limits"

class DiagnosticIssue(BaseModel):
    code: str
    severity: DiagnosticSeverity
    category: DiagnosticCategory
    title: str
    message: str
    affected_path: str | None = None
    dependency_name: str | None = None
    dependency_chain: list[str] = Field(default_factory=list)
    required: str | None = None
    provided: str | None = None
    hint: str | None = None
```

Do not force this exact implementation if the existing codebase already has better names. Preserve existing project style.

### Goal 2 — stable issue codes

Introduce stable issue codes. They are important for CI and scripts.

Recommended initial issue code set:

| Code | Severity | Meaning |
|---|---:|---|
| `CL_ARCH_MISMATCH` | error | Artifact architecture does not match target architecture. |
| `CL_INTERP_MISSING` | error | Required dynamic linker is not available on target. |
| `CL_LIB_MISSING` | error | Required shared library is missing from bundle and target profile. |
| `CL_SYMBOL_GLIBC_TOO_NEW` | error | Artifact requires a newer `GLIBC_*` version than target provides. |
| `CL_SYMBOL_GLIBCXX_TOO_NEW` | error | Artifact requires a newer `GLIBCXX_*` version than target provides. |
| `CL_SYMBOL_CXXABI_TOO_NEW` | error | Artifact requires a newer `CXXABI_*` version than target provides. |
| `CL_BUNDLE_AMBIGUOUS_LIB` | warning | Bundle contains several candidates for one dependency. |
| `CL_BUNDLE_MAX_DEPTH_REACHED` | warning | Recursive traversal stopped because `--max-depth` was reached. |
| `CL_BUNDLE_MAX_FILES_REACHED` | warning | Bundle indexing stopped because `--max-files` was reached. |
| `CL_RPATH_ABSOLUTE` | warning | Artifact contains an absolute `RPATH` or `RUNPATH` entry. |
| `CL_RPATH_ESCAPES_BUNDLE` | warning | `$ORIGIN`-based path escapes the bundle root. |
| `CL_RPATH_UNRESOLVED_TOKEN` | warning | Unsupported runtime path token was found. |
| `CL_ELF_SCAN_FAILED` | warning or error | `readelf` scan failed for a bundled ELF. Use error only if the main artifact cannot be scanned. |

The actual codes may differ if the existing project already has a code taxonomy. However, after implementation codes must be stable, documented, and tested.

### Goal 3 — human-readable explanations

Pretty output should not only list problems. It should explain them.

Add a diagnostics section to terminal output for `scan` and `compare`.

Recommended format:

```text
Diagnostics

ERROR CL_LIB_MISSING
  libssl.so.3 is required by dist/my-app but was not found in the bundle or target profile.
  Chain: dist/my-app -> libfoo.so -> libssl.so.3
  Hint: install the runtime library on the target image or include a compatible libssl.so.3 in the bundle.

WARNING CL_BUNDLE_AMBIGUOUS_LIB
  libz.so.1 has multiple candidates inside the bundle.
  Candidates:
    dist/lib/libz.so.1
    dist/vendor/libz.so.1
  Hint: prefer a single runtime library location or adjust RUNPATH.
```

Do not make output too noisy by default. A compact mode is acceptable as long as JSON contains full details.

### Goal 4 — CI quality gates

Add CLI flags that make results useful in CI.

Recommended flags for `scan` and `compare`:

```bash
--fail-on error      # default; fail when at least one error diagnostic exists
--fail-on warning    # fail when error or warning diagnostics exist
--fail-on never      # never fail because of diagnostics; still fail on internal CLI/runtime errors
```

Recommended behavior:

- `--fail-on error`: exit code `1` if at least one `error` diagnostic exists;
- `--fail-on warning`: exit code `1` if at least one `warning` or `error` diagnostic exists;
- `--fail-on never`: exit code `0` if command completed and report was produced, even when diagnostics exist;
- internal failures still return non-zero exit code.

Preserve existing default behavior as much as possible. If current `compare` already exits non-zero on compatibility failure, keep the default equivalent to `--fail-on error`.

### Goal 5 — summary counters in JSON

Add summary counters to JSON reports.

Recommended shape:

```json
{
  "summary": {
    "status": "failed",
    "errors": 2,
    "warnings": 1,
    "infos": 0,
    "issue_codes": {
      "CL_LIB_MISSING": 1,
      "CL_SYMBOL_GLIBCXX_TOO_NEW": 1,
      "CL_RPATH_ABSOLUTE": 1
    }
  },
  "diagnostics": []
}
```

Where `status` may be:

- `passed`;
- `warning`;
- `failed`.

Status rules:

- `failed` if any `error` exists;
- `warning` if no errors exist, but at least one warning exists;
- `passed` if neither errors nor warnings exist.

### Goal 6 — dependency chain attribution

For bundle-related diagnostics, include the dependency chain where possible.

Example:

```json
{
  "code": "CL_LIB_MISSING",
  "severity": "error",
  "affected_path": "dist/lib/libfoo.so",
  "dependency_name": "libssl.so.3",
  "dependency_chain": [
    "dist/my-app",
    "dist/lib/libfoo.so",
    "libssl.so.3"
  ]
}
```

If the chain cannot be reconstructed cleanly, provide at least:

- affected artifact path;
- dependency name;
- resolution state from dependency graph.

### Goal 7 — documentation and release note

Update:

- `README.md`;
- `docs/ReleaseNotes/v0.8.md`;
- CLI help text where relevant.

README should show examples:

```bash
uv run compatlab compare ./dist/my-app \
  --target-file /tmp/ubuntu-2204-cpp-runtime.yaml \
  --bundle-root ./dist \
  --recursive \
  --fail-on warning \
  --json report.json
```

Release note must include:

- Summary;
- Added;
- Changed;
- Current Behavior;
- Not Included Yet;
- Verification;
- Next Step.

---

## 7. Detailed task list

### Task 1 — inspect the existing codebase

Before modifying anything, inspect:

```bash
find compatlab -maxdepth 4 -type f | sort
find tests -maxdepth 4 -type f | sort
```

Search for:

```bash
grep -R "Diagnostic\|Issue\|Problem\|severity\|compare\|scan\|dependency_graph\|bundle" -n compatlab tests
```

The agent must adapt to the existing architecture. Do not blindly create duplicate models if issue/problem models already exist.

### Task 2 — add diagnostic models

Add or extend diagnostic models near existing report/domain models.

Likely locations may be one of:

- `compatlab/src/models.py`;
- `compatlab/src/reports.py`;
- `compatlab/src/diagnostics.py`;
- another existing module discovered during inspection.

Requirements:

- use Pydantic models if current reports use Pydantic;
- use enums for severity/category if consistent with project style;
- keep JSON field names stable and readable;
- avoid hidden side effects in model constructors.

### Task 3 — map existing comparison results to diagnostics

Find current comparison problem model and convert it into normalized diagnostics.

Required mappings:

- architecture mismatch -> `CL_ARCH_MISMATCH`;
- missing interpreter/dynamic linker -> `CL_INTERP_MISSING`;
- missing `DT_NEEDED` library -> `CL_LIB_MISSING`;
- too-new `GLIBC_*` -> `CL_SYMBOL_GLIBC_TOO_NEW`;
- too-new `GLIBCXX_*` -> `CL_SYMBOL_GLIBCXX_TOO_NEW`;
- too-new `CXXABI_*` -> `CL_SYMBOL_CXXABI_TOO_NEW`.

Do not delete existing fields from JSON unless necessary. Prefer additive changes.

### Task 4 — map bundle resolver states to diagnostics

From v0.7 dependency graph/resolver results, create diagnostics for:

- missing dependencies;
- ambiguous dependencies;
- max depth reached;
- max files reached;
- scan failure for bundled ELF;
- suspicious `RPATH` / `RUNPATH` when data is already available.

If v0.7 does not expose enough metadata for one of these, add metadata conservatively.

Do not try to fully emulate the Linux dynamic loader.

### Task 5 — add summary calculation

Implement a small pure function similar to:

```python
def summarize_diagnostics(issues: Sequence[DiagnosticIssue]) -> DiagnosticSummary:
    ...
```

The function should be easy to unit test.

Expected summary fields:

- `status`;
- `errors`;
- `warnings`;
- `infos`;
- `issue_codes` map.

### Task 6 — add quality gate evaluation

Implement quality gate logic as a pure function:

```python
def should_fail_for_diagnostics(issues: Sequence[DiagnosticIssue], fail_on: FailOn) -> bool:
    ...
```

Recommended enum:

```python
class FailOn(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    NEVER = "never"
```

CLI flags should parse only allowed values.

### Task 7 — extend CLI

Add `--fail-on` to:

- `scan`;
- `compare`.

Recommended default:

```text
error
```

Optional flag:

```bash
--show-hints / --no-show-hints
```

Do not add this optional flag unless it fits cleanly.

### Task 8 — update terminal output

Add a diagnostics section to Rich output.

It should show:

- severity;
- code;
- short title;
- affected artifact/dependency;
- hint when available.

Keep the existing dependency resolution table from v0.7.

The terminal report should remain readable on normal laptop width. Do not create a five-kilometer table. Long details can go into JSON.

### Task 9 — update JSON reports

JSON reports for `scan` and `compare` must include:

```json
{
  "summary": {},
  "diagnostics": []
}
```

Keep existing v0.7 `dependency_graph` output.

Backward compatibility rule:

- existing report fields should remain unless they are clearly obsolete;
- tests should prove that `dependency_graph` is still emitted when `--bundle-root --recursive --json` is used.

### Task 10 — tests

Add unit tests for:

- diagnostic severity enum;
- summary calculation;
- fail-on behavior;
- problem-to-diagnostic mapping;
- bundle missing dependency diagnostic;
- bundle ambiguous dependency diagnostic;
- JSON report contains `summary` and `diagnostics`;
- CLI `--fail-on never` returns zero for compatibility diagnostics;
- CLI `--fail-on warning` returns non-zero for warning diagnostics;
- existing simple scan/compare behavior without `--bundle-root` still works.

Expected useful test file names:

```text
tests/test_diagnostics_models.py
tests/test_diagnostics_summary.py
tests/test_quality_gates.py
tests/test_cli_diagnostics_json.py
tests/test_cli_fail_on.py
```

Adapt names to existing test layout.

### Task 11 — docs

Update `README.md` with a new section:

```markdown
## Diagnostics and CI Gates
```

Include examples:

```bash
uv run compatlab compare ./dist/my-app \
  --target ubuntu-2204 \
  --bundle-root ./dist \
  --recursive \
  --fail-on warning
```

```bash
uv run compatlab compare ./dist/my-app \
  --target-file ./profiles/prod.yaml \
  --bundle-root ./dist \
  --recursive \
  --fail-on never \
  --json report.json
```

Explain the three values:

- `error`;
- `warning`;
- `never`.

### Task 12 — release note

Create:

```text
docs/ReleaseNotes/v0.8.md
```

Template:

```markdown
# CompatLab ArtifactDoctor 0.8

Release date: 2026-06-28

## Summary

CompatLab ArtifactDoctor 0.8 adds actionable diagnostics and CI quality gates.

## Added

...

## Changed

...

## Current Behavior

...

## Not Included Yet

...

## Verification

The release was verified with:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
make check
```

Expected test result:

```text
NN passed
```

## Next Step

The next development step is to consider package artifact scanning for wheel,
RPM, or DEB files, or to add an optional HTML report once the diagnostic JSON
schema is stable.
```

Use the actual test count after running tests.

---

## 8. CLI contract for v0.8

### Existing commands that must keep working

```bash
uv run compatlab scan ./app
uv run compatlab scan ./app --json report.json
uv run compatlab compare ./app --target ubuntu-1804
uv run compatlab compare ./app --target-file ./local.yaml
uv run compatlab compare ./dist/my-app --target-file ./target.yaml --bundle-root ./dist --recursive
uv run compatlab profiles list
uv run compatlab profiles show ubuntu-1804
uv run compatlab profiles detect
uv run compatlab profiles generate --from-current --name local --output local.yaml
uv run compatlab profiles generate --from-image ubuntu:22.04 --name ubuntu-2204-docker --output ubuntu-2204.yaml
uv run compatlab profiles runtime-presets list
uv run compatlab profiles runtime-presets show cpp-runtime
uv run compatlab profiles generate --from-image ubuntu:22.04 --runtime-preset cpp-runtime --name ubuntu-2204-cpp --output ubuntu-2204-cpp.yaml
uv run compatlab profiles validate ubuntu-2204.yaml
```

### New v0.8 command examples

```bash
uv run compatlab compare ./dist/my-app \
  --target-file /tmp/ubuntu-2204-cpp-runtime.yaml \
  --bundle-root ./dist \
  --recursive \
  --fail-on error
```

```bash
uv run compatlab compare ./dist/my-app \
  --target ubuntu-2204 \
  --bundle-root ./dist \
  --recursive \
  --fail-on warning \
  --json report.json
```

```bash
uv run compatlab scan ./dist/my-app \
  --bundle-root ./dist \
  --recursive \
  --fail-on never \
  --json scan-report.json
```

---

## 9. JSON contract for v0.8

v0.8 should add fields, not radically rewrite report JSON.

Minimum expected shape:

```json
{
  "summary": {
    "status": "failed",
    "errors": 1,
    "warnings": 1,
    "infos": 0,
    "issue_codes": {
      "CL_LIB_MISSING": 1,
      "CL_RPATH_ABSOLUTE": 1
    }
  },
  "diagnostics": [
    {
      "code": "CL_LIB_MISSING",
      "severity": "error",
      "category": "bundle",
      "title": "Missing shared library",
      "message": "libssl.so.3 is required but was not found in the bundle or target profile.",
      "affected_path": "dist/lib/libfoo.so",
      "dependency_name": "libssl.so.3",
      "dependency_chain": [
        "dist/my-app",
        "dist/lib/libfoo.so",
        "libssl.so.3"
      ],
      "required": "libssl.so.3",
      "provided": null,
      "hint": "Install the runtime library on the target image or include a compatible libssl.so.3 in the bundle."
    }
  ],
  "dependency_graph": {}
}
```

---

## 10. Non-goals for v0.8

Do not implement:

- wheel scanning;
- RPM scanning;
- DEB scanning;
- SBOM generation;
- vulnerability scanning;
- automatic patching through `patchelf`;
- artifact execution inside containers;
- Docker image mutation, commit, save, or push;
- arbitrary package installation;
- general package manager frontend;
- full dynamic linker emulation;
- web interface;
- database;
- daemon/server mode;
- Go helper implementation.

HTML report generation is also not part of the primary v0.8 scope. It may be considered only if the diagnostic model, JSON, CLI quality gates, tests, README, and release note are complete.

---

## 11. Agent-specific implementation rules

The Codex agent should follow these rules:

1. **Inspect before editing.** Do not assume file/module names.
2. **Preserve existing public CLI behavior.** New flags must be additive.
3. **Prefer pure functions for diagnostic mapping, summary calculation, and quality gate decisions.** They are easier to test.
4. **Do not introduce external services or network requirements.**
5. **Do not require Docker for tests unless the existing test suite already does.** Use mocks/fixtures.
6. **Keep fixtures small.** Avoid large binary files. Reuse existing fixture strategy.
7. **Use existing project style.** Follow current Pydantic, Typer, Rich, pytest, and ruff patterns.
8. **Do not silently swallow scanner errors.** Convert expected scan/resolve problems into diagnostics, but let internal bugs fail loudly.
9. **Keep JSON deterministic.** Stable ordering is important for tests and CI.
10. **Run all checks before final response.**

---

## 12. Recommended implementation order

1. Inspect project tree and existing models.
2. Add diagnostic model and summary model.
3. Add unit tests for model serialization and summary calculation.
4. Add quality gate enum/function and tests.
5. Map existing compare problems to diagnostics.
6. Map v0.7 bundle resolver outcomes to diagnostics.
7. Add `summary` and `diagnostics` to JSON output.
8. Add `--fail-on` CLI option to `scan` and `compare`.
9. Update Rich output with a compact diagnostics section.
10. Add CLI tests for JSON and exit codes.
11. Update README.
12. Add `docs/ReleaseNotes/v0.8.md`.
13. Run full verification.

---

## 13. Acceptance criteria

v0.8 is complete when all criteria are satisfied:

- `scan` and `compare` expose `--fail-on error|warning|never`.
- JSON reports include `summary` and `diagnostics`.
- Diagnostic issues have stable `code`, `severity`, `category`, `title`, and `message` fields.
- Missing library diagnostics include affected path and dependency name.
- Bundle diagnostics include dependency chain where possible.
- Too-new symbol diagnostics identify required and provided versions where possible.
- Rich output contains a compact diagnostics section.
- `--fail-on never` returns zero for compatibility diagnostics when the command itself succeeds.
- `--fail-on warning` returns non-zero when warning diagnostics exist.
- Existing v0.7 bundle resolution behavior remains intact.
- Existing commands without v0.8 flags remain compatible.
- README documents diagnostics and CI gates.
- `docs/ReleaseNotes/v0.8.md` exists and uses the real test count.
- Verification passes:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
make check
```

---

## 14. Example final user-facing behavior

Command:

```bash
uv run compatlab compare ./dist/my-app \
  --target-file ./profiles/ubuntu-2204-cpp-runtime.yaml \
  --bundle-root ./dist \
  --recursive \
  --fail-on warning \
  --json report.json
```

Expected terminal output should include something conceptually similar to:

```text
Dependency Resolution
  libfoo.so      bundled   dist/lib/libfoo.so
  libssl.so.3    missing   -

Diagnostics
  ERROR   CL_LIB_MISSING          libssl.so.3 is missing
  WARNING CL_RPATH_ABSOLUTE       absolute RUNPATH entry found

Summary
  Status: failed
  Errors: 1
  Warnings: 1
```

Expected exit behavior:

- with `--fail-on error`: non-zero because there is an error;
- with `--fail-on warning`: non-zero because there is a warning/error;
- with `--fail-on never`: zero if report generation succeeded.

---

## 15. Suggested next step after v0.8

After v0.8, good candidates for v0.9 are:

1. package artifact scanning for Python wheels;
2. package artifact scanning for RPM/DEB;
3. optional HTML report generated from the stable v0.8 JSON schema;
4. Alpine/musl compatibility modeling;
5. container-based artifact execution smoke checks.

Do not start these in v0.8.
