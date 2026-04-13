# Phase 1: Ingest Per-Torrent Error Isolation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restructure `run_ingest()` so one torrent failure does not abort all remaining torrents. Replace string-based exception heuristics with `isinstance()` checks.

**Architecture:** Split the monolithic try/except into two levels — outer for qBit session errors, inner per-torrent isolation.

**Tech Stack:** Python, qbittorrent-api, requests, pytest

---

## Task 1: Write failing tests for per-torrent error isolation

**Files:**

- Modify: `tests/ingest/test_ingest.py`

- [ ] **Step 1: Add test for per-torrent isolation**

Add this test to `TestRunIngest` in `tests/ingest/test_ingest.py`:

```python
@patch("personalscraper.ingest.ingest.transfer_torrent")
@patch("personalscraper.ingest.ingest.IngestTracker")
@patch("personalscraper.ingest.ingest.QBitClient")
def test_one_torrent_failure_does_not_block_others(
    self,
    mock_qbit_cls: MagicMock,
    mock_tracker_cls: MagicMock,
    mock_transfer: MagicMock,
    tmp_path: Path,
) -> None:
    """A failing torrent should not prevent processing of remaining torrents."""
    settings = MagicMock()
    settings.staging_dir = tmp_path
    settings.ingest_dir = tmp_path / "097-TEMP"
    settings.min_free_space_staging_gb = 0

    t1 = _make_torrent("Good1", "h1")
    t2 = _make_torrent("Bad", "h2")
    t3 = _make_torrent("Good2", "h3")

    # Create source dirs
    for name in ("Good1", "Bad", "Good2"):
        src = tmp_path / "complete" / name
        src.mkdir(parents=True, exist_ok=True)
        (src / "file.mkv").write_bytes(b"\x00" * 100)

    mock_client = MagicMock()
    mock_client.get_completed_torrents.return_value = [t1, t2, t3]
    mock_client.get_all_torrent_hashes.return_value = {"h1", "h2", "h3"}
    mock_client.get_content_path.side_effect = [
        tmp_path / "complete" / "Good1",
        tmp_path / "complete" / "Bad",
        tmp_path / "complete" / "Good2",
    ]
    mock_client.is_seeding.side_effect = [False, False, False]
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_qbit_cls.return_value = mock_client

    mock_tracker = MagicMock()
    mock_tracker.is_ingested.return_value = False
    mock_tracker_cls.return_value = mock_tracker

    # 2nd torrent transfer raises OSError
    mock_transfer.side_effect = [True, OSError("Disk I/O error"), True]

    report = run_ingest(settings)

    # Torrent 1 and 3 succeed, torrent 2 is an error
    assert report.success_count == 2
    assert report.error_count == 1
    assert any("Bad" in d for d in report.details)
```

- [ ] **Step 2: Add test for LoginFailed actionable message**

```python
@patch("personalscraper.ingest.ingest.QBitClient")
def test_login_failed_actionable_message(
    self, mock_qbit_cls: MagicMock, tmp_path: Path,
) -> None:
    """LoginFailed should produce an actionable error message."""
    import qbittorrentapi

    settings = MagicMock()
    settings.staging_dir = tmp_path
    settings.ingest_dir = tmp_path / "097-TEMP"

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(side_effect=qbittorrentapi.LoginFailed())
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_qbit_cls.return_value = mock_client

    report = run_ingest(settings)

    assert report.error_count >= 1
    assert any("auth" in d.lower() or "login" in d.lower() for d in report.details)
```

- [ ] **Step 3: Add test for APIConnectionError actionable message**

```python
@patch("personalscraper.ingest.ingest.QBitClient")
def test_api_connection_error_actionable_message(
    self, mock_qbit_cls: MagicMock, tmp_path: Path,
) -> None:
    """APIConnectionError should produce an actionable error message."""
    import qbittorrentapi

    settings = MagicMock()
    settings.staging_dir = tmp_path
    settings.ingest_dir = tmp_path / "097-TEMP"

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(
        side_effect=qbittorrentapi.APIConnectionError("Connection refused"),
    )
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_qbit_cls.return_value = mock_client

    report = run_ingest(settings)

    assert report.error_count >= 1
    assert any("unreachable" in d.lower() or "running" in d.lower() for d in report.details)
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `python -m pytest tests/ingest/test_ingest.py::TestRunIngest::test_one_torrent_failure_does_not_block_others tests/ingest/test_ingest.py::TestRunIngest::test_login_failed_actionable_message tests/ingest/test_ingest.py::TestRunIngest::test_api_connection_error_actionable_message -v`

Expected: FAIL — the per-torrent isolation test fails because the current code's `except Exception` aborts after the 2nd torrent raises. The LoginFailed and APIConnectionError tests may fail because the current string-matching heuristic handles them inconsistently.

- [ ] **Step 5: Commit test stubs**

```bash
git add tests/ingest/test_ingest.py
git commit -m "v11.1.1: Add failing tests for per-torrent error isolation"
```

## Task 2: Restructure run_ingest() error handling

**Files:**

- Modify: `personalscraper/ingest/ingest.py:167-321`

- [ ] **Step 1: Add qBit exception imports**

At the top of `personalscraper/ingest/ingest.py`, add `requests` and import `QBitAuthLockoutError`:

```python
import requests
from personalscraper.ingest.qbit_client import QBitClient, QBitAuthLockoutError
```

Note: `QBitClient` is already imported on line 13. Modify that line to also import `QBitAuthLockoutError`.

- [ ] **Step 2: Add inner per-torrent try/except**

In `run_ingest()`, wrap the body of the `for torrent in torrents:` loop (lines 215-277) in a try/except:

```python
            for torrent in torrents:
                try:
                    name = torrent.name
                    torrent_hash = torrent.hash

                    # Skip already ingested
                    if tracker.is_ingested(torrent_hash):
                        log.debug("already_ingested", name=name)
                        report.skip_count += 1
                        continue

                    # Resolve content path — if missing, check if already in staging
                    source = client.get_content_path(torrent)
                    if not source.exists():
                        staging_dirs = [
                            settings.staging_dir / settings.movies_dir_name,
                            settings.staging_dir / settings.tvshows_dir_name,
                            settings.ingest_dir,
                        ]
                        found_in_staging = any(
                            (d / source.name).exists() for d in staging_dirs
                        )
                        if found_in_staging:
                            log.info("already_in_staging", name=name)
                            tracker.mark_ingested(torrent_hash, name, "found_in_staging")
                            report.skip_count += 1
                        else:
                            log.warning("content_missing", name=name, path=str(source))
                            content_missing_count += 1
                            report.skip_count += 1
                            report.warnings.append(f"{name}: content path missing ({source})")
                        continue

                    # Destination in 097-TEMP/ (sort picks up from here)
                    dest = ingest_dir / source.name
                    if dest.exists():
                        log.info("already_exists", name=name, dest=str(dest))
                        report.skip_count += 1
                        tracker.mark_ingested(torrent_hash, name, "skipped_exists")
                        continue

                    # Check disk space
                    source_size = _get_dir_size(source)
                    if not _check_disk_space(ingest_dir, source_size, settings.min_free_space_staging_gb):
                        log.warning("insufficient_space", name=name, size_mb=source_size // (1024 * 1024))
                        report.skip_count += 1
                        report.warnings.append(f"{name}: insufficient disk space")
                        continue

                    # Transfer
                    is_copy = client.is_seeding(torrent)
                    action = "copied" if is_copy else "moved"
                    success = transfer_torrent(source, dest, copy=is_copy, dry_run=dry_run)

                    if success:
                        report.success_count += 1
                        report.details.append(f"{name} → {action}")
                        if not dry_run:
                            tracker.mark_ingested(torrent_hash, name, action)
                    else:
                        report.error_count += 1
                        report.details.append(f"{name}: transfer failed")

                except Exception as exc:
                    torrent_name = getattr(torrent, "name", "unknown")
                    log.error("torrent_failed", name=torrent_name, error=str(exc), exc_info=True)
                    report.error_count += 1
                    report.details.append(f"{torrent_name}: {exc}")
                    continue
```

- [ ] **Step 3: Replace outer except with typed catches**

Replace the outer `except Exception as e:` block (lines 291-312) with specific exception types and actionable messages:

```python
    except QBitAuthLockoutError as e:
        log.exception("ingest_failed", error=str(e))
        report.error_count += 1
        report.details.append(f"qBittorrent auth lockout active: {e}")
    except qbittorrentapi.LoginFailed as e:
        log.exception("ingest_failed", error=str(e))
        report.error_count += 1
        report.details.append(
            f"qBittorrent login failed: {e}. "
            "Fix: check QBIT_USERNAME/QBIT_PASSWORD in .env"
        )
    except (qbittorrentapi.APIConnectionError, requests.ConnectionError) as e:
        log.exception("ingest_failed", error=str(e))
        report.error_count += 1
        report.details.append(
            f"qBittorrent unreachable: {e}. "
            "Fix: verify qBit is running and Web UI is enabled."
        )
    except qbittorrentapi.Forbidden403Error as e:
        log.exception("ingest_failed", error=str(e))
        report.error_count += 1
        report.details.append(
            f"qBittorrent auth blocked (IP banned): {e}. "
            "Fix: unban IP in qBit > Preferences > Web UI > IP Banning, "
            "or wait for the ban to expire."
        )
    except Exception as e:
        log.exception("ingest_failed", error=str(e))
        report.error_count += 1
        report.details.append(f"Ingest failed: {type(e).__name__}: {e}")
```

Note: Keep a final `except Exception` as a safety catch-all, but now the common cases are handled explicitly with `isinstance()`.

- [ ] **Step 4: Add `import qbittorrentapi` at the top**

Add to the imports at the top of `ingest.py`:

```python
import qbittorrentapi
import requests
```

- [ ] **Step 5: Run the new tests**

Run: `python -m pytest tests/ingest/test_ingest.py::TestRunIngest::test_one_torrent_failure_does_not_block_others tests/ingest/test_ingest.py::TestRunIngest::test_login_failed_actionable_message tests/ingest/test_ingest.py::TestRunIngest::test_api_connection_error_actionable_message -v`

Expected: PASS

- [ ] **Step 6: Run full ingest test suite**

Run: `python -m pytest tests/ingest/ -v`

Expected: All tests pass (existing + new)

- [ ] **Step 7: Run full test suite for regressions**

Run: `python -m pytest tests/ -x -q`

Expected: 994+ passed, 0 failed

- [ ] **Step 8: Commit**

```bash
git add personalscraper/ingest/ingest.py
git commit -m "v11.1.2: Restructure run_ingest with per-torrent isolation and typed exceptions"
```

## Task 3: Update IMPLEMENTATION.md

- [ ] **Step 1: Add V11 Phase 1 entry**

Add V11 section to `docs/IMPLEMENTATION.md` tracking phase 1 as complete.

- [ ] **Step 2: Commit**

```bash
git add -f docs/IMPLEMENTATION.md
git commit -m "v11.1.3: Update IMPLEMENTATION.md — Phase 1 complete"
```
