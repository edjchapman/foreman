.PHONY: help up down build logs migrate makemigrations test lint fmt ci shell

# Default goal prints help.
.DEFAULT_GOAL := help

help: ## Print available targets
	@grep -E '^[a-z][a-zA-Z0-9_-]*:.*##' $(MAKEFILE_LIST) \
		| awk 'BEGIN { FS = ":.*##" } { printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2 }'

# === Local stack (Docker) ===

up: ## Start the local stack (Django + Postgres) with live reload
	docker compose up --build

down: ## Stop the stack and remove volumes
	docker compose down -v

build: ## Build the web image
	docker compose build

logs: ## Tail stack logs
	docker compose logs -f

# === App (host, via uv) ===

migrate: ## Apply migrations
	uv run python manage.py migrate

makemigrations: ## Generate migrations
	uv run python manage.py makemigrations

test: ## Run the test suite
	uv run pytest

lint: ## Lint + format-check (no changes)
	uv run ruff check .
	uv run ruff format --check .

fmt: ## Auto-fix lint + format
	uv run ruff check --fix .
	uv run ruff format .

ci: lint test ## What CI runs: lint + tests

shell: ## Django shell
	uv run python manage.py shell
