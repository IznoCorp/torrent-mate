# Phase 1 — CLI flag + core dry-run branch + tests

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire `--dry-run` through the CLI into `Sorter`, intercept filesystem ops, cover the branch with unit + E2E tests, and pass the quality gate.

**Architecture:** Single injection point — `Sorter.__init__(dry_run: bool)` guards `shutil.move`/`os.rename` with an `if self.dry_run:` branch that logs `[DRY-RUN]` and returns `status="dry-run"`. Flag is a Typer `Option` on `sort`; `run_sort()` threads it through.

**Tech Stack:** Python 3.11+, Typer, pytest, ruff, mypy

**Implementation note:** Code already exists on `main`. This phase verifies completeness, fills any gaps, and runs the quality gate.

---

## Files

| Action        | Path                                                                                     |
| ------------- | ---------------------------------------------------------------------------------------- |
| Verify/Modify | `personalscraper/cli.py` — `sort` command `--dry-run` option                             |
| Verify/Modify | `personalscraper/sorter/run.py` — `run_sort(dry_run=False)` parameter                    |
| Verify/Modify | `personalscraper/sorter/sorter.py` — `Sorter.dry_run` + branch in `sort_item()`          |
| Verify/Add    | `tests/sorter/test_sorter.py` — unit tests: no side effect, correct status + destination |
| Verify/Add    | `tests/sorter/test_e2e.py` — `run_sort(dry_run=True)` + `Sorter.process(dry_run=True)`   |
| Verify/Add    | `tests/test_cli.py` — `["sort", "--dry-run"]` CLI passthrough                            |

---

## Sub-phase 1.1 — CLI flag + core implementation

- [ ] **Step 1: Verify CLI flag**

  ```bash
  grep -n "dry.run" personalscraper/cli.py | grep -i sort
  ```

  Expected: `dry_run: bool = typer.Option(False, "--dry-run", ...)` on the `sort` command.
  If missing, add to `sort()` in `personalscraper/cli.py`:

  ```python
  dry_run: bool = typer.Option(False, "--dry-run", help="Preview without moving"),
  ```

  And pass through: `run_sort(settings, staging_dir=config.paths.staging_dir, dry_run=dry_run)`

- [ ] **Step 2: Verify `run_sort` signature**

  ```bash
  grep -n "def run_sort" personalscraper/sorter/run.py
  ```

  Expected: `def run_sort(settings: Settings, staging_dir: Path, dry_run: bool = False) -> StepReport:`
  If missing, add `dry_run: bool = False` parameter and pass it to `Sorter(cleaner=cleaner, dry_run=dry_run)`.

- [ ] **Step 3: Verify `Sorter.sort_item()` dry-run branch**

  ```bash
  grep -n "dry_run\|DRY-RUN" personalscraper/sorter/sorter.py
  ```

  Expected: `if self.dry_run:` guard before any `shutil.move`/`os.rename`, returning `SortResult(..., status="dry-run")`.
  If missing, insert after computing `dest_path` and before `dest_path.parent.mkdir(...)`:

  ```python
  if self.dry_run:
      action = "replace" if is_movie_dir_replace else "move"
      logger.info("[DRY-RUN] Would %s %s -> %s", action, item, dest_path)
      return SortResult(
          source=item, destination=dest_path, media_type=file_type.value,
          title=title, year=year, season=season, episode=episode,
          status="dry-run", message=None,
      )
  ```

- [ ] **Step 4: Verify `run_sort` details population**

  In `personalscraper/sorter/run.py`, confirm `elif r.status == "dry-run":` branch exists:

  ```python
  elif r.status == "dry-run":
      report.success_count += 1
      report.details.append(f"[DRY-RUN] {r.source.name} -> {r.destination}")
  ```

- [ ] **Step 5: Commit if any changes were made**

  ```bash
  git add personalscraper/cli.py personalscraper/sorter/run.py personalscraper/sorter/sorter.py
  git commit -m "feat(sort-dry-run): wire --dry-run through CLI, run_sort, and Sorter"
  ```

---

## Sub-phase 1.2 — Unit tests

- [ ] **Step 6: Check existing unit test coverage**

  ```bash
  grep -n "class TestSortItemDryRun\|def test_dry_run" tests/sorter/test_sorter.py
  ```

  Required tests: `test_dry_run_does_not_move`, `test_dry_run_movie_destination`, `test_dry_run_tvshow_destination`.

- [ ] **Step 7: Add any missing unit tests to `tests/sorter/test_sorter.py`**

  ```python
  class TestSortItemDryRun:
      """Sorter.sort_item() dry-run — no filesystem side effects."""

      def test_dry_run_does_not_move(self, staging):
          movie = staging / "Movie.2024.mkv"
          movie.touch()
          result = Sorter(dry_run=True).sort_item(movie, staging)
          assert result.status == "dry-run"
          assert movie.exists()  # original untouched

      def test_dry_run_movie_destination(self, staging):
          movie = staging / "Movie.Title.2024.1080p.mkv"
          movie.touch()
          result = Sorter(dry_run=True).sort_item(movie, staging)
          assert "001-MOVIES" in str(result.destination)
          assert result.year == 2024

      def test_dry_run_tvshow_destination(self, staging):
          episode = staging / "Show.S01E04.1080p.mkv"
          episode.touch()
          result = Sorter(dry_run=True).sort_item(episode, staging)
          assert "002-TVSHOWS" in str(result.destination)
          assert result.season == 1
          assert result.episode == 4
  ```

- [ ] **Step 8: Run unit tests**

  ```bash
  python -m pytest tests/sorter/test_sorter.py -v
  ```

  Expected: all PASS.

- [ ] **Step 9: Commit if new tests were added**

  ```bash
  git add tests/sorter/test_sorter.py
  git commit -m "test(sort-dry-run): unit tests for Sorter dry-run branch"
  ```

---

## Sub-phase 1.3 — E2E + quality gate

- [ ] **Step 10: Check E2E coverage**

  ```bash
  grep -n "dry.run\|DRY-RUN" tests/sorter/test_e2e.py tests/test_cli.py
  ```

  Required: `test_run_sort_dry_run` (checks `[DRY-RUN]` in details, originals still exist) and `test_sort_dry_run` CLI test (exit 0).

- [ ] **Step 11: Add missing E2E tests**

  In `tests/sorter/test_e2e.py` (`TestE2ERunSort`):

  ```python
  def test_run_sort_dry_run(self, staging_settings, staging):
      """run_sort dry-run: details contain [DRY-RUN], no files moved."""
      temp = staging / "097-TEMP"
      temp.mkdir(exist_ok=True)
      movie_dir = temp / "Movie.2024.1080p"
      movie_dir.mkdir()
      (movie_dir / "movie.mkv").write_text("video")
      report = run_sort(staging_settings, staging_dir=staging, dry_run=True)
      assert report.success_count == 1
      assert any("[DRY-RUN]" in d for d in report.details)
      assert movie_dir.exists()
  ```

  In `tests/test_cli.py` (CLI smoke — mock `run_sort` to avoid filesystem):

  ```python
  @patch("personalscraper.sorter.run.run_sort", return_value=_mock_sort_report)
  @patch("personalscraper.cli.release_lock")
  @patch("personalscraper.cli.acquire_lock", return_value=True)
  def test_sort_dry_run(mock_lock, mock_release, mock_run):
      """sort --dry-run passes flag through and exits 0."""
      result = runner.invoke(app, ["sort", "--dry-run"])
      assert result.exit_code == 0
      assert mock_run.call_args is not None
  ```

- [ ] **Step 12: Run full sort test suite**

  ```bash
  python -m pytest tests/sorter/ tests/test_cli.py -v
  ```

  Expected: all PASS.

- [ ] **Step 13: Quality gate**

  ```bash
  make lint && make test
  ```

  Expected: ruff clean, all tests PASS.

- [ ] **Step 14: Commit if new tests were added**

  ```bash
  git add tests/sorter/test_e2e.py tests/test_cli.py
  git commit -m "test(sort-dry-run): E2E smoke tests for sort --dry-run"
  ```

---

## Coherence gate

- [ ] `personalscraper sort --help` shows `--dry-run` option
- [ ] `make test` exits 0
- [ ] `make lint` exits 0
- [ ] No moved/renamed files in any dry-run test (asserted by `item.exists()` checks)
