.PHONY: test coverage coverage-html lint format format-check check run-scan run-profiles build-bin-ubuntu2204 test-bin-ubuntu2204 build-bin-sberlinux97 test-bin-sberlinux97

UBUNTU2204_BUILD_NAME ?= compatlab-build-ubuntu2204
UBUNTU2204_BUILD_IMAGE ?= ubuntu:22.04

SBERLINUX97_BASE_IMAGE ?=
SBERLINUX97_BUILD_NAME ?= compatlab-build-sberlinux97
SBERLINUX97_BUILD_IMAGE ?=

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
	docker build \
		-f packaging/Dockerfile.ubuntu2204 \
		-t $(UBUNTU2204_BUILD_NAME) \
		.
	mkdir -p dist-bin
	cid="$$(docker create $(UBUNTU2204_BUILD_NAME))"; \
	docker cp "$$cid:/out/compatlab" ./dist-bin/compatlab; \
	docker rm "$$cid"; \
	chmod +x ./dist-bin/compatlab

test-bin-ubuntu2204:
	docker run --rm \
		-v "$$(pwd)/dist-bin/compatlab:/usr/local/bin/compatlab:ro" \
		$(UBUNTU2204_BUILD_IMAGE) \
		bash -lc 'apt-get update && apt-get install -y binutils && compatlab --help && compatlab profiles list && compatlab scan /bin/bash && compatlab compare /bin/bash --target ubuntu-2204'

build-bin-sberlinux97:
	@test -n "$(SBERLINUX97_BASE_IMAGE)" || (echo "Set SBERLINUX97_BASE_IMAGE to a reachable SberLinux 9.7 image"; exit 1)
	docker build \
		-f packaging/Dockerfile.sberlinux97 \
		--build-arg BASE_IMAGE="$(SBERLINUX97_BASE_IMAGE)" \
		-t $(SBERLINUX97_BUILD_NAME) \
		.
	mkdir -p dist-bin
	cid="$$(docker create $(SBERLINUX97_BUILD_NAME))"; \
	docker cp "$$cid:/out/compatlab" ./dist-bin/compatlab-sberlinux97; \
	docker rm "$$cid"; \
	chmod +x ./dist-bin/compatlab-sberlinux97

test-bin-sberlinux97:
	@test -n "$(SBERLINUX97_BUILD_IMAGE)" || (echo "Set SBERLINUX97_RUN_IMAGE to a reachable SberLinux 9.7 runtime image"; exit 1)
	docker run --rm \
		-v "$$(pwd)/dist-bin/compatlab-sberlinux97:/usr/local/bin/compatlab:ro" \
		"$(SBERLINUX97_BUILD_IMAGE)" \
		bash -lc 'command -v dnf >/dev/null 2>&1 || (echo "dnf is required"; exit 1); dnf -y install binutils && compatlab --help && compatlab profiles list && compatlab scan /bin/bash && compatlab compare /bin/bash --target sberlinux-9'
