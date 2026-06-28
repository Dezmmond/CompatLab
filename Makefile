.PHONY: test build run-scan fmt vet

test:
    go test ./...

build:
    go build -o bin/compatlab ./cmd/compatlab

run-scan:
    go run ./cmd/compatlab scan /bin/bash

fmt:
    go fmt ./...

vet:
    go vet ./...
