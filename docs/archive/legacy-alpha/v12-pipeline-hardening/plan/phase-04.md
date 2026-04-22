# Phase 4: qBit auth pre-check (bugs #1, #2, #12, #20)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Pre-check qBit accessibility before `auth_log_in()` to detect IP ban without triggering further bans.

**Architecture:** GET `/api/v2/app/version` (no auth needed) before login. 403 = already banned → raise without login attempt.

**Tech Stack:** Python, requests, qbittorrent-api, pytest

---

## Task 1: Write reproducer tests

**Files:**

- Modify: `tests/ingest/test_qbit_client.py`

- [ ] **Step 1: Write failing tests**

```python
class TestPreCheckBan:
    """Tests for qBit pre-check before auth_log_in."""

    @patch("personalscraper.ingest.qbit_client.requests.get")
    @patch("personalscraper.ingest.qbit_client.qbittorrentapi.Client")
    def test_403_pre_check_skips_login(self, mock_client_cls, mock_get) -> None:
        """When pre-check returns 403, auth_log_in should NOT be called."""
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_get.return_value = mock_resp

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        client = QBitClient(host="localhost", port=8081, username="u", password="p")

        with pytest.raises(qbittorrentapi.Forbidden403Error):
            client.__enter__()

        # auth_log_in must NEVER be called when IP is already banned
        mock_client.auth_log_in.assert_not_called()

    @patch("personalscraper.ingest.qbit_client.requests.get")
    @patch("personalscraper.ingest.qbit_client.qbittorrentapi.Client")
    def test_connection_refused_raises_api_error(self, mock_client_cls, mock_get) -> None:
        """Connection refused on pre-check should raise APIConnectionError."""
        import requests as req
        mock_get.side_effect = req.ConnectionError("Connection refused")

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        client = QBitClient(host="localhost", port=8081, username="u", password="p")

        with pytest.raises(qbittorrentapi.APIConnectionError):
            client.__enter__()

        mock_client.auth_log_in.assert_not_called()

    @patch("personalscraper.ingest.qbit_client.requests.get")
    @patch("personalscraper.ingest.qbit_client.qbittorrentapi.Client")
    def test_200_pre_check_proceeds_to_login(self, mock_client_cls, mock_get) -> None:
        """When pre-check returns 200, auth_log_in should be called normally."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        client = QBitClient(host="localhost", port=8081, username="u", password="p")
        # Remove lockout file if exists (from other tests)
        from personalscraper.ingest.qbit_client import _LOCKOUT_FILE
        _LOCKOUT_FILE.unlink(missing_ok=True)

        client.__enter__()

        mock_client.auth_log_in.assert_called_once()
```

Add necessary imports at the top of the test file:

```python
import qbittorrentapi
import pytest
from personalscraper.ingest.qbit_client import QBitClient
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/ingest/test_qbit_client.py::TestPreCheckBan -v`
Expected: FAIL — current code doesn't do a pre-check, goes straight to `auth_log_in()`

- [ ] **Step 3: Commit**

```bash
git add tests/ingest/test_qbit_client.py
git commit -m "v12.4.1: Add failing tests for qBit pre-check before login"
```

## Task 2: Implement pre-check in **enter**

**Files:**

- Modify: `personalscraper/ingest/qbit_client.py`

- [ ] **Step 1: Add requests import**

Add at the top of `qbit_client.py`:

```python
import requests
```

- [ ] **Step 2: Add pre-check before auth_log_in**

In `__enter__()`, AFTER the lockout file check (line 88-90) and BEFORE `auth_log_in()` (line 93), add:

```python
        # Pre-check: detect IP ban without attempting auth
        # /api/v2/app/version requires no auth — 403 means IP is banned
        try:
            resp = requests.get(
                f"http://{self._client.host}:{self._client.port}/api/v2/app/version",
                timeout=5,
            )
            if resp.status_code == 403:
                log.error(
                    "qbit_ip_banned_pre_check",
                    hint="IP is already banned. Unban in qBit > Preferences > Web UI > IP Banning.",
                )
                raise qbittorrentapi.Forbidden403Error(
                    "IP is already banned by qBittorrent. "
                    "Unban in Preferences > Web UI > IP Banning, or restart qBit."
                )
        except requests.ConnectionError as exc:
            raise qbittorrentapi.APIConnectionError(
                f"qBittorrent unreachable at {self._client.host}:{self._client.port}: {exc}"
            )

        try:
            self._client.auth_log_in()
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/ingest/test_qbit_client.py::TestPreCheckBan -v`
Expected: PASS

- [ ] **Step 4: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add personalscraper/ingest/qbit_client.py
git commit -m "v12.4.2: Add qBit pre-check — detect IP ban before login attempt"
```

## Task 3: Update IMPLEMENTATION.md

- [ ] **Step 1: Mark Phase 4 complete**
- [ ] **Step 2: Commit**

```bash
git add -f docs/IMPLEMENTATION.md
git commit -m "v12.4.3: Update IMPLEMENTATION.md — Phase 4 complete"
```
