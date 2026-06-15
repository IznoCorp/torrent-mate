# KanbanMate developer task runner.
#
# Targets:
#   lint   ruff check + ruff format --check + mypy (strict) on src and tests.
#   test   pytest, excluding the integration marker.
#   size   per-file LOC guard: warn at 800, fail above 1000 (src only).
#   check  lint + test + size (the full local gate).

# Use bash for recipes (the size guard relies on process substitution).
SHELL := /bin/bash

.PHONY: lint test size check

lint:
	ruff check src tests
	ruff format --check src tests
	mypy src tests

test:
	pytest -m "not integration"

# Per-file module-size guard. Warns (non-fatal) when a src module exceeds the
# soft 800-LOC threshold, and FAILS the build when any module exceeds the hard
# 1000-LOC ceiling. Counts physical lines in every tracked src/**/*.py file.
size:
	@fail=0; \
	while IFS= read -r f; do \
		[ -z "$$f" ] && continue; \
		lines=$$(wc -l < "$$f" | tr -d ' '); \
		if [ "$$lines" -gt 1000 ]; then \
			echo "ERROR: $$f has $$lines LOC (hard ceiling 1000)"; \
			fail=1; \
		elif [ "$$lines" -gt 800 ]; then \
			echo "WARN: $$f has $$lines LOC (soft warning 800)"; \
		fi; \
	done < <(find src -name '*.py' -type f); \
	if [ "$$fail" -ne 0 ]; then \
		echo "size guard failed: at least one module exceeds the 1000-LOC hard ceiling"; \
		exit 1; \
	fi

check: lint test size
