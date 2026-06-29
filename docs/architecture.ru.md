# Архитектура CompatLab

Этот документ фиксирует текущие зоны ответственности модулей и целевые границы
для следующих шагов рефакторинга.

## Текущее состояние

### CLI и оркестрация

CLI-логика находится в `compatlab/src/cli.py`.

Модуль отвечает за регистрацию Typer-команд, разбор опций, вывод через Rich,
пользовательские ошибки и решения по exit code. Сейчас он также напрямую
оркестрирует несколько workflow:

- `scan`: вызывает ELF-сканирование, опциональный bundle resolver, обогащение
  diagnostics, запись JSON/HTML, терминальный вывод и обработку `--fail-on`.
- `compare`: загружает target profile, сканирует артефакт, опционально
  резолвит bundle-зависимости, вызывает compare engine для entrypoint и
  bundled libraries, строит bundle dependency problems, обогащает diagnostics,
  пишет отчеты, рендерит терминальный вывод и применяет `--fail-on`.
- `profiles`: обнаруживает, генерирует и валидирует профили из текущей системы
  или Docker images.

Поэтому `cli.py` сейчас является крупнейшей точкой связанности. Он импортирует
scanner, bundle resolver, compare engine, diagnostics, profile loaders/generators
и report writers.

### ELF-сканирование

ELF-сканирование находится в `compatlab/src/elfscan/`.

- `scanner.py` предоставляет `scan_path(path)` и строит `ArtifactReport`.
- `command.py` содержит общий runner внешних команд и `run_readelf`.
- `parsers.py` парсит вывод `readelf`: headers, program headers, dynamic section
  и требования к symbol versions.
- `models.py` определяет `ElfInfo` и `SymbolVersion`.

Scanner отвечает за перевод частичных или неуспешных результатов `readelf` в
scan warnings. Он не сравнивает артефакт с target profiles.

### Построение compare-результата

Сравнение совместимости находится в `compatlab/src/compare/engine.py`.

`compare_report(report, target, assumed_provided_libraries=...)` принимает уже
просканированный `ArtifactReport` и `TargetProfile`, затем возвращает копию
report с заполненными `target`, `problems` и `warnings`.

Compare engine отвечает за проверки:

- несовпадение архитектуры;
- доступность dynamic linker/interpreter;
- требования к glibc, GLIBCXX и CXXABI;
- отсутствующие target libraries;
- абсолютные или build-time значения RPATH/RUNPATH.

Bundle-aware compare поведение сейчас находится в compare layer только частично.
Фактический обход bundle выполняет bundle resolver, а `cli.py` пока координирует
сравнение bundled ELF reports и объединение их problems.

### Diagnostics

Нормализованные diagnostics находятся в `compatlab/src/diagnostics.py`.

Модуль определяет:

- `DiagnosticIssue`;
- `DiagnosticSummary`;
- `DiagnosticSeverity`;
- `DiagnosticCategory`;
- `FailOn`;
- `diagnostics_from_report_parts`;
- `summarize_diagnostics`;
- `should_fail_for_diagnostics`.

Diagnostics создаются из legacy `Problem` objects и unresolved edges из
bundle `DependencyGraph`. Сейчас `cli.py` вызывает приватный workflow helper
`_with_diagnostics()`, чтобы прикрепить `diagnostics` и `summary` к reports
перед рендерингом или записью.

### Report models и терминальный вывод

Модели отчетов находятся в `compatlab/src/report/models.py`.

`ArtifactReport` является центральным объектом отчета. Он содержит metadata
артефакта, опциональные ELF-данные, опциональный target profile, diagnostics
summary, diagnostics, dependency graph, legacy problems и legacy warnings.

Терминальный рендеринг находится в `compatlab/src/report/pretty.py`.

### JSON reports

Запись JSON-отчетов находится в `compatlab/src/report/json.py`.

`write_json_report(report, path)` сериализует `ArtifactReport` через Pydantic
`model_dump_json`. Модуль не отвечает за построение report или diagnostics.

### HTML reports

HTML-рендеринг находится в `compatlab/src/report/html.py`.

Модуль определяет:

- `HtmlReportContext`;
- `render_html_report(report, context=...)`;
- `write_html_report(report, output_path, context=...)`;
- небольшие section renderers для summary, diagnostics, dependency graph,
  legacy problems/warnings и technical metadata.

HTML-вывод статический и самодостаточный. Renderer экранирует строки report
перед вставкой в HTML. Он не сканирует, не сравнивает и не генерирует
diagnostics.

### Bundle resolver

Резолвинг bundle-зависимостей находится в `compatlab/src/bundle/`.

- `models.py` определяет `DependencyGraph`, `DependencyNode`, `DependencyEdge`
  и `DependencyResolutionKind`.
- `resolver.py` предоставляет `resolve_bundle_dependencies(...)`.

Resolver индексирует файлы под `--bundle-root`, сканирует ELF-файлы через
`elfscan.scanner.scan_path`, следует прямым или recursive `DT_NEEDED`
dependencies, раскрывает `$ORIGIN` search paths, классифицирует dependencies
как `bundled`, `target`, `missing` или `ambiguous`, и возвращает
`BundleResolutionResult` с graph, scanned reports и warnings.

Resolver сейчас зависит от ELF scanning и library facts из target profile. Сам
compare engine он не запускает.

### Profiles

Profile-логика находится в `compatlab/src/profile/`.

- `models.py` определяет `SystemFacts`, `TargetProfile`, profile metadata,
  library facts, symbol facts и warnings.
- `loader.py` загружает built-in или external YAML profiles.
- `builtin.py` находит built-in profile files в `compatlab/profiles/`.
- `detect.py` обнаруживает facts текущего host через `ldd`, `ldconfig` и
  `readelf`.
- `generate.py` преобразует `SystemFacts` в `TargetProfile`.
- `docker_image.py` обнаруживает facts из Docker image rootfs exports.
- `docker_cli.py` оборачивает Docker CLI operations.
- `rootfs_tar.py` парсит exported rootfs tar files.
- `runtime_presets.py` определяет runtime package presets и install scripts.
- `ldd.py`, `ldconfig.py`, `linkers.py` и `os_release.py` содержат узкие
  parsers/helpers.

Profile detection и generation отделены от artifact scanning и compare, но
Docker image detection переиспользует parsing `readelf` для library symbol
versions.

### Внешние инструменты

Выполнение внешних команд сосредоточено в двух местах:

- `compatlab/src/elfscan/command.py` запускает generic commands и `readelf`.
- `compatlab/src/profile/docker_cli.py` строит Docker CLI commands через общий
  command runner.

Текущее прямое использование внешних инструментов:

- `readelf`: artifact scanning, current-system library symbol detection, Docker
  rootfs library symbol detection.
- `ldd --version`: current-system glibc detection.
- `ldconfig -p`: current-system library inventory.
- `docker`: image inspect, pull, create, start, export и cleanup.

## Целевые границы модулей

Текущая архитектура работоспособна, но следующий шаг должен уменьшить workflow
coupling в `cli.py`.

### Целевая ответственность CLI

`compatlab/src/cli.py` должен оставаться тонким adapter:

- разбирать command-line options;
- вызывать application services;
- рендерить пользовательские success/error messages;
- переводить результаты services в exit codes.

Он не должен собирать compare workflows, объединять bundled report problems или
знать детальный порядок scan, bundle, compare, diagnostics и report writing.

### Application service layer

Стоит ввести небольшой workflow layer, например `compatlab/src/app/` или
`compatlab/src/workflows/`, с services:

- `scan_artifact(options) -> ArtifactReport`;
- `compare_artifact(options) -> ArtifactReport`;
- `generate_profile(options) -> TargetProfile`;
- `detect_profile_facts(options) -> SystemFacts`;
- `write_requested_reports(report, outputs, context)`.

Этот слой должен владеть orchestration и сохранять domain modules сфокусированными.

### Domain modules

Нужно сохранить существующие domain boundaries:

- `elfscan`: извлекает ELF facts из файлов.
- `compare`: сравнивает scanned facts с target profiles.
- `bundle`: резолвит local dependency graphs.
- `diagnostics`: нормализует problems/graphs в stable diagnostic issues и
  summaries.
- `profile`: загружает, обнаруживает и генерирует target profiles.
- `report`: содержит data models и renderers/writers.

### External adapters

Выполнение команд должно оставаться изолированным от domain logic:

- `elfscan.command` остается generic process runner и readelf adapter.
- `profile.docker_cli` остается Docker adapter.
- Current-system adapters для `ldd` и `ldconfig` должны оставаться внутри
  `profile` или переехать за явные adapter functions, если вырастут.

Domain code должен получать parsed data или adapter results, а не строить raw
shell commands напрямую.

### Report pipeline

Целевой report pipeline:

1. Workflow строит `ArtifactReport`.
2. Workflow прикрепляет diagnostics через `diagnostics`.
3. CLI или workflow пишет запрошенные outputs через `report.json` и
   `report.html`.
4. CLI рендерит terminal output через `report.pretty`.
5. CLI применяет выбранный `FailOn` gate на основе diagnostics.

JSON и HTML должны оставаться renderers report model, а не местами, где
принимаются compatibility decisions.

### Известная связанность, которую нужно убрать

- `cli.py` сейчас содержит compare orchestration для bundled libraries.
- `cli.py` владеет `_dependency_problems`, который превращает unresolved bundle
  edges в legacy `Problem` objects.
- `cli.py` владеет `_with_diagnostics`, хотя diagnostic enrichment относится к
  report pipeline.
- `profile/docker_image.py` переиспользует compare helpers для version sorting и
  architecture normalization; со временем эти helpers могут переехать в общий
  normalization module.
- `bundle/resolver.py` напрямую сканирует ELF-файлы; пока это допустимо, но
  workflow layer мог бы сделать dependency scanning явным и более удобным для
  mock в тестах.
