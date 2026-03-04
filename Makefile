.PHONY: help install test test-unit test-integration test-with-emulator \
        dev-up dev-down dev-logs dev-build \
        emulators-up emulators-down \
        clean format lint generate-sample-data \
        gh-run-local hn-run-local gh-create-table hn-create-tables

# Default target
help:
	@echo "Cloud Storage → Cloud Run → BigQuery Pipeline"
	@echo ""
	@echo "Development:"
	@echo "  make install          - Install dependencies"
	@echo "  make dev-up           - Start local development environment"
	@echo "  make dev-down         - Stop local development environment"
	@echo "  make dev-logs         - View logs from development environment"
	@echo "  make dev-build        - Rebuild development containers"
	@echo ""
	@echo "Testing:"
	@echo "  make test             - Run all tests"
	@echo "  make test-unit        - Run unit tests (no emulators)"
	@echo "  make test-integration - Run integration tests (with emulators)"
	@echo "  make test-with-emulator - Run tests with BigQuery emulator"
	@echo ""
	@echo "Data:"
	@echo "  make generate-sample-data - Generate sample test data"
	@echo "  make gh-create-table  - Create GitHub BigQuery tables"
	@echo "  make hn-create-tables - Create HN BigQuery tables"
	@echo ""
	@echo "Local Services:"
	@echo "  make gh-run-local     - Run GitHub processor locally"
	@echo "  make hn-run-local     - Run HN processor locally"
	@echo ""
	@echo "Utilities:"
	@echo "  make format           - Format code with black"
	@echo "  make lint             - Run linting"
	@echo "  make clean            - Clean generated files"

# Installation
install:
	pip install -r requirements.txt
	pip install -e .

# Testing
test:
	pytest tests/ -v

test-unit:
	pytest tests/ -v -m "not emulator"

test-integration:
	docker-compose -f docker-compose.test.yml up -d bigquery gcs
	sleep 3
	BIGQUERY_EMULATOR_HOST=http://localhost:9050 pytest tests/ -v -m emulator
	docker-compose -f docker-compose.test.yml down

test-with-emulator:
	BIGQUERY_EMULATOR_HOST=http://localhost:9050 pytest tests/ -v

test-coverage:
	pytest tests/ --cov=src/ --cov-report=html --cov-report=term

# Development environment
dev-up:
	docker-compose -f docker-compose.dev.yml up -d

dev-down:
	docker-compose -f docker-compose.dev.yml down

dev-logs:
	docker-compose -f docker-compose.dev.yml logs -f

dev-build:
	docker-compose -f docker-compose.dev.yml build

dev-restart:
	docker-compose -f docker-compose.dev.yml restart

# Emulators only
emulators-up:
	docker-compose -f docker-compose.test.yml up -d

emulators-down:
	docker-compose -f docker-compose.test.yml down

emulator-status:
	docker-compose -f docker-compose.test.yml ps

# Local service runners (Python)
gh-run-local:
	cd src/github_archive && \
	PROJECT_ID=test-project \
	DATASET_ID=github_dataset \
	TABLE_ID=events \
	BUCKET_NAME=test-bucket \
	LOG_LEVEL=DEBUG \
	python -m main

hn-run-local:
	cd src/hacker_news && \
	PROJECT_ID=test-project \
	DATASET_ID=hacker_news \
	BUCKET_NAME=test-bucket \
	LOG_LEVEL=DEBUG \
	python -m main

# BigQuery table creation
gh-create-table:
	PROJECT_ID=test-project python scripts/create_bigquery_datasets.py --github

hn-create-tables:
	PROJECT_ID=test-project python scripts/create_bigquery_datasets.py --hackernews

create-all-tables:
	PROJECT_ID=test-project python scripts/create_bigquery_datasets.py --all

# Sample data generation
generate-sample-data:
	@mkdir -p tests/fixtures
	python scripts/generate_sample_data.py --source github --rows 100 --output tests/fixtures/sample-gh.json.gz
	python scripts/generate_sample_data.py --source hackernews --rows 50 --output tests/fixtures/sample-hn.json.gz

# Code quality
format:
	black src/ tests/ scripts/
	isort src/ tests/ scripts/

lint:
	flake8 src/ tests/ scripts/
	mypy src/ --ignore-missing-imports

lint-check:
	black --check src/ tests/ scripts/
	flake8 src/ tests/ scripts/
	mypy src/ --ignore-missing-imports

# Cleanup
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage htmlcov
	rm -rf tests/fixtures/*.json.gz
	rm -rf /tmp/test-*.json.gz
	docker-compose -f docker-compose.dev.yml down -v
	docker-compose -f docker-compose.test.yml down -v

# Health checks
health-check:
	@echo "Checking services..."
	@curl -s http://localhost:8081/health && echo " ✓ GitHub Processor" || echo " ✗ GitHub Processor"
	@curl -s http://localhost:8082/health && echo " ✓ HN Processor" || echo " ✗ HN Processor"
	@curl -s http://localhost:9050 >/dev/null && echo " ✓ BigQuery Emulator" || echo " ✗ BigQuery Emulator"
	@curl -s http://localhost:4443 >/dev/null && echo " ✓ GCS Emulator" || echo " ✗ GCS Emulator"

# Watch mode for development
watch:
	ptw tests/ --runner "pytest -v"

# Docker shortcuts
docker-bash-gh:
	docker-compose -f docker-compose.dev.yml exec github-processor bash

docker-bash-hn:
	docker-compose -f docker-compose.dev.yml exec hn-processor bash

docker-bash-bq:
	docker-compose -f docker-compose.dev.yml exec bigquery bash
