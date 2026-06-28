# CompatLab ArtifactDoctor — Codex Handoff

Дата подготовки: 2026-06-28

Этот файл предназначен для передачи контекста агенту разработки Codex. Его задача — помочь начать новый проект с чистого листа и не потерять продуктовый фокус.

Главная правка относительно ранних обсуждений: **основной язык проекта — Python**. Go можно использовать позже и только по необходимости: для ускоренного ELF/rootfs-сканера, отдельного статического helper-бинарника или узких системных задач. Первый MVP должен быть Python-first.

---

## 1. Короткая суть проекта

**CompatLab ArtifactDoctor** — CLI-first инструмент для preflight-проверки совместимости Linux-бинарных артефактов с целевой Linux-системой.

Первый MVP отвечает на вопрос:

> Запустится ли этот ELF-бинарник или shared library на целевой ОС, и если нет — почему?

Инструмент анализирует ELF-метаданные, динамические зависимости, interpreter, RPATH/RUNPATH, требуемые версии `GLIBC_*`, `GLIBCXX_*`, `CXXABI_*`, сравнивает их с target profile и выдаёт понятный диагноз.

Ключевой принцип:

> `readelf` показывает факты. CompatLab ставит диагноз.

---

## 2. Главная боль

В корпоративной Linux-разработке часто возникает ситуация:

> На машине разработчика работает, в CI собирается, но на целевом корпоративном Linux не запускается.

Причины обычно низкоуровневые:

- нужна более новая `glibc`;
- нужна более новая `libstdc++` / `GLIBCXX_*`;
- не хватает shared library;
- бинарник собран под неправильную архитектуру;
- используется неподходящий dynamic linker / interpreter;
- в бинарнике прописан плохой `RPATH` или `RUNPATH`;
- wheel содержит `.so`, которые несовместимы с целевой ОС;
- RPM/DEB не объявляет реальные runtime-зависимости;
- контейнерный образ работает случайно из-за библиотеки, которая не будет доступна в поставке.

Сегодня инженер вручную использует:

```bash
ldd ./app
readelf -d ./app
readelf --version-info ./app
objdump -p ./app
patchelf --print-rpath ./app
strace ./app
```

Эти инструменты мощные, но разрозненные и не дают объясняемый продуктовый отчёт.

CompatLab должен превращать низкоуровневую диагностику в понятный preflight report.

---

## 3. Первый пользователь

Первый пользователь — **инженер сборки и поставки корпоративного Linux-ПО**.

Портрет:

- собирает бинарники, Python-приложения, wheels, RPM/DEB или standalone-сборки;
- поставляет артефакты на Astra Linux, SberLinux, Rocky Linux, Ubuntu, Debian или другую корпоративную ОС;
- сталкивается с ошибками вида `GLIBC_2.xx not found`, `GLIBCXX_3.4.xx not found`, `No such file or directory`, `cannot open shared object file`;
- умеет пользоваться `readelf`, `ldd`, `objdump`, но не хочет каждый раз собирать диагноз вручную;
- хочет встроить проверку в CI до поставки заказчику.

Формула пользователя:

> Я инженер, который собирает и поставляет Linux-приложение в закрытую корпоративную среду. Мне нужно заранее понять, запустится ли мой артефакт на целевой ОС, и если нет — получить понятную причину.

---

## 4. Позиционирование

Полная формулировка:

> CompatLab ArtifactDoctor — Python-first CLI-инструмент для проверки совместимости Linux-бинарников с целевой ОС перед поставкой. Он анализирует ELF-метаданные, динамические зависимости, требуемые версии GLIBC/GLIBCXX/CXXABI, interpreter, RPATH/RUNPATH и сравнивает их с профилем целевой системы. Вместо сырого вывода `readelf` он объясняет, что сломается, почему это важно и как это исправить.

Короткая формулировка:

> CompatLab показывает, почему Linux-бинарник не доедет до целевой ОС.

README tagline:

> Preflight compatibility checker for Linux binary artifacts.

---

## 5. Главный продуктовый фокус MVP

Не делать сразу платформу обо всём.

Первый MVP:

> Один ELF-файл + один target profile + понятный compatibility report.

Входит:

- CLI;
- анализ одного ELF-файла;
- JSON report;
- pretty terminal output;
- target profiles в YAML;
- сравнение с профилем целевой ОС;
- problem taxonomy;
- exit codes для CI;
- тесты.

Не входит в первый MVP:

- web UI;
- база данных;
- daemon/agent;
- auth/users/teams;
- wheel analysis;
- RPM/DEB analysis;
- container image scan;
- Kubernetes;
- SBOM/security scan;
- автоматическое исправление через `patchelf`;
- полноценный dynamic linker resolver;
- rootfs scan.

---

## 6. Почему Python-first

Основной язык проекта — Python.

Причины:

- пользователь сильнее всего работает с Python;
- быстрее собрать CLI и продуктовый MVP;
- проще писать понятную бизнес-логику диагностики;
- удобно работать с JSON/YAML/HTML reports;
- удобно писать тесты и golden tests;
- проект хорошо ложится в профиль Python system/backend developer;
- Python позволяет быстро развивать поддержку wheels, packaging metadata, RPM/DEB wrappers;
- низкоуровневые места можно позже вынести в Go/Rust/C extension/helper-binary.

Go не исключается, но не является языком первого MVP.

Go можно использовать позже для:

- быстрого сканера rootfs/container image;
- standalone helper-бинарника без Python runtime;
- performance-sensitive ELF traversal;
- agent mode;
- экспериментов с безопасным parallel scanning.

Принцип:

> Python — основной продуктовый слой. Go — optional helper там, где он действительно нужен.

---

## 7. Рекомендуемый Python-стек

Минимальный и практичный стек:

- Python 3.12+;
- `uv` для окружения, зависимостей и запуска команд;
- `typer` для CLI;
- `rich` для красивого terminal output;
- `pydantic` для моделей отчёта и target profiles;
- `pyyaml` для YAML profiles;
- `pytest` для тестов;
- `ruff` для lint/format;
- `mypy` опционально, лучше включить не сразу, а после стабилизации моделей.

Для ELF parsing на старте:

- использовать системные инструменты `readelf`, `objdump`, `file` через subprocess;
- парсить их вывод аккуратно и покрывать тестами;
- позже добавить native parser через `pyelftools`, если это даст пользу.

Почему не сразу `pyelftools`:

- MVP должен быстрее дать ценность;
- `readelf` уже установлен почти везде вместе с binutils;
- вывод `readelf` легко сравнивать вручную;
- продуктовая ценность не в том, что мы сами читаем байты ELF, а в том, что мы объясняем совместимость.

Однако архитектуру нужно сделать так, чтобы источник ELF-данных можно было заменить:

```text
ElfBackend protocol/interface
  ├── ReadelfBackend
  └── PyElfToolsBackend later
```

---

## 8. CLI MVP

Основной CLI: `compatlab`.

Команды первого MVP:

```bash
compatlab scan ./app
compatlab scan ./app --json report.json
compatlab compare ./app --target ubuntu-1804
compatlab compare ./app --target ./profiles/custom.yml
compatlab compare ./app --target ubuntu-1804 --json report.json
compatlab profiles list
compatlab profiles show ubuntu-1804
```

Exit codes:

```text
0 — compatible / no HIGH or CRITICAL problems
1 — compatibility problems found
2 — scan or internal error
```

Пример expected output:

```text
Artifact: ./demo-app
Type: ELF64 executable
Machine: x86_64
Interpreter: /lib64/ld-linux-x86-64.so.2

Needed libraries:
  - libc.so.6

Required symbol versions:
  - GLIBC_2.2.5
  - GLIBC_2.34

Compatibility: FAIL
Target: Ubuntu 18.04

HIGH glibc.too_new
Binary requires GLIBC_2.34, but target provides GLIBC_2.27.

Suggested fix:
  - Rebuild on an older baseline distribution
  - Use a target-compatible build container
  - Avoid APIs introduced after GLIBC_2.27
```

---

## 9. Target profiles

Профили целевых ОС хранятся в YAML.

Минимальная модель:

```yaml
id: ubuntu-1804
name: Ubuntu 18.04
arch: x86_64
libc:
  family: glibc
  version: "2.27"
libstdcxx:
  max_glibcxx: "3.4.25"
  max_cxxabi: "1.3.11"
interpreters:
  - /lib64/ld-linux-x86-64.so.2
  - /lib/x86_64-linux-gnu/ld-linux-x86-64.so.2
provided_libraries:
  - soname: libc.so.6
  - soname: libstdc++.so.6
  - soname: libgcc_s.so.1
  - soname: libm.so.6
  - soname: libpthread.so.0
  - soname: libdl.so.2
```

Профили первого MVP:

- `ubuntu-1804.yml`;
- `ubuntu-2004.yml`;
- `ubuntu-2204.yml`;
- `ubuntu-2404.yml`;
- `rocky-9.yml`;
- `astra-17.yml` placeholder;
- `sberlinux-9.yml` placeholder.

Важно: профили могут быть приблизительными на старте. В отчёте нужно честно писать, что compatibility check зависит от точности target profile.

---

## 10. Problem taxonomy

Основные problem IDs первого MVP:

```text
wrong.architecture
missing.interpreter
profile.interpreter_not_provided
missing.library
profile.library_not_provided
glibc.too_new
glibcxx.too_new
cxxabi.too_new
bad.rpath.absolute
bad.rpath.build_path
bad.runpath.absolute
bad.runpath.build_path
unsupported.elf
scan.failed
```

Severity:

```text
CRITICAL — артефакт почти точно не запустится
HIGH     — высокая вероятность runtime failure
MEDIUM   — потенциальная проблема переносимости
LOW      — подозрительная практика
INFO     — диагностическая заметка
```

---

## 11. Основная модель данных

Python-модели можно реализовать через Pydantic.

Пример структуры:

```python
class ArtifactInfo(BaseModel):
    path: str
    kind: str
    size_bytes: int | None = None
    sha256: str | None = None

class SymbolVersion(BaseModel):
    namespace: str
    version: str
    raw: str

class ElfInfo(BaseModel):
    elf_class: str | None = None
    machine: str | None = None
    elf_type: str | None = None
    interpreter: str | None = None
    is_dynamic: bool | None = None
    needed: list[str] = []
    rpath: list[str] = []
    runpath: list[str] = []
    required_versions: list[SymbolVersion] = []

class Problem(BaseModel):
    id: str
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
    title: str
    details: str
    artifact_path: str | None = None
    evidence: dict[str, str] = {}
    suggestions: list[str] = []

class ArtifactReport(BaseModel):
    schema_version: str = "0.1"
    tool: str = "compatlab"
    artifact: ArtifactInfo
    elf: ElfInfo | None = None
    target: TargetProfile | None = None
    problems: list[Problem] = []
    warnings: list[Problem] = []
```

---

## 12. Рекомендуемая структура репозитория

```text
compatlab/
├── pyproject.toml
├── README.md
├── README.ru.md
├── Makefile
├── .gitignore
├── src/
│   └── compatlab/
│       ├── __init__.py
│       ├── cli.py
│       ├── artifact/
│       │   ├── __init__.py
│       │   ├── detect.py
│       │   └── hash.py
│       ├── elfscan/
│       │   ├── __init__.py
│       │   ├── models.py
│       │   ├── scanner.py
│       │   ├── readelf_backend.py
│       │   ├── parsers.py
│       │   └── versions.py
│       ├── profile/
│       │   ├── __init__.py
│       │   ├── models.py
│       │   ├── loader.py
│       │   └── builtin.py
│       ├── compare/
│       │   ├── __init__.py
│       │   ├── engine.py
│       │   ├── glibc.py
│       │   ├── libstdcxx.py
│       │   ├── libraries.py
│       │   └── rpath.py
│       ├── problem/
│       │   ├── __init__.py
│       │   ├── models.py
│       │   └── taxonomy.py
│       └── report/
│           ├── __init__.py
│           ├── models.py
│           ├── json.py
│           └── pretty.py
├── profiles/
│   ├── ubuntu-1804.yml
│   ├── ubuntu-2004.yml
│   ├── ubuntu-2204.yml
│   ├── ubuntu-2404.yml
│   ├── rocky-9.yml
│   ├── astra-17.yml
│   └── sberlinux-9.yml
├── tests/
│   ├── test_cli.py
│   ├── test_readelf_parsers.py
│   ├── test_compare_versions.py
│   ├── test_profiles.py
│   └── fixtures/
│       ├── readelf/
│       └── elf/
├── testdata/
│   └── elf/
├── examples/
│   └── demo-c/
├── docs/
│   ├── pitch.md
│   ├── architecture.md
│   ├── demo.md
│   └── compatibility-model.md
└── scripts/
    └── build-demo-binaries.sh
```

---

## 13. Архитектурный поток

```text
CLI args
  ↓
Artifact detector
  ↓
ELF scanner
  ↓
ArtifactReport
  ↓
Target profile loader
  ↓
Compatibility engine
  ↓
Problems + suggestions
  ↓
Pretty output / JSON output
```

Важное разделение:

- `elfscan` только извлекает факты;
- `compare` принимает решения;
- `report` только отображает результат;
- `profile` отвечает только за загрузку target profiles;
- CLI не должен содержать бизнес-логику.

---

## 14. Реализация ELF scan на первом этапе

На первом этапе можно использовать subprocess wrapper над `readelf`.

Команды:

```bash
readelf -h ./app
readelf -l ./app
readelf -d ./app
readelf --version-info ./app
```

Что извлекать:

- ELF class;
- machine;
- type;
- interpreter из program headers;
- `NEEDED` из dynamic section;
- `RPATH`;
- `RUNPATH`;
- required symbol versions.

Парсинг должен быть устойчивым:

- если часть данных не прочиталась, не падать;
- добавлять warning/problem `scan.failed` или частичный warning;
- сохранять partial report.

---

## 15. Demo-сценарий MVP

Цель demo:

> Показать, что бинарник, собранный на новой системе, требует более новую glibc и не совместим со старым target profile.

Шаги:

1. Собрать маленький C-бинарник на Ubuntu 24.04.
2. Просканировать:

```bash
compatlab scan ./demo-app
```

3. Увидеть required versions:

```text
GLIBC_2.2.5
GLIBC_2.34
GLIBC_2.38
```

4. Сравнить с Ubuntu 18.04:

```bash
compatlab compare ./demo-app --target ubuntu-1804
```

5. Получить проблему:

```text
HIGH glibc.too_new
Binary requires GLIBC_2.38, but target Ubuntu 18.04 provides GLIBC_2.27.
```

6. Проверить exit code:

```bash
compatlab compare ./demo-app --target ubuntu-1804
echo $?
```

Ожидается:

```text
1
```

7. Получить JSON:

```bash
compatlab compare ./demo-app --target ubuntu-1804 --json report.json
jq . report.json
```

Финальная demo-фраза:

> Теперь это можно поставить в CI и ломать сборку до того, как артефакт уедет заказчику.

---

## 16. Roadmap

### v0.1 — Python ELF Compatibility Check

- Python package skeleton;
- CLI через Typer;
- scan одного ELF;
- compare с YAML target profile;
- pretty output через Rich;
- JSON report;
- pytest tests;
- ruff;
- profiles list/show;
- demo C binary.

### v0.2 — Local Dependency Resolver

- поиск прямых `DT_NEEDED` библиотек на локальной системе;
- учёт RPATH/RUNPATH;
- `$ORIGIN`;
- dependency graph model;
- unresolved library problems.

### v0.3 — Static HTML Report

- генерация standalone HTML;
- таблица проблем;
- summary;
- простая dependency graph визуализация позже.

### v0.4 — Python Wheel Doctor

- parse wheel filename tags;
- parse WHEEL/METADATA;
- find `.so` inside wheel;
- run ELF scan for each `.so`;
- report external native dependencies;
- platform/ABI mismatch warnings.

### v0.5 — RPM/DEB Doctor

- extract metadata;
- list files;
- find ELF;
- compare declared deps vs actual ELF deps.

### v0.6 — Rootfs/Profile Generator

- scan rootfs;
- generate target profile from rootfs;
- compare artifact against actual rootfs.

### v0.7 — Optional Go helper

- only if Python performance or deployment becomes a real limitation;
- helper should produce the same JSON model;
- Python remains orchestrator and product layer.

---

## 17. Non-goals

Do not implement these in the first MVP:

- server;
- web dashboard;
- database;
- users/auth;
- Kubernetes;
- vulnerability scan;
- SBOM;
- package manager integration;
- automatic dependency installation;
- automatic binary patching;
- complex rootfs/container extraction;
- enterprise multi-tenant platform.

This project must stay sharp:

> scan -> compare -> explain -> JSON/pretty report.

---

## 18. Development rules for Codex

Codex should follow these rules:

1. Keep changes small and reviewable.
2. Do not implement future roadmap items unless explicitly asked.
3. Prefer simple, tested code over clever abstractions.
4. Keep CLI thin; business logic belongs in internal modules.
5. Use Python typing everywhere practical.
6. Use Pydantic models for stable report/profile schemas.
7. All subprocess calls must have error handling and timeouts where appropriate.
8. Tests are required for parsers and version comparison.
9. JSON output must be deterministic enough for golden tests.
10. Do not add a web server, database, Docker stack, or UI in MVP.
11. Do not silently ignore parse failures; expose warnings/problems.
12. Prefer explicit problem IDs from taxonomy.

---

## 19. First Codex task

Use this prompt as the first instruction to Codex:

```text
We are starting a new Python-first project called CompatLab ArtifactDoctor.

Build the first clean project skeleton for a CLI-first Linux artifact compatibility checker. Do not implement the full product yet.

Goal for this step:
- initialize a Python package using src-layout
- create pyproject.toml
- use Typer for CLI
- use Rich for pretty output
- use Pydantic for report/profile models
- add pytest and ruff configuration
- create CLI commands:
  - compatlab scan PATH
  - compatlab compare PATH --target TARGET
  - compatlab profiles list
  - compatlab profiles show TARGET
- commands may return stubbed structured output for now, but code structure must be ready for real implementation
- add README.md with pitch, MVP scope and non-goals
- add Makefile with test, lint, format, run-scan
- add profiles directory with a few initial YAML target profiles
- add tests for CLI smoke behavior
- run tests after implementation

Product context:
CompatLab ArtifactDoctor is a Python-first preflight checker for Linux binary artifacts. The first MVP checks one ELF binary against a target Linux profile and explains compatibility problems such as too-new glibc/libstdc++, missing interpreter, missing DT_NEEDED libraries, wrong architecture and bad RPATH/RUNPATH.

Important constraints:
- do not add web UI
- do not add database
- do not add wheel/RPM/DEB/rootfs support yet
- do not use Go in the first implementation
- keep the skeleton small and easy to extend
```

---

## 20. Second Codex task

After skeleton is ready:

```text
Implement the first real ELF scanner backend using system readelf.

Requirements:
- add ReadelfBackend that calls:
  - readelf -h PATH
  - readelf -l PATH
  - readelf -d PATH
  - readelf --version-info PATH
- parse ELF class, machine, type, interpreter, DT_NEEDED, RPATH, RUNPATH and required symbol versions
- store results in Pydantic models
- add robust error handling for missing readelf, non-ELF files and parse failures
- add pytest tests for parsers using fixture files with captured readelf output
- keep scan command functional with pretty and JSON output
- do not implement target comparison yet except preserving current stubs
```

---

## 21. Third Codex task

After scanner works:

```text
Implement target profile comparison.

Requirements:
- load profiles from built-in profiles directory or explicit YAML path
- compare artifact architecture with target arch
- compare required GLIBC_* max version with target libc.version
- compare required GLIBCXX_* with target libstdcxx.max_glibcxx
- compare required CXXABI_* with target libstdcxx.max_cxxabi
- check interpreter against target interpreters
- check direct DT_NEEDED libraries against target provided_libraries by soname
- emit Problem objects with stable IDs, severity, details, evidence and suggestions
- make compare return exit code 1 for HIGH/CRITICAL problems
- add unit tests for version comparison and problem generation
```

---

## 22. First practical milestone

The first milestone is complete when these commands work:

```bash
uv run compatlab --help
uv run compatlab profiles list
uv run compatlab scan /bin/bash
uv run compatlab scan /bin/bash --json /tmp/bash-report.json
jq . /tmp/bash-report.json
uv run compatlab compare /bin/bash --target ubuntu-1804
echo $?
uv run pytest
uv run ruff check .
```

Expected result:

- scan prints ELF facts;
- JSON report is valid;
- compare produces compatibility problems if profile is older than artifact requirements;
- tests pass;
- linter passes.

---

## 23. Main reminder

Do not let the project become an enterprise monster too early.

The first product must be small, sharp and demonstrable:

> Give CompatLab one ELF and one target Linux profile. It tells you whether the artifact is compatible, why not, and what to do next.

