.PHONY: check-contract-types help clean test test-unit test-integration test-cov test-impacte lint lint-logging check check-frontend format install-dev version update-ytdlp perf-rebaseline openapi fixture harness harness-contracts maquette-oracle maquette-a11y

THRESHOLD := $(shell python3 scripts/get_coverage_threshold.py)

help:
	@echo "PersonalScraper — Available commands:"
	@echo "  make clean           - Remove build artifacts and cache files"
	@echo "  make test            - Run all tests with pytest"
	@echo "  make test-unit       - Run unit tests only (no coverage)"
	@echo "  make test-integration - Run integration tests only"
	@echo "  make test-cov        - Run tests with branch coverage at fail_under threshold"
	@echo "  make test-impacte    - Run only tests impacted by code changes (pytest-testmon)"
	@echo "  make lint            - Run ruff check + ruff format --check + mypy + logging audit"
	@echo "  make lint-logging    - Run logging convention audit (fails on errors)"
	@echo "  make check           - Run lint, tests, module-size, typed-api, pragma, CLI-coverage checks"
	@echo "  make format          - Format code with ruff"
	@echo "  make install-dev     - Install package in development mode with dev deps"
	@echo "  make version         - Show current version"
	@echo "  make update-ytdlp    - Upgrade yt-dlp + run network integration smoke test"
	@echo "  make perf-rebaseline - Run slow perf tests and write new baseline.json"
	@echo "  make openapi         - Export OpenAPI schema + regenerate frontend TS types"
	@echo "  make fixture         - Refresh the maquette follow fixture from acquire.db"

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

# Local iteration loop ONLY — selects tests whose recorded dependencies
# (.testmondata, built on first run) intersect the code changed since then.
# Runs single-process: testmon and xdist are incompatible. The FULL suite
# remains the gate everywhere it is one today (make test / make check).
# --testmon-forceselect: pyproject addopts pass -m (marker exclusions), and
# testmon silently deactivates selection under -m without this flag — the
# marker filter still applies to what testmon selects.
test-impacte:
	@echo "Running impacted tests only (pytest-testmon; full suite remains the gate)..."
	python3 -m pytest tests/ --ignore=tests/e2e -q --testmon --testmon-forceselect

test-cov:
	@echo "Running tests with branch coverage (fail_under=$(THRESHOLD))..."
	# Erase any leftover .coverage* files first — `parallel = true` writes
	# `.coverage.<host>.<pid>.<rand>` shards that can poison a subsequent
	# run on a dirty tree. Reproducible from any state.
	python3 -m coverage erase
	python3 -m pytest tests/ --ignore=tests/e2e -q --no-header -n auto \
		--cov=personalscraper --cov-branch --cov-report=xml --cov-report=term \
		--cov-fail-under=$(THRESHOLD)

lint:
	@echo "Running linter..."
	python -m ruff check personalscraper/ tests/ scripts/ frontend/maquette/ frontend/scripts/
	python -m ruff format --check personalscraper/ tests/
	python -m mypy personalscraper/
	$(MAKE) lint-logging

lint-logging:
	@echo "Running logging convention audit..."
	python scripts/check_logging.py personalscraper/

check: lint test-cov
	python3 scripts/check-module-size.py
	python3 scripts/check-module-size.py --root scripts
	python3 scripts/check-module-size.py --root tests
	python3 scripts/check-module-size.py --root frontend
	python3 scripts/check-no-broad-registry-catch.py
	python3 scripts/check-typed-api.py
	python3 scripts/check-pragma-discipline.py
	python3 scripts/check-no-french.py
	python3 scripts/check-code-abbreviations.py
	python3 scripts/check-css-tokens.py
	python3 scripts/check-compositor-css.py
	python3 scripts/check-tailwind-confinement.py
	python3 scripts/check-legacy-css-residue.py
	python3 scripts/check-markup-contracts.py
	python3 scripts/check-frontend-boundaries.py
	python3 scripts/check-state-ownership.py
	python3 frontend/maquette/oracle.py --contracts
	python3 scripts/check-i18n-placeholders.py
	python3 scripts/check-command-safety.py
	python3 scripts/audit-cli-coverage.py
	$(MAKE) cli-coverage-check
	@echo "Checking feature map freshness..."
	python3 scripts/update_feature_map.py --check
	@echo "Auditing design coverage..."
	python3 scripts/audit_design_coverage.py --strict
	@echo "Checking maquette fixture drift..."
	python3 scripts/refresh-maquette-fixture.py --check
	@echo "Running the maquette's unit suite, and holding its floor..."
	python3 scripts/check-maquette-unit-tests.py
	@echo "Checking the mock seeds against the fixtures they were taken from..."
	python3 scripts/check-mock-seeds.py
	@echo "Checking the backend-demand register against the two contracts..."
	python3 scripts/compare-contracts.py --check
	@echo "Checking OpenAPI drift..."
	@if [ -d frontend/node_modules ]; then $(MAKE) openapi && git diff --exit-code frontend/openapi.json frontend/src/api/schema.d.ts; else echo "openapi-drift: skipped (frontend/node_modules absent)"; fi
	@echo "Checking the maquette contract types for drift..."
	@if [ -d frontend/node_modules ]; then $(MAKE) check-contract-types; else echo "contract-types: skipped (frontend/node_modules absent)"; fi
	@echo "Checking version bump..."
	@if git rev-parse --verify origin/main >/dev/null 2>&1; then python3 scripts/check_version_bump.py --base origin/main; else echo "version-bump: skipped (origin/main unavailable)"; fi
	@if [ -d frontend/node_modules ]; then $(MAKE) check-frontend; else echo "check-frontend: skipped (frontend/node_modules absent)"; fi

cli-coverage-check:
	@echo "Running CLI coverage check..."
	python3 scripts/cli-coverage-report.py --check

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

fixture:
	@echo "Refreshing the maquette fixture from acquire.db..."
	python3 scripts/refresh-maquette-fixture.py --apply
	@echo "Then: frontend/maquette/harness/run.sh (the script rebuilds and re-copies itself)"

openapi:
	@echo "Exporting OpenAPI schema..."
	python scripts/export-openapi.py
	@echo "Regenerating frontend TypeScript types..."
	cd frontend && npm run gen-api
	@echo "OpenAPI schema and TS types are up to date."

check-contract-types:
	@echo "Regenerating the maquette contract types and refusing any difference..."
	@# THE EXEMPTION THIS TARGET EARNS. `mocks/contract-types.d.ts` is stepped
	@# over by the module-size ceiling and by the vocabulary arm, on the grounds
	@# that nobody writes it. That claim is only worth what this check is: the
	@# file is regenerated from the contract and any difference is refused, so a
	@# file carrying a line a human typed fails here. Both guards name this
	@# target as the proof behind their exemption.
	cd frontend/maquette/design && npm run generate-contract-types
	git diff --exit-code frontend/maquette/design/src/mocks/contract-types.d.ts

check-frontend:
	@echo "Running frontend typecheck..."
	cd frontend && npm run typecheck
	@echo "Running maquette shell typecheck..."
	@if [ -d frontend/maquette/design/node_modules ]; then cd frontend/maquette/design && npm run typecheck; else echo "maquette-typecheck: skipped (frontend/maquette/design/node_modules absent)"; fi
	@echo "Running frontend lint..."
	cd frontend && npm run lint
	cd frontend && npm run lint:ds
	@echo "Running frontend tests..."
	cd frontend && npm run test -- --run
	@echo "Running frontend build..."
	cd frontend && npm run build

harness:
	@echo "Running the maquette rule suite — the wave gate; one headless Chrome per rule, as many at a time as this machine has processors..."
	frontend/maquette/harness/run.sh

harness-contracts:
	@echo "Running the contract subset (8 rules) — what CI runs on every maquette PR..."
	frontend/maquette/harness/run.sh --contracts

maquette-oracle:
	@echo "Running the recorded oracle — 83 states x 33 regions against the committed reference..."
	frontend/maquette/harness/run.sh --oracle

maquette-a11y:
	@echo "Running the accessibility audit — axe-core over the 83 named states..."
	frontend/maquette/harness/run.sh --a11y
