# CricAlgo Makefile

.PHONY: help dev build test lint clean

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

dev: ## Start development environment with docker-compose
	docker-compose up --build

build: ## Build the Docker image
	docker build -t cricalgo .

test: ## Run tests
	pytest tests/

lint: ## Run linting
	ruff check app/ tests/
	black --check app/ tests/

format: ## Format code
	black app/ tests/
	ruff check --fix app/ tests/

clean: ## Clean up Docker containers and volumes
	docker-compose down -v
	docker system prune -f

migrate: ## Run database migrations
	alembic upgrade head

migrate-create: ## Create a new migration
	alembic revision --autogenerate -m "$(message)"

shell: ## Open a shell in the app container
	docker-compose exec app bash
