.PHONY: help clean test test-unit test-integration test-cov lint lint-logging check format install-dev version update-ytdlp perf-rebaseline

THRESHOLD := $(shell python3 scripts/get_coverage_threshold.py)

help:
	@echo "PersonalScraper — Available commands:"
	@echo "  make clean           - Remove build artifacts and cache files"
	@echo "  make test            - Run all tests with pytest"
	@echo "  make test-unit       - Run unit tests only (no coverage)"
	@echo "  make test-integration - Run integration tests only"
	@echo "  make test-cov        - Run tests with branch coverage at fail_under threshold"
	@echo "  make lint            - Run ruff check + ruff format --check + mypy + logging audit"
	@echo "  make lint-logging    - Run logging convention audit (fails on errors)"
	@echo "  make check           - Run lint, tests, and advisory module-size check"
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
	python -m pytest -v -n auto

test-unit:
	@echo "Running unit tests..."
	python3 -m pytest tests/ --ignore=tests/integration --ignore=tests/e2e -q -n auto

test-integration:
	@echo "Running integration tests..."
	python3 -m pytest tests/integration/ -q -n auto

test-cov:
	@echo "Running tests with branch coverage (fail_under=$(THRESHOLD))..."
	python3 -m pytest tests/ --ignore=tests/e2e -q --no-header -n auto \
		--cov=personalscraper --cov-branch --cov-report=xml --cov-report=term \
		--cov-fail-under=$(THRESHOLD)

lint:
	@echo "Running linter..."
	python -m ruff check personalscraper/ tests/
	python -m ruff format --check personalscraper/ tests/
	python -m mypy personalscraper/
	$(MAKE) lint-logging

lint-logging:
	@echo "Running logging convention audit..."
	python scripts/check_logging.py personalscraper/

check: lint test-cov
	python3 scripts/check-module-size.py
	python3 scripts/check-typed-api.py

gate: check
	@echo "Gate: residual import audit..."
	@! rg -q "from personalscraper\.scraper\.circuit_breaker" personalscraper/ tests/ 2>/dev/null || { echo "FAIL: residual scraper.circuit_breaker import"; exit 1; }
	@! rg -q "from personalscraper\.scraper\.tmdb_client" personalscraper/ tests/ 2>/dev/null || { echo "FAIL: residual scraper.tmdb_client import"; exit 1; }
	@! rg -q "from personalscraper\.scraper\.tvdb_client" personalscraper/ tests/ 2>/dev/null || { echo "FAIL: residual scraper.tvdb_client import"; exit 1; }
	@! rg -q "from personalscraper\.scraper\.http_retry" personalscraper/ tests/ 2>/dev/null || { echo "FAIL: residual scraper.http_retry import"; exit 1; }
	@! rg -q "from personalscraper\.scraper\.providers" personalscraper/ tests/ 2>/dev/null || { echo "FAIL: residual scraper.providers import"; exit 1; }
	@! rg -l "TMDBError|TVDBError" personalscraper/ --include='*.py' 2>/dev/null | grep -v "_contracts.py" > /dev/null || { echo "FAIL: residual TMDBError/TVDBError references"; exit 1; }
	@python3 -c "import personalscraper" || { echo "FAIL: import personalscraper"; exit 1; }
	@echo "Gate: ALL CHECKS PASSED"

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
