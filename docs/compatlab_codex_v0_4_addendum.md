# CompatLab ArtifactDoctor v0.4 — Additional Codex Specification

This document is an addendum to the main Codex handoff for CompatLab ArtifactDoctor v0.4.

It describes optional but strongly recommended improvements that may be implemented in v0.4 **after** the core profile auto-detection pipeline is working.

The main v0.4 goal remains unchanged:

> Generate a valid YAML target profile from the current Linux system using detected system facts.

Do not expand v0.4 into Docker image scanning, rootfs scanning, recursive dependency resolution, package analysis, or runtime package installation. Those belong to v0.5+.

---

## 1. Recommended v0.4 Additions

Implement these only after the base v0.4 flow is green:

```bash
uv run compatlab profiles detect
uv run compatlab profiles detect --json /tmp/system-facts.json
uv run compatlab profiles generate --from-current --name local --output /tmp/local.yaml
```

Recommended additions:

1. `compatlab compare PATH --target-file PROFILE.yaml`
2. `compatlab profiles validate PROFILE.yaml`
3. JSON export for raw `SystemFacts`
4. Metadata in generated YAML profiles

These additions make v0.4 much more practical without changing the release theme.

---

## 2. Add `compare --target-file`

### Goal

Allow users to compare an artifact against an external YAML profile file, not only against built-in profile names.

Current expected flow after v0.4:

```bash
uv run compatlab profiles generate --from-current --name local --output /tmp/local.yaml
uv run compatlab compare /bin/bash --target-file /tmp/local.yaml
```

### CLI behavior

Add an optional argument to `compatlab compare`:

```bash
compatlab compare PATH --target TARGET
compatlab compare PATH --target-file PROFILE.yaml
```

Rules:

- `--target` keeps existing behavior and loads a built-in profile by name.
- `--target-file` loads a profile from the given YAML path.
- User must provide exactly one of:
  - `--target`
  - `--target-file`
- If both are provided, return a clear CLI error.
- If neither is provided, return a clear CLI error.
- If the file does not exist, return exit code `2`.
- If the file exists but is invalid, return exit code `2`.
- Existing compare exit-code semantics must remain unchanged:
  - `0` when no `HIGH` or `CRITICAL` compatibility problems are found;
  - `1` when a `HIGH` or `CRITICAL` compatibility problem is found;
  - `2` when profile/artifact scanning fails.

### Implementation notes

Prefer reusing the existing profile loading and validation path.

Do not duplicate YAML parsing logic inside the CLI command. Add a reusable function if needed, for example:

```python
load_builtin_profile(name: str) -> TargetProfile
load_profile_file(path: Path) -> TargetProfile
```

or one generalized loader if the current project structure supports it.

### Tests

Add tests for:

- compare using a valid external profile file;
- compare with missing external profile file;
- compare with invalid YAML/profile content;
- compare with both `--target` and `--target-file`;
- compare with neither `--target` nor `--target-file`;
- existing `--target` behavior remains unchanged.

---

## 3. Add `profiles validate`

### Goal

Allow users and CI to check whether a YAML target profile is valid before using it in `compare`.

Expected command:

```bash
compatlab profiles validate ./local.yaml
```

Optional JSON output may be added if the existing CLI/report style makes it easy:

```bash
compatlab profiles validate ./local.yaml --json /tmp/validation.json
```

### CLI behavior

For a valid profile:

```text
Profile: ./local.yaml
Status: valid
Target: local
Architecture: x86_64
```

For an invalid profile:

```text
Profile: ./broken.yaml
Status: invalid
Error: <clear validation message>
```

Exit codes:

- `0` for a valid profile;
- `2` for missing file, invalid YAML, or validation failure.

### Implementation notes

Validation must use the same `TargetProfile` model used by `compare`.

Do not create a separate schema that can diverge from the actual runtime model.

### Tests

Add tests for:

- valid generated-like profile;
- missing file;
- malformed YAML;
- YAML with missing required fields;
- YAML with wrong field types.

---

## 4. JSON Export for Raw `SystemFacts`

### Goal

Make system detection debuggable.

Expected command:

```bash
compatlab profiles detect --json /tmp/system-facts.json
```

The JSON file should contain raw facts, not a normalized target profile.

This is useful because generated profiles may hide details that were present during detection.

### Expected content

The exact schema depends on the implemented `SystemFacts` model, but it should include at least:

```json
{
  "os_release": {
    "id": "ubuntu",
    "version_id": "24.04",
    "pretty_name": "Ubuntu 24.04 LTS"
  },
  "architecture": "x86_64",
  "glibc_version": "2.39",
  "dynamic_linkers": [
    "/lib64/ld-linux-x86-64.so.2"
  ],
  "libraries": [
    {
      "soname": "libc.so.6",
      "path": "/lib/x86_64-linux-gnu/libc.so.6"
    }
  ],
  "symbol_versions": {
    "glibc": ["2.2.5", "2.17", "2.34", "2.39"],
    "glibcxx": ["3.4", "3.4.29", "3.4.33"],
    "cxxabi": ["1.3", "1.3.13", "1.3.15"]
  },
  "warnings": []
}
```

### Tests

Add tests for:

- `profiles detect --json` writes a valid JSON file;
- the JSON file can be loaded back;
- expected top-level keys are present;
- warnings are serialized consistently.

If live system dependent tests are needed, guard them carefully so they do not fail on CI environments lacking `ldconfig`, `ldd`, `readelf`, `/bin/bash`, or `libstdc++.so.6`.

Prefer parser and generator tests based on fixtures.

---

## 5. Metadata in Generated YAML Profiles

### Goal

Generated profiles should explain where they came from.

This helps users distinguish manually maintained built-in profiles from profiles generated from a host.

### Suggested metadata block

Add optional metadata to `TargetProfile` if the model can support it cleanly:

```yaml
metadata:
  generated_by: compatlab
  generated_at: "2026-06-28T15:30:00Z"
  source: current-system
  source_os_id: ubuntu
  source_os_version_id: "24.04"
  detection_backend: local-system
```

Rules:

- Do not make metadata required for built-in profiles unless all existing profiles are updated.
- Metadata should be optional.
- Generated profiles should include metadata by default.
- `generated_at` should use ISO 8601 format.
- Avoid non-deterministic timestamps in unit tests unless injected/mocked.

### Tests

Add tests for:

- generated profile includes metadata;
- built-in profiles still load if metadata is absent;
- metadata does not affect compatibility comparison logic.

---

## 6. Recommended Development Order

Follow this order to avoid over-expanding the release:

1. Ensure base v0.4 detection/generation is implemented and tested.
2. Add `profiles detect --json` if not already present.
3. Add `profiles validate PROFILE.yaml`.
4. Add `compare --target-file PROFILE.yaml`.
5. Add optional metadata to generated YAML profiles.
6. Update README and release notes.
7. Run full checks.

Do not start Docker work until the above is complete and stable.

---

## 7. Acceptance Criteria

v0.4 can be considered complete when the following commands work:

```bash
uv run compatlab profiles detect
uv run compatlab profiles detect --json /tmp/system-facts.json
uv run compatlab profiles generate --from-current --name local --output /tmp/local.yaml
uv run compatlab profiles validate /tmp/local.yaml
uv run compatlab compare /bin/bash --target-file /tmp/local.yaml
uv run pytest
uv run ruff check .
uv run ruff format --check .
make check
```

The generated profile should be usable immediately by `compare`.

---

## 8. Explicitly Out of Scope for v0.4

Do not implement in v0.4:

- `profiles generate --from-image IMAGE`
- Docker image execution
- Dockerfile or runtime agent installation
- rootfs scanning
- container scanning
- recursive dependency resolution
- automatic installation of common runtime packages
- wheel/RPM/DEB scanning
- SBOM generation
- security scanning
- automatic binary patching
- web UI
- database
- daemon/server mode

These are candidates for v0.5+.

---

## 9. Suggested Commit Breakdown

Use small commits. Suggested sequence:

1. `Add profile file loader`
2. `Add profiles validate command`
3. `Add target-file support to compare`
4. `Add system facts JSON output`
5. `Add metadata to generated profiles`
6. `Update README and v0.4 release notes`

Each commit should keep tests green.

---

## 10. Final Reminder for Codex

Do not rewrite the whole project.

Preserve the existing design:

- Typer CLI
- Rich terminal output
- Pydantic models
- YAML target profiles
- readelf-based ELF scanner
- compatibility engine from v0.3
- pytest + Ruff + Makefile workflow

v0.4 should feel like a natural continuation of v0.1-v0.3, not a new application.
