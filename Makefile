.PHONY: help sync test core-test shared-test network-test lint format format-check manifest run pre-commit \
       docker-build docker-up docker-down docker-logs

help:
	@echo "UniFi Network MCP (read-only fork) — Top-Level Commands"
	@echo ""
	@echo "  make sync           Sync the uv workspace"
	@echo "  make run            Run the read-only Network MCP server over stdio"
	@echo "  make test           Run core, shared and Network tests"
	@echo "  make lint           Lint the workspace"
	@echo "  make format         Format the workspace"
	@echo "  make manifest       Regenerate the Network tool manifest"
	@echo "  make pre-commit     Format + manifest + lint + test"
	@echo "  make docker-build   Build the Network Docker image"

sync:
	uv sync --all-packages

run:
	uv run --package unifi-network-mcp unifi-network-mcp

test: core-test shared-test network-test

core-test:
	uv run --package unifi-core --all-extras pytest packages/unifi-core/tests -n auto -q

shared-test:
	uv run --package unifi-mcp-shared pytest packages/unifi-mcp-shared/tests -n auto -q

network-test:
	uv run --package unifi-network-mcp pytest apps/network/tests -n auto -q

lint:
	uv run ruff check .

format:
	uv run ruff format .

format-check:
	uv run ruff format --check .

manifest:
	$(MAKE) -C apps/network manifest

pre-commit:
	$(MAKE) format
	$(MAKE) manifest
	$(MAKE) lint
	$(MAKE) test

docker-build:
	docker compose -f docker/docker-compose.yml build

docker-up:
	docker compose -f docker/docker-compose.yml up --build -d

docker-down:
	docker compose -f docker/docker-compose.yml down

docker-logs:
	docker compose -f docker/docker-compose.yml logs -f
