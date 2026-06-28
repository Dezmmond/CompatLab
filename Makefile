.PHONY: test coverage coverage-html lint format format-check check run-scan run-profiles

test:
	uv run pytest

coverage:
	uv run pytest --cov=compatlab --cov-report=term-missing --cov-report=xml

coverage-html:
	uv run pytest --cov=compatlab --cov-report=term-missing --cov-report=html

check: coverage lint format-check

lint:
	uv run ruff check .

format:
	uv run ruff format .

format-check:
	uv run ruff format --check .

run-scan:
	uv run compatlab scan /bin/bash

run-profiles:
	uv run compatlab profiles list
