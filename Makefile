.PHONY: test lint format run-scan run-profiles

test:
	uv run pytest

lint:
	uv run ruff check .

format:
	uv run ruff format .

run-scan:
	uv run compatlab scan /bin/bash

run-profiles:
	uv run compatlab profiles list
