.PHONY: help clean test lint lint-logging format install-dev version update-ytdlp perf-rebaseline

help:
	@echo "PersonalScraper — Available commands:"
	@echo "  make clean           - Remove build artifacts and cache files"
	@echo "  make test            - Run all tests with pytest"
	@echo "  make lint            - Run ruff linter + logging convention audit"
	@echo "  make lint-logging    - Run logging convention audit (fails on errors)"
	@echo "  make format          - Format code with ruff"
	@echo "  make install-dev     - Install package in development mode with dev deps"
	@echo "  make version         - Show current version"
	@echo "  make update-ytdlp    - Upgrade yt-dlp + run network integration smoke test"
	@echo "  make perf-rebaseline - Run slow perf tests and write new baseline.json"

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
	@echo "Running logging convention audit..."
	python scripts/check_logging.py personalscraper/

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

update-ytdlp:
	@echo "Updating yt-dlp..."
	python -m pip install -U yt-dlp
	@echo "Running yt-dlp integration test (requires TRAILER_INTEGRATION_TESTS=1)..."
	TRAILER_INTEGRATION_TESTS=1 python -m pytest tests/scraper/test_ytdlp_downloader.py -v -m network

perf-rebaseline:
	@echo "Running perf regression tests and updating baseline.json..."
	PERF_REBASELINE=1 python -m pytest -m slow tests/e2e/perf/test_indexer_perf.py -v
	@echo "baseline.json updated with fresh measurements."
