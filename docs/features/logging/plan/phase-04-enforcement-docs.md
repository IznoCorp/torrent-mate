# Phase 04 — Enforcement & Documentation

**Goal**: regressions are caught by CI, and contributors have a reference to point at.

## Sub-phase 4.1 — Flip the linter from report-only to hard failure

- Edit `scripts/check_logging.py` so the default exit code is `1` on any finding.
- Keep the `--report-only` flag for manual use.
- Update the Makefile `lint-logging` target to drop `--report-only`.
- Run `make lint-logging` locally to confirm the clean baseline.

### Commit

`feat(tooling): enforce logging convention in lint`

## Sub-phase 4.2 — Write the reference doc

New file : `docs/reference/logging.md`.

Contents :

- The three channels table from the design doc.
- A one-paragraph "why" pointing at the problem statement.
- Canonical code snippets : structured log, CLI output, interactive prompt.
- Pointers to `personalscraper/logger.py` (factory) and `scripts/check_logging.py` (enforcement).
- Common migration recipes (pattern → replacement).

Add a row in `CLAUDE.md`'s **Reference Index** table pointing to the new doc (trigger : "when writing any new logging call").

If `.claude/norms.md` exists in the project, add a one-line rule pointing at the reference doc.

### Commit

`docs(reference): add logging convention reference`

## Sub-phase 4.3 — Wire into CI (optional, if not already covered by `make lint`)

If `make lint` is already called in CI, nothing to do — Phase 01/04.1 already plugged the script into `lint`.

Otherwise :

- Add a step to the CI workflow that runs `make lint-logging`.

### Quality gate (final)

- `make lint` green on a freshly cloned checkout.
- CI runs the logging check on every PR.
- `docs/reference/logging.md` linked from `CLAUDE.md`.
- Grep across `personalscraper/` returns zero `import logging\b` / `logging.getLogger` / raw `print(` findings.

## Exit criteria for the feature

All phase gates green ⇒ ready for `/implement:pr-review` and merge.
