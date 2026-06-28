# CompatLab ArtifactDoctor — Codex Context for v0.2 Development

Дата подготовки: 2026-06-28

Этот файл предназначен для передачи контекста Codex перед началом следующего этапа разработки CompatLab ArtifactDoctor.

Задача Codex: продолжить существующий Python-first проект, в котором уже реализован v0.1 skeleton, и довести `compatlab scan` до первого реального ELF-сканера.

---

## 1. Краткое описание проекта

**CompatLab ArtifactDoctor** — Python-first CLI-инструмент для preflight-проверки совместимости Linux-бинарников с целевой Linux-системой.

Главная продуктовая идея:

> Не просто показать сырой вывод `readelf`, а объяснить, почему Linux-артефакт может не запуститься на целевой ОС.

Первый большой продуктовый фокус:

> Проверить ELF-бинарник или shared library до поставки заказчику и заранее увидеть проблемы уровня glibc, libstdc++, dynamic linker, `DT_NEEDED`, `RPATH` и `RUNPATH`.

CompatLab не является:

- security scanner;
- SBOM generator;
- vulnerability scanner;
- package manager;
- web platform;
- daemon/service;
- Kubernetes/container security tool.

---

## 2. Текущий статус проекта

Версия **v0.1** уже реализована и залита в GitHub.

Что уже есть:

- Python-first проект со `src` layout.
- CLI на Typer.
- Pretty output на Rich.
- Pydantic-модели для отчётов, профилей и проблем.
- YAML target profiles.
- Smoke-тесты на pytest.
- Ruff configuration.
- Makefile.
- Команды:
  - `compatlab scan PATH`
  - `compatlab compare PATH --target TARGET`
  - `compatlab profiles list`
  - `compatlab profiles show TARGET`
- JSON output для `scan` и `compare`.
- Built-in target profiles:
  - `ubuntu-1804`
  - `ubuntu-2004`
  - `ubuntu-2204`
  - `ubuntu-2404`
  - `rocky-9`
  - `astra-17`
  - `sberlinux-9`

Текущий `scan` пока является заглушкой:

```bash
uv run compatlab scan /bin/bash
```

Пример текущего вывода:

```text
Artifact: /bin/bash
Type: linux-artifact
Size: 1396520 bytes
Compatibility: PASS
```

Это нужно исправить в v0.2.

---

## 3. Цель v0.2

Реализовать первый настоящий ELF scanner backend через системный `readelf`.

После v0.2 команда:

```bash
uv run compatlab scan /bin/bash
```

должна показывать реальные ELF-факты, а не stub output.

Пример желаемого вывода:

```text
Artifact: /bin/bash
Kind: ELF
Class: ELF64
Machine: x86-64
Type: DYN
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
    - GLIBC_2.34

Scan: OK
Problems: 0
Warnings: 0
```

Важно:

> `scan` не должен выводить `Compatibility: PASS`.

Причина: без target profile команда `scan` не знает, совместим артефакт или нет. Совместимость должна определяться только в `compare`.

В `scan` допустимы формулировки:

- `Scan: OK`
- `Problems: N`
- `Warnings: N`

---

## 4. Scope v0.2

### Нужно реализовать

1. Безопасный запуск системного `readelf`.
2. Парсинг `readelf -h`.
3. Парсинг `readelf -l`.
4. Парсинг `readelf -d`.
5. Парсинг `readelf --version-info`.
6. Заполнение существующих report models реальными ELF-данными.
7. Pretty output для новых данных.
8. JSON output для новых данных.
9. Unit-тесты парсеров на fixture-файлах.
10. Smoke-тест CLI.
11. Обновление README/release notes при необходимости.

### Не нужно реализовывать

Не добавлять в этот этап:

- target compatibility comparison rules;
- recursive dependency resolver;
- local filesystem library resolution;
- wheel scanner;
- RPM scanner;
- DEB scanner;
- rootfs/container scanner;
- HTML report;
- web UI;
- database;
- daemon/server mode;
- Go code;
- pyelftools;
- automatic patching через `patchelf`.

Цель v0.2 — только настоящий `scan`.

---

## 5. Recommended implementation design

Предлагаемая структура файлов может быть адаптирована под текущую структуру проекта, но общий смысл желательно сохранить.

```text
src/compatlab/
├── elfscan/
│   ├── __init__.py
│   ├── command.py
│   ├── scanner.py
│   ├── parsers.py
│   └── errors.py
├── report/
│   └── ...
├── problem/
│   └── ...
└── cli.py
```

### `command.py`

Отвечает только за безопасный запуск `readelf`.

Требования:

- использовать `subprocess.run`;
- не использовать `shell=True`;
- принимать список аргументов;
- выставить timeout;
- возвращать stdout/stderr/returncode;
- корректно обрабатывать отсутствие `readelf`;
- не смешивать парсинг и запуск команд.

Примерный интерфейс:

```python
@dataclass(frozen=True)
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str


def run_readelf(args: list[str], path: Path, timeout: float = 5.0) -> CommandResult:
    ...
```

Команды, которые понадобятся:

```bash
readelf -h /path/to/artifact
readelf -l /path/to/artifact
readelf -d /path/to/artifact
readelf --version-info /path/to/artifact
```

### `parsers.py`

Отвечает за чистый парсинг текста.

Желательно сделать функции без побочных эффектов:

```python
def parse_elf_header(output: str) -> dict:
    ...

def parse_program_headers(output: str) -> dict:
    ...

def parse_dynamic_section(output: str) -> dict:
    ...

def parse_version_info(output: str) -> list[SymbolVersion]:
    ...
```

### `scanner.py`

Оркестрирует запуск команд и сбор итоговой модели.

Примерный интерфейс:

```python
def scan_elf(path: Path) -> ArtifactReport:
    ...
```

---

## 6. Данные, которые нужно извлечь

### 6.1 `readelf -h`

Извлечь минимум:

- ELF class;
- endianness;
- OS ABI;
- ELF type;
- machine;
- entry point address.

Примеры строк:

```text
Class:                             ELF64
Data:                              2's complement, little endian
OS/ABI:                            UNIX - System V
Type:                              DYN (Position-Independent Executable file)
Machine:                           Advanced Micro Devices X86-64
Entry point address:               0x31750
```

Ожидаемые поля в модели:

```json
{
  "class": "ELF64",
  "endianness": "little",
  "os_abi": "UNIX - System V",
  "type": "DYN",
  "machine": "Advanced Micro Devices X86-64",
  "entry_point": "0x31750"
}
```

### 6.2 `readelf -l`

Извлечь interpreter.

Пример строки:

```text
[Requesting program interpreter: /lib64/ld-linux-x86-64.so.2]
```

Ожидаемое поле:

```json
{
  "interpreter": "/lib64/ld-linux-x86-64.so.2"
}
```

Если interpreter не найден, это не обязательно ошибка. Для `.so` его может не быть.

### 6.3 `readelf -d`

Извлечь:

- `DT_NEEDED`;
- `RPATH`;
- `RUNPATH`.

Примеры строк:

```text
0x0000000000000001 (NEEDED)             Shared library: [libc.so.6]
0x000000000000001d (RUNPATH)            Library runpath: [$ORIGIN/../lib]
0x000000000000000f (RPATH)              Library rpath: [/opt/vendor/lib]
```

Ожидаемые поля:

```json
{
  "needed": ["libc.so.6"],
  "rpath": ["/opt/vendor/lib"],
  "runpath": ["$ORIGIN/../lib"]
}
```

Если dynamic section отсутствует, артефакт может быть static или не ELF dynamic object. Это должно быть отражено как warning/info, но не обязательно как crash.

### 6.4 `readelf --version-info`

Извлечь уникальные версии символов:

- `GLIBC_*`;
- `GLIBCXX_*`;
- `CXXABI_*`.

Минимальный подход для v0.2:

- пройти по тексту регулярками;
- собрать уникальные значения;
- отсортировать;
- нормализовать namespace/version/raw.

Примеры:

```text
GLIBC_2.2.5
GLIBC_2.34
GLIBCXX_3.4.29
CXXABI_1.3
```

Ожидаемые объекты:

```json
[
  {"namespace": "GLIBC", "version": "2.2.5", "raw": "GLIBC_2.2.5"},
  {"namespace": "GLIBC", "version": "2.34", "raw": "GLIBC_2.34"},
  {"namespace": "GLIBCXX", "version": "3.4.29", "raw": "GLIBCXX_3.4.29"},
  {"namespace": "CXXABI", "version": "1.3", "raw": "CXXABI_1.3"}
]
```

Не нужно пока идеально реализовывать ELF symbol versioning. Regex-based extraction достаточно для v0.2.

---

## 7. Problem/warning behavior

v0.2 пока не делает полноценный compatibility diagnosis.

Но scanner должен быть устойчивым:

### Возможные warnings

- `readelf` command failed;
- `readelf` not found;
- artifact is not an ELF file;
- dynamic section not found;
- version info not found;
- interpreter not found for executable;
- partial report produced.

### Не надо делать в v0.2

Не создавать `glibc.too_new` и похожие проблемы. Это задача `compare`, а не `scan`.

---

## 8. Test strategy

Тесты не должны жёстко зависеть от конкретного вывода `/bin/bash` на конкретной машине.

### Unit tests

Создать fixture-файлы:

```text
tests/fixtures/readelf/header_bash.txt
tests/fixtures/readelf/program_headers_bash.txt
tests/fixtures/readelf/dynamic_bash.txt
tests/fixtures/readelf/version_info_bash.txt
```

Тестировать парсеры на этих фикстурах:

```text
tests/test_readelf_header_parser.py
tests/test_readelf_program_headers_parser.py
tests/test_readelf_dynamic_parser.py
tests/test_readelf_versions_parser.py
```

Проверять:

- class parsed correctly;
- machine parsed correctly;
- type parsed correctly;
- interpreter parsed correctly;
- needed libraries parsed correctly;
- rpath/runpath parsed correctly;
- symbol versions parsed and deduplicated correctly.

### CLI smoke test

Можно использовать `/bin/bash`, но мягко:

- пропускать тест, если `/bin/bash` отсутствует;
- не проверять точные версии glibc;
- проверять, что команда завершилась успешно;
- проверять, что вывод содержит `Artifact`;
- проверять, что вывод содержит хотя бы `ELF` или реальные ELF-поля.

### JSON smoke test

Проверить, что:

```bash
uv run compatlab scan /bin/bash --json /tmp/bash-report.json
jq . /tmp/bash-report.json
```

создаёт валидный JSON.

---

## 9. Acceptance criteria

Перед завершением задачи Codex должен проверить:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run compatlab scan /bin/bash
uv run compatlab scan /bin/bash --json /tmp/bash-report.json
jq . /tmp/bash-report.json
```

Ожидаемый результат:

1. Tests pass.
2. Ruff pass.
3. `scan /bin/bash` показывает реальные ELF metadata.
4. JSON report содержит реальные ELF metadata.
5. `scan` больше не выводит `Compatibility: PASS`.
6. `compare` пока может оставаться stub/partial behavior, но не должен ломаться.
7. Public CLI shape должна остаться совместимой:
   - `compatlab scan PATH`
   - `compatlab compare PATH --target TARGET`
   - `compatlab profiles list`
   - `compatlab profiles show TARGET`

---

## 10. Suggested Codex task prompt

Можно использовать этот prompt напрямую:

```text
We continue the Python-first CompatLab ArtifactDoctor project.

Current state:
- v0.1 project skeleton is implemented and pushed to GitHub.
- CLI commands exist:
  - compatlab scan PATH
  - compatlab compare PATH --target TARGET
  - compatlab profiles list
  - compatlab profiles show TARGET
- Reports and profiles use Pydantic models.
- Pretty output uses Rich.
- Tests and Ruff are configured.
- Current scan output is still a stub and prints placeholder compatibility status.

Goal for this step:
Implement v0.2: the first real ELF scanner backend using the system `readelf`.

Scope:
- Implement real scan support for one ELF binary or shared library.
- Use system `readelf`, not pyelftools yet.
- Do not implement target compatibility comparison yet.
- Do not implement dependency resolution yet.
- Do not add wheel/RPM/DEB/rootfs support.
- Do not add UI, database, server, daemon, or Go code.

Required behavior:
`compatlab scan /bin/bash` should extract and display real ELF facts:
- ELF class
- endianness if available
- OS ABI if available
- machine/architecture
- ELF type
- entry point if available
- whether the artifact is dynamic
- program interpreter from PT_INTERP
- DT_NEEDED libraries
- RPATH
- RUNPATH
- required symbol versions for at least:
  - GLIBC_*
  - GLIBCXX_*
  - CXXABI_*

Important output correction:
`scan` must not print `Compatibility: PASS`.
Without a target profile, scan cannot know compatibility.
Change scan output to something like:
- `Scan: OK`
- `Problems: N`
- `Warnings: N`

Implementation suggestions:
- Add a safe command runner around `subprocess.run`.
- Do not use `shell=True`.
- Add a timeout.
- If one readelf command fails, return a partial report with warnings where possible.
- Add parser functions for:
  - `readelf -h`
  - `readelf -l`
  - `readelf -d`
  - `readelf --version-info`

Testing:
- Prefer parser unit tests using fixture text files under `tests/fixtures/readelf/`.
- Do not make unit tests depend on exact `/bin/bash` output from the host system.
- A smoke test may use `/bin/bash`, but it should only check broad behavior.
- Keep `uv run pytest` and `uv run ruff check .` passing.

Acceptance criteria:
- `uv run compatlab scan /bin/bash` shows real ELF metadata.
- `uv run compatlab scan /bin/bash --json /tmp/bash-report.json` writes real ELF metadata.
- `jq . /tmp/bash-report.json` works.
- `uv run pytest` passes.
- `uv run ruff check .` passes.
```

---

## 11. Development philosophy

Keep this step small.

Do not try to implement the entire product.

Current desired sequence:

1. v0.1 — project skeleton. Done.
2. v0.2 — real ELF scan. Current task.
3. v0.3 — first target comparison rules:
   - architecture;
   - interpreter;
   - GLIBC max version;
   - GLIBCXX max version;
   - CXXABI max version.
4. v0.4 — local dependency resolver.
5. v0.5 — static HTML report.
6. v0.6 — wheel analysis.

For now, build the x-ray. Diagnosis comes next.
