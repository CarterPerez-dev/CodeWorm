# ©AngelaMos | 2026
# justfile

set dotenv-filename := ".env.development"
set dotenv-load
set export
set shell := ["bash", "-uc"]
set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]

project := file_name(justfile_directory())
version := `git describe --tags --always 2>/dev/null || echo "dev"`

# =============================================================================
# Default
# =============================================================================

default:
    @just --list --unsorted

# =============================================================================
# CodeWorm Daemon (runs on host)
# =============================================================================

[group('daemon')]
run:
    uv run codeworm run

[group('daemon')]
run-once *ARGS:
    uv run codeworm run-once {{ARGS}}

[group('daemon')]
run-once-dry:
    uv run codeworm run-once --dry-run

[group('daemon')]
status:
    uv run codeworm status

# =============================================================================
# Linting
# =============================================================================

[group('lint')]
ruff *ARGS:
    ruff check codeworm/ {{ARGS}}

[group('lint')]
ruff-fix:
    ruff check codeworm/ --fix
    ruff format codeworm/

[group('lint')]
ruff-format:
    ruff format codeworm/

[group('lint')]
lint: ruff

# =============================================================================
# Frontend Linting
# =============================================================================

[group('frontend')]
biome *ARGS:
    cd dashboard/frontend && pnpm biome check . {{ARGS}}

[group('frontend')]
biome-fix:
    cd dashboard/frontend && pnpm biome check --write .

[group('frontend')]
tsc *ARGS:
    cd dashboard/frontend && pnpm tsc --noEmit {{ARGS}}

# =============================================================================
# Type Checking
# =============================================================================

[group('types')]
mypy *ARGS:
    mypy codeworm {{ARGS}}

[group('types')]
typecheck: mypy

# =============================================================================
# Testing
# =============================================================================

[group('test')]
pytest *ARGS:
    pytest tests {{ARGS}}

[group('test')]
test: pytest

[group('test')]
test-cov:
    pytest tests --cov=codeworm --cov-report=term-missing --cov-report=html

# =============================================================================
# CI / Quality
# =============================================================================

[group('ci')]
ci: lint typecheck test

[group('ci')]
check: ruff mypy

# =============================================================================
# Docker Compose (Production)
# =============================================================================

[group('prod')]
up *ARGS:
    docker compose --env-file .env up {{ARGS}}

[group('prod')]
start *ARGS:
    docker compose --env-file .env up -d {{ARGS}}

[group('prod')]
down *ARGS:
    docker compose --env-file .env down {{ARGS}}

[group('prod')]
stop:
    docker compose --env-file .env stop

[group('prod')]
build *ARGS:
    docker compose --env-file .env build {{ARGS}}

[group('prod')]
rebuild:
    docker compose --env-file .env build --no-cache

[group('prod')]
logs *SERVICE:
    docker compose --env-file .env logs -f {{SERVICE}}

[group('prod')]
ps:
    docker compose --env-file .env ps

[group('prod')]
shell service='dashboard':
    docker compose --env-file .env exec -it {{service}} /bin/bash

# =============================================================================
# Docker Compose (Development)
# =============================================================================

[group('dev')]
dev-up *ARGS:
    docker compose -f dev.compose.yml up {{ARGS}}

[group('dev')]
dev-start *ARGS:
    docker compose -f dev.compose.yml up -d {{ARGS}}

[group('dev')]
dev-down *ARGS:
    docker compose -f dev.compose.yml down {{ARGS}}

[group('dev')]
dev-stop:
    docker compose -f dev.compose.yml stop

[group('dev')]
dev-build *ARGS:
    docker compose -f dev.compose.yml build {{ARGS}}

[group('dev')]
dev-rebuild:
    docker compose -f dev.compose.yml build --no-cache

[group('dev')]
dev-logs *SERVICE:
    docker compose -f dev.compose.yml logs -f {{SERVICE}}

[group('dev')]
dev-ps:
    docker compose -f dev.compose.yml ps

[group('dev')]
dev-shell service='dashboard':
    docker compose -f dev.compose.yml exec -it {{service}} /bin/bash

# =============================================================================
# Ollama Management
# =============================================================================

[group('ollama')]
ollama-pull model='qwen2.5:7b':
    docker exec ${APP_NAME:-codeworm}-ollama ollama pull {{model}}

[group('ollama')]
ollama-list:
    docker exec ${APP_NAME:-codeworm}-ollama ollama list

[group('ollama')]
ollama-ps:
    docker exec ${APP_NAME:-codeworm}-ollama ollama ps

# =============================================================================
# Utilities
# =============================================================================

[group('util')]
info:
    @echo "Project: {{project}}"
    @echo "Version: {{version}}"
    @echo "OS: {{os()}} ({{arch()}})"

[group('util')]
clean:
    -rm -rf .mypy_cache
    -rm -rf .pytest_cache
    -rm -rf .ruff_cache
    -rm -rf htmlcov
    -rm -rf .coverage
    @echo "Cache directories cleaned"
