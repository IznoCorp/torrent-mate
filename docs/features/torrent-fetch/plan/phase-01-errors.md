# Phase 1 — Errors module

## Gate

This is the first phase. No prior phase dependency.

**Pre-flight check:**

```bash
python -c "from personalscraper.api._contracts import ApiError; print('ok')"
```

Expected: `ok`

---

## Goal

Create `api/tracker/_errors.py` with two `ApiError` subclasses used by all subsequent phases:

- `TrackerAuthError` — raised on HTTP 401/403 from a download (not a search)
- `TorrentFetchError` — raised on bad/empty/oversize body, hash mismatch, missing url/provider

**Why a separate file:** mirrors the circular-import hygiene pattern from `api/torrent/_errors.py` — keeping `ApiError` subclasses out of `_base.py` prevents circular imports when `_fetch.py` imports both `_base.py` and the errors.

---

## Files

- **Create:** `personalscraper/api/tracker/_errors.py`
- **Create:** `tests/unit/test_tracker_errors.py`

---

## Tasks

### Task 1.1 — Create `_errors.py`

- [ ] **Create** `personalscraper/api/tracker/_errors.py` with this exact content:

```python
"""Tracker-family typed errors.

Kept separate from ``_base.py`` to avoid a circular import: ``_fetch.py``
imports both ``_base.py`` (for TrackerResult) and these error types, and
``_base.py`` must not import from ``_fetch.py``. Same hygiene pattern as
``api/torrent/_errors.py``.

Design: §5.3 (D4).
"""

from __future__ import annotations

from personalscraper.api._contracts import ApiError


class TrackerAuthError(ApiError):
    """Authentication failure on a tracker download (HTTP 401 or 403).

    Raised by ``fetch_torrent_source`` when the tracker returns 401/403,
    signalling an expired token or invalid API key. Callers (RP7 and
    beyond) can catch this to trigger a credential refresh or alert.

    Inherits ``ApiError``'s ``__init__``: ``provider``, ``http_status``,
    ``provider_code``, ``message``.
    """


class TorrentFetchError(ApiError):
    """Unrecoverable error fetching or validating a ``.torrent`` file.

    Raised by ``fetch_torrent_source`` / ``resolve_source`` for:
    - Empty body from a successful HTTP response
    - Body exceeds the size cap
    - Body is not a valid bencoded dict (HTML-200 login wall, JSON error)
    - Bencoded dict has no top-level ``info`` key
    - Derived info_hash does not match the expected hash
    - ``TrackerResult.download_url`` is None
    - ``TrackerResult.provider`` key not found in the transports map

    Inherits ``ApiError``'s ``__init__``: ``provider``, ``http_status``,
    ``provider_code``, ``message``.
    """


__all__ = ["TrackerAuthError", "TorrentFetchError"]
```

- [ ] **Verify it imports cleanly:**

```bash
python -c "from personalscraper.api.tracker._errors import TrackerAuthError, TorrentFetchError; print('ok')"
```

Expected: `ok`

---

### Task 1.2 — Write tests for the error types

- [ ] **Create** `tests/unit/test_tracker_errors.py`:

```python
"""Tests for api/tracker/_errors.py.

Design: §5.3 (D4) — TrackerAuthError and TorrentFetchError are field-free
ApiError subclasses; they inherit __init__, __eq__, and str() from ApiError.
Contract: construction, isinstance hierarchy, and message propagation.
"""

from __future__ import annotations

import pytest

from personalscraper.api._contracts import ApiError
from personalscraper.api.tracker._errors import TorrentFetchError, TrackerAuthError


class TestTrackerAuthError:
    """TrackerAuthError is an ApiError subclass for 401/403 download failures."""

    def test_is_api_error(self) -> None:
        """TrackerAuthError must be catchable as ApiError."""
        err = TrackerAuthError(provider="c411", http_status=401, provider_code=0, message="Unauthorized")
        assert isinstance(err, ApiError)

    def test_is_tracker_auth_error(self) -> None:
        """isinstance check works for the concrete type."""
        err = TrackerAuthError(provider="lacale", http_status=403, provider_code=0, message="Forbidden")
        assert isinstance(err, TrackerAuthError)

    def test_http_status_preserved(self) -> None:
        """http_status is stored and accessible."""
        err = TrackerAuthError(provider="c411", http_status=401, provider_code=0, message="Unauthorized")
        assert err.http_status == 401

    def test_message_preserved(self) -> None:
        """The message string is propagated through ApiError.__init__."""
        err = TrackerAuthError(provider="c411", http_status=401, provider_code=0, message="token expired")
        assert "token expired" in str(err)

    def test_403_also_valid(self) -> None:
        """403 Forbidden is a valid auth failure status."""
        err = TrackerAuthError(provider="lacale", http_status=403, provider_code=0, message="Forbidden")
        assert err.http_status == 403


class TestTorrentFetchError:
    """TorrentFetchError is an ApiError subclass for bad/empty/oversize content."""

    def test_is_api_error(self) -> None:
        """TorrentFetchError must be catchable as ApiError."""
        err = TorrentFetchError(provider="c411", http_status=200, provider_code=0, message="empty body")
        assert isinstance(err, ApiError)

    def test_is_torrent_fetch_error(self) -> None:
        """isinstance check works for the concrete type."""
        err = TorrentFetchError(provider="lacale", http_status=200, provider_code=0, message="not a torrent")
        assert isinstance(err, TorrentFetchError)

    def test_message_preserved(self) -> None:
        """Error message describes the failure context."""
        err = TorrentFetchError(
            provider="c411", http_status=200, provider_code=0,
            message="body is not a bencoded dict: b'<html>'"
        )
        assert "bencoded" in str(err)

    def test_not_auth_error(self) -> None:
        """TorrentFetchError must NOT be a TrackerAuthError."""
        err = TorrentFetchError(provider="c411", http_status=200, provider_code=0, message="bad")
        assert not isinstance(err, TrackerAuthError)

    def test_auth_error_not_fetch_error(self) -> None:
        """TrackerAuthError must NOT be a TorrentFetchError."""
        err = TrackerAuthError(provider="c411", http_status=401, provider_code=0, message="auth")
        assert not isinstance(err, TorrentFetchError)
```

- [ ] **Run the tests — verify they PASS:**

```bash
pytest tests/unit/test_tracker_errors.py -v
```

Expected: `10 passed`

---

### Task 1.3 — Commit

- [ ] **Commit:**

```bash
git add personalscraper/api/tracker/_errors.py tests/unit/test_tracker_errors.py
git commit -m "feat(torrent-fetch): tracker error types — TrackerAuthError + TorrentFetchError"
```

---

## Gate exit checklist

- [ ] `python -c "from personalscraper.api.tracker._errors import TrackerAuthError, TorrentFetchError"` → exit 0
- [ ] `pytest tests/unit/test_tracker_errors.py` → 10 passed, 0 failed
- [ ] Commit SHA recorded
