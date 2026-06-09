# Phase 1 — Error types: `TrackerError` + `TrackerConfigIssue` + `TrackerConfigError`

## Gate

This is the first phase. No prior phase dependency.

**Pre-flight:**

```bash
python -c "from personalscraper.api.tracker._errors import TrackerAuthError; print('ok')"
# Expected: ok
```

---

## Goal

Extend `personalscraper/api/tracker/_errors.py` with three new symbols:

- `TrackerError` — base exception for the tracker family (analogous to `RegistryError` in the metadata family).
- `TrackerConfigIssue` — frozen dataclass carrying one boot-validation finding (severity + code + provider + message).
- `TrackerConfigError(TrackerError)` — aggregated error raised at boot when any error-severity issue is found.

The two existing symbols (`TrackerAuthError`, `TorrentFetchError`) are **not changed**.

---

## Files

- **Modify:** `personalscraper/api/tracker/_errors.py`
- **Create:** `tests/unit/test_tracker_config_errors.py`

---

## Tasks

### Task 1.1 — Add new symbols to `_errors.py`

Open `personalscraper/api/tracker/_errors.py`. After the existing imports block and before `class TrackerAuthError`, insert:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
```

Then append the following **after** the existing `TorrentFetchError` class and before `__all__`:

```python
# ---------------------------------------------------------------------------
# Boot-validation error hierarchy — tracker-wiring RP5a
# ---------------------------------------------------------------------------


class TrackerError(Exception):
    """Base exception for the tracker provider family.

    All tracker-specific errors derive from this class, mirroring the
    ``RegistryError`` base in ``api/metadata/registry/_errors.py``.
    Catching ``TrackerError`` handles every tracker-family exception without
    accidentally swallowing unrelated ``Exception`` subclasses.
    """


@dataclass(frozen=True)
class TrackerConfigIssue:
    """One boot-validation finding for the tracker factory (DESIGN §Components.2).

    Attributes:
        severity: ``"error"`` → fatal (raises :class:`TrackerConfigError`);
            ``"warning"`` → logged, non-fatal.
        code: Machine-readable issue identifier.
            ``missing_credentials`` — tracker enabled but API key absent.
            ``protocol_mismatch`` — built client fails ``TorrentSearchable`` check.
            ``unknown_provider`` — name in priority not present in providers.
            ``disabled_in_priority`` — disabled tracker referenced in priority
                when ≥1 tracker is active (warning only).
        provider: Tracker name (e.g. ``"lacale"``), or ``None`` for issues
            not tied to a single provider.
        message: Human-readable description for operator logs / error output.
    """

    severity: Literal["error", "warning"]
    code: Literal[
        "missing_credentials",
        "protocol_mismatch",
        "unknown_provider",
        "disabled_in_priority",
    ]
    provider: str | None
    message: str


class TrackerConfigError(TrackerError):
    """Aggregated, fail-loud tracker boot-config error (parity with RegistryConfigError).

    Carries every error-severity :class:`TrackerConfigIssue` so the operator
    sees all problems at once (never fail-fast on the first). Raised by
    :func:`~personalscraper.api.tracker._factory.build_tracker_registry` at the
    composition root when any error-severity issue is found.

    Attributes:
        issues: List of all error-severity issues found during boot validation.
    """

    def __init__(self, issues: list[TrackerConfigIssue]) -> None:
        """Initialise with the aggregated list of error-severity issues.

        Args:
            issues: Non-empty list of :class:`TrackerConfigIssue` instances,
                all with ``severity == "error"``.
        """
        self.issues = issues
        codes = ", ".join(f"{i.provider or '?'}:{i.code}" for i in issues)
        super().__init__(f"Tracker boot validation failed ({len(issues)} error(s)): {codes}")
```

Update `__all__` at the bottom of the file to include the new names:

```python
__all__ = [
    "TrackerAuthError",
    "TorrentFetchError",
    "TrackerError",
    "TrackerConfigIssue",
    "TrackerConfigError",
]
```

- [ ] Apply the edit above to `personalscraper/api/tracker/_errors.py`.
- [ ] Verify:
  ```bash
  python -c "
  from personalscraper.api.tracker._errors import (
      TrackerError, TrackerConfigIssue, TrackerConfigError
  )
  issue = TrackerConfigIssue(severity='error', code='missing_credentials',
                             provider='lacale', message='no key')
  err = TrackerConfigError([issue])
  assert isinstance(err, TrackerError)
  assert isinstance(err, Exception)
  assert err.issues[0].code == 'missing_credentials'
  print('ok')
  "
  # Expected: ok
  ```

---

### Task 1.2 — Write unit tests

- [ ] **Create** `tests/unit/test_tracker_config_errors.py`:

```python
"""Unit tests for tracker boot-validation error types — tracker-wiring RP5a.

Covers: TrackerError base, TrackerConfigIssue frozen dataclass,
TrackerConfigError aggregation and message formatting.
"""
from __future__ import annotations

import pytest

from personalscraper.api.tracker._errors import (
    TrackerAuthError,
    TrackerConfigError,
    TrackerConfigIssue,
    TrackerError,
    TorrentFetchError,
)


class TestTrackerErrorBase:
    def test_is_exception_subclass(self) -> None:
        assert issubclass(TrackerError, Exception)

    def test_tracker_config_error_is_tracker_error(self) -> None:
        issue = TrackerConfigIssue(
            severity="error", code="missing_credentials",
            provider="lacale", message="no key",
        )
        err = TrackerConfigError([issue])
        assert isinstance(err, TrackerError)

    def test_existing_errors_unaffected(self) -> None:
        """TrackerAuthError and TorrentFetchError still exist and are ApiError subclasses."""
        from personalscraper.api._contracts import ApiError
        assert issubclass(TrackerAuthError, ApiError)
        assert issubclass(TorrentFetchError, ApiError)


class TestTrackerConfigIssue:
    def test_frozen_dataclass(self) -> None:
        issue = TrackerConfigIssue(
            severity="error", code="missing_credentials",
            provider="lacale", message="LACALE_API_KEY absent",
        )
        with pytest.raises(Exception):
            issue.severity = "warning"  # type: ignore[misc]

    def test_warning_severity(self) -> None:
        issue = TrackerConfigIssue(
            severity="warning", code="disabled_in_priority",
            provider="lacale", message="disabled but in priority",
        )
        assert issue.severity == "warning"

    def test_provider_none(self) -> None:
        issue = TrackerConfigIssue(
            severity="error", code="unknown_provider",
            provider=None, message="ghost in priority list",
        )
        assert issue.provider is None

    def test_all_error_codes_accepted(self) -> None:
        for code in ("missing_credentials", "protocol_mismatch",
                     "unknown_provider", "disabled_in_priority"):
            TrackerConfigIssue(severity="error", code=code,  # type: ignore[arg-type]
                               provider="x", message="m")


class TestTrackerConfigError:
    def test_carries_issues(self) -> None:
        issues = [
            TrackerConfigIssue(severity="error", code="missing_credentials",
                               provider="lacale", message="no key"),
            TrackerConfigIssue(severity="error", code="unknown_provider",
                               provider=None, message="ghost"),
        ]
        err = TrackerConfigError(issues)
        assert err.issues is issues
        assert len(err.issues) == 2

    def test_message_includes_count(self) -> None:
        issue = TrackerConfigIssue(severity="error", code="protocol_mismatch",
                                   provider="c411", message="not searchable")
        err = TrackerConfigError([issue])
        assert "1 error" in str(err)
        assert "c411" in str(err)

    def test_catchable_as_tracker_error(self) -> None:
        issue = TrackerConfigIssue(severity="error", code="missing_credentials",
                                   provider="lacale", message="no key")
        with pytest.raises(TrackerError):
            raise TrackerConfigError([issue])
```

- [ ] **Run:**
  ```bash
  python -m pytest tests/unit/test_tracker_config_errors.py -v
  # Expected: 10 passed, 0 failed
  ```

---

### Task 1.3 — Commit

```bash
git add personalscraper/api/tracker/_errors.py \
        tests/unit/test_tracker_config_errors.py
git commit -m "feat(tracker-wiring): TrackerError + TrackerConfigIssue + TrackerConfigError"
```

---

## Gate exit checklist

- [ ] `python -c "from personalscraper.api.tracker._errors import TrackerConfigError; print('ok')"` → `ok`
- [ ] `pytest tests/unit/test_tracker_config_errors.py` → 10 passed, 0 failed
- [ ] Existing tracker error tests unaffected: `pytest tests/unit/test_tracker_errors.py` → all pass
- [ ] Commit SHA recorded
