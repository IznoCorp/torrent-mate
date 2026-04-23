.PHONY: help clean test lint lint-logging format install-dev version

help:
	@echo "PersonalScraper — Available commands:"
	@echo "  make clean       - Remove build artifacts and cache files"
	@echo "  make test        - Run all tests with pytest"
	@echo "  make lint        - Run ruff linter + logging convention audit"
	@echo "  make lint-logging - Run logging convention audit (report-only)"
	@echo "  make format      - Format code with ruff"
	@echo "  make install-dev - Install package in development mode with dev deps"
	@echo "  make version     - Show current version"

clean:
	@echo "Cleaning build artifacts..."
	rm -rf dist/ build/ *.egg-info personalscraper.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache/ htmlcov/ .coverage
	@echo "Clean complete!"

test:
	@echo "Running tests..."
	python -m pytest -v

lint:
	@echo "Running linter..."
	python -m ruff check personalscraper/ tests/
	$(MAKE) lint-logging

lint-logging:
	@echo "Running logging convention audit (report-only)..."
	python scripts/check_logging.py --report-only personalscraper/

format:
	@echo "Formatting code..."
	python -m ruff format personalscraper/ tests/
	python -m ruff check --fix personalscraper/ tests/

install-dev:
	@echo "Installing PersonalScraper in development mode..."
	pip install -e ".[dev]"

version:
	@echo "Current version:"
	@python -c "from personalscraper import __version__; print(__version__)"
