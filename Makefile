# CricAlgo Makefile

.PHONY: help dev build test test-unit test-integration test-e2e lint clean

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

dev: ## Start development environment with docker-compose
	docker-compose up --build

build: ## Build the Docker image
	docker build -t cricalgo .

test: ## Run all tests
	pytest tests/

test-unit: ## Run unit tests only
	pytest tests/ -m "not integration and not e2e"

test-integration: ## Run integration tests with real database
	@echo "Starting test database and Redis..."
	docker-compose -f docker-compose.test.yml up -d postgres redis
	@echo "Waiting for services to be ready..."
	sleep 10
	@echo "Running integration tests..."
	DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5433/cricalgo_test \
	REDIS_URL=redis://localhost:6380/1 \
	pytest tests/integration/ -v
	@echo "Stopping test services..."
	docker-compose -f docker-compose.test.yml down

test-e2e: ## Run end-to-end tests with full stack
	@echo "Starting full test stack..."
	docker-compose -f docker-compose.test.yml up -d
	@echo "Waiting for services to be ready..."
	sleep 15
	@echo "Running E2E tests..."
	RUN_E2E=1 \
	DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5433/cricalgo_test \
	REDIS_URL=redis://localhost:6380/1 \
	pytest tests/e2e/ -v
	@echo "Stopping test services..."
	docker-compose -f docker-compose.test.yml down

test-coverage: ## Run tests with coverage report
	pytest tests/ --cov=app --cov-report=html --cov-report=term

lint: ## Run linting
	ruff check app/ tests/
	black --check app/ tests/

format: ## Format code
	black app/ tests/
	ruff check --fix app/ tests/

clean: ## Clean up Docker containers and volumes
	docker-compose down -v
	docker-compose -f docker-compose.test.yml down -v
	docker system prune -f

migrate: ## Run database migrations
	alembic upgrade head

migrate-create: ## Create a new migration
	alembic revision --autogenerate -m "$(message)"

shell: ## Open a shell in the app container
	docker-compose exec app bash

test-services: ## Start test services only (for manual testing)
	docker-compose -f docker-compose.test.yml up -d postgres redis
	@echo "Test services started. Database: localhost:5433, Redis: localhost:6380"
	@echo "Run 'make test-services-stop' to stop them"

test-services-stop: ## Stop test services
	docker-compose -f docker-compose.test.yml down

worker: ## Start Celery worker
	celery -A app.celery_app.celery worker --loglevel=info --concurrency=2

worker-logs: ## View worker logs
	docker-compose logs -f worker

worker-shell: ## Open Celery shell
	celery -A app.celery_app.celery shell

flower: ## Start Flower (Celery monitoring)
	celery -A app.celery_app.celery flower --port=5555

# Smoke test targets
smoke-up: ## Start test stack for smoke testing
	docker-compose -f docker-compose.test.yml up -d --build

smoke-test: ## Run smoke test script
	@echo "Running smoke test..."
	python scripts/smoke_test.py
	@echo "Smoke test completed. Check artifacts/smoke_test.log and artifacts/smoke_test_result.json"

smoke-down: ## Stop test stack
	docker-compose -f docker-compose.test.yml down -v

smoke: ## Run complete smoke test (up + test + down)
	@echo "Starting complete smoke test..."
	$(MAKE) smoke-up
	@echo "Waiting for services to be ready..."
	sleep 15
	$(MAKE) smoke-test
	$(MAKE) smoke-down
	@echo "Smoke test complete!"