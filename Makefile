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

build-bin-ubuntu2204:
	docker build -f packaging/Dockerfile.ubuntu2204 -t compatlab-build-ubuntu2204 .
	mkdir -p dist-bin
	cid="$$(docker create compatlab-build-ubuntu2204)"; \
	docker cp "$$cid:/out/compatlab" ./dist-bin/compatlab; \
	docker rm "$$cid"; \
	chmod +x ./dist-bin/compatlab

test-bin-ubuntu2204:
	docker run --rm \
		-v "$$(pwd)/dist-bin/compatlab:/usr/local/bin/compatlab:ro" \
		ubuntu:22.04 \
		bash -lc 'apt-get update && apt-get install -y binutils && compatlab --help && compatlab profiles list && compatlab scan /bin/bash && compatlab compare /bin/bash --target ubuntu-2204'
