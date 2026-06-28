# CompatLab ArtifactDoctor

Инструмент предварительной проверки совместимости бинарных артефактов Linux.

CompatLab ArtifactDoctor - это Python-first CLI-инструмент для проверки того,
сможет ли Linux-бинарник с высокой вероятностью запуститься на целевом Linux-
профиле до поставки. Цель продукта — превращать низкоуровневые ELF-факты в
диагноз совместимости: слишком новая версия `glibc` или `libstdc++`,
отсутствующий dynamic linker, отсутствующие библиотеки `DT_NEEDED`, неверная
архитектура и подозрительные значения `RPATH`/`RUNPATH`.

Сейчас репозиторий содержит Python-first CLI-каркас и первый реальный backend
ELF-сканера на основе системной утилиты `readelf`.

## CLI

```bash
compatlab scan ./app
compatlab compare ./app --target ubuntu-1804
compatlab profiles list
compatlab profiles show ubuntu-1804
```

Для `scan` и `compare` уже подключен вывод JSON-отчета:

```bash
compatlab scan ./app --json report.json
compatlab compare ./app --target ubuntu-1804 --json report.json
```

## Объем MVP

Первый MVP намеренно узкий:

- один ELF-бинарник или shared library на входе;
- один целевой профиль в YAML;
- красивый терминальный вывод через Rich;
- JSON-отчеты на основе Pydantic-моделей;
- CLI на Typer, подходящий для CI;
- целевые профили для распространенных Linux baseline;
- таксономия проблем, готовая для диагностики совместимости.

## Пока не входит в задачу

Этот каркас не добавляет web UI, базу данных, daemon, анализ wheel/RPM/DEB,
сканирование container/rootfs, SBOM/security scan, автоматический patching или
реализацию на Go. Все это явно находится за пределами первого этапа реализации.

## Разработка

```bash
make test
make coverage
make check
uv run compatlab scan /bin/bash
```

`make coverage` выводит общий процент покрытия тестами в терминал и записывает
`coverage.xml`. `make coverage-html` дополнительно создает HTML-отчет в
`htmlcov/`.
