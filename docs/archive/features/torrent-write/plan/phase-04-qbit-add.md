# Phase 04 — `QBitClient.add()` Implementation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Implement `QBitClient.add()` and `_limit_kwargs()` helper. qBit becomes the first client composing `TorrentAdder`. 1 commit.

**D10 check:** During implementation, confirm whether `add()` needs a `save_path` default from `TorrentClientEntry`. If `torrents_add` requires a `savepath` argument when no category default is configured, add `save_path: str | None = None` to `TorrentClientEntry` in `conf/models/api_config.py` and pass it as `savepath=entry.save_path` when not `None`. If `torrents_add` works without it (qBit uses its own default download path), leave `TorrentClientEntry` unchanged. Document the decision with a comment in the implementation.

**Tech Stack:** `qbittorrentapi`, `unittest.mock`, pytest

---

## Gate

- `TorrentItem.tags` field present; `TorrentAdder`/`TorrentLimiter` importable.
- `make check` passes.

---

## Files

- Modify: `personalscraper/api/torrent/qbittorrent.py`
- Create: `tests/unit/test_qbittorrent_add.py`

---

## Steps

- [ ] **1. Write failing tests** in `tests/unit/test_qbittorrent_add.py`:

```python
"""Tests for QBitClient.add() — DESIGN D1/D6/D7/D8."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest, qbittorrentapi
from personalscraper.api._contracts import ApiError
from personalscraper.api.torrent._base import TorrentLimits, TorrentSource
from personalscraper.api.torrent._contracts import TorrentAdder
from personalscraper.api.torrent.qbittorrent import QBitClient

MAGNET = "magnet:?xt=urn:btih:aabbcc112233ddeeff00112233445566778899aa&dn=t"

def _c():
    c = QBitClient("localhost", 8080, "u", "p"); c._client = MagicMock(); return c

def test_qbit_is_torrent_adder(): assert isinstance(_c(), TorrentAdder)

def test_add_magnet_calls_torrents_add():
    c = _c(); c._client.torrents_add.return_value = "Ok"
    c.add(TorrentSource.from_magnet(MAGNET), category="movies", tags=["action"])
    kw = c._client.torrents_add.call_args[1]
    assert kw["urls"] == MAGNET and kw["category"] == "movies" and kw["tags"] == ["action"]

def test_add_file_bytes_uses_torrent_files():
    c = _c(); c._client.torrents_add.return_value = "Ok"
    c.add(TorrentSource.from_file(b"bytes"))
    kw = c._client.torrents_add.call_args[1]
    assert kw.get("torrent_files") == b"bytes" and not kw.get("urls")

def test_add_paused_forwarded():
    c = _c(); c._client.torrents_add.return_value = "Ok"
    c.add(TorrentSource.from_magnet(MAGNET), paused=True)
    assert c._client.torrents_add.call_args[1]["is_paused"] is True

def test_add_returns_info_hash():
    c = _c(); c._client.torrents_add.return_value = "Ok"
    src = TorrentSource.from_magnet(MAGNET)
    assert c.add(src) == src.info_hash

def test_add_idempotent_on_duplicate():
    c = _c(); c._client.torrents_add.return_value = "Fails."
    src = TorrentSource.from_magnet(MAGNET)
    assert c.add(src) == src.info_hash  # no exception, returns hash (D7)

def test_add_with_limits_sets_ratio_and_upload():
    c = _c(); c._client.torrents_add.return_value = "Ok"
    c.add(TorrentSource.from_magnet(MAGNET), limits=TorrentLimits(ratio=2.0, up_bytes_per_s=1024))
    kw = c._client.torrents_add.call_args[1]
    assert kw.get("ratio_limit") == 2.0 and kw.get("upload_limit") == 1024

def test_add_forbidden_raises_api_error():
    c = _c(); c._client.torrents_add.side_effect = qbittorrentapi.Forbidden403Error("ban")
    with pytest.raises(ApiError) as ei: c.add(TorrentSource.from_magnet(MAGNET))
    assert ei.value.http_status == 403
```

- [ ] **2. Run — confirm AttributeError**

```bash
cd /Users/izno/dev/PersonnalScaper && pytest tests/unit/test_qbittorrent_add.py -q 2>&1 | tail -5
```

- [ ] **3. Update `qbittorrent.py` class declaration** to include `TorrentAdder, TorrentLimiter`:

Add imports (after existing imports in qbittorrent.py):

```python
from collections.abc import Sequence
from personalscraper.api.torrent._base import TorrentLimits, TorrentSource
from personalscraper.api.torrent._contracts import TorrentAdder, TorrentLimiter
```

Change the class header:

```python
class QBitClient(
    TorrentLister, TorrentInspector, AuthenticatedClient,
    TorrentStateInspector, TorrentController, TorrentAdder, TorrentLimiter,
):
```

Update the class docstring to list `TorrentAdder` and `TorrentLimiter` in the capabilities list.

- [ ] **4. Add `add()` method** in the `# -- Protocol: mutations` section of `QBitClient`:

```python
    def add(
        self,
        source: TorrentSource,
        *,
        category: str | None = None,
        tags: Sequence[str] = (),
        paused: bool = False,
        limits: TorrentLimits | None = None,
    ) -> str:
        """Add a torrent to qBittorrent (D1/D6/D7/D8).

        Applies category, tags, paused state, and limits inline in one
        torrents_add call. Duplicate adds return the existing info_hash
        (idempotent, D7). 401/403 surfaces as ApiError (observable).

        Args:
            source: TorrentSource — magnet or file bytes.
            category: Category label.
            tags: Tag strings.
            paused: Add in paused state if True.
            limits: Optional transfer limits applied inline.

        Returns:
            info_hash of the added (or already-present) torrent.

        Raises:
            ApiError: qBittorrent returns 401 or 403.
        """
        try:
            kwargs: dict[str, object] = {
                "category": category, "tags": list(tags), "is_paused": paused,
                **_limit_kwargs(limits),
            }
            if source.magnet is not None:
                kwargs["urls"] = source.magnet
            else:
                kwargs["torrent_files"] = source.file_bytes
            self._client.torrents_add(**kwargs)
            # "Ok" = success, "Fails." = duplicate → both are idempotent success (D7)
            return source.info_hash
        except qbittorrentapi.Forbidden403Error as exc:
            raise ApiError(provider=ProviderName.QBITTORRENT, http_status=403,
                           message=f"qBittorrent add forbidden: {exc}") from exc
        except qbittorrentapi.LoginFailed as exc:
            raise ApiError(provider=ProviderName.QBITTORRENT, http_status=401,
                           message=f"qBittorrent add unauthorized: {exc}") from exc
```

- [ ] **5. Add `_limit_kwargs()` helper** at the bottom of `qbittorrent.py`:

```python
def _limit_kwargs(limits: TorrentLimits | None) -> dict[str, object]:
    """Build qBittorrent limit kwargs from a TorrentLimits instance.

    Only non-None fields are included to avoid overwriting client defaults
    with zeros.

    Args:
        limits: TorrentLimits or None.

    Returns:
        Dict of torrents_add kwargs for limits; empty if limits is None.
    """
    if limits is None:
        return {}
    out: dict[str, object] = {}
    if limits.ratio is not None:
        out["ratio_limit"] = limits.ratio
    if limits.seed_time_minutes is not None:
        out["seeding_time_limit"] = limits.seed_time_minutes * 60
    if limits.up_bytes_per_s is not None:
        out["upload_limit"] = limits.up_bytes_per_s
    if limits.down_bytes_per_s is not None:
        out["download_limit"] = limits.down_bytes_per_s
    return out
```

- [ ] **6. Run tests — expect all pass**

```bash
cd /Users/izno/dev/PersonnalScaper && pytest tests/unit/test_qbittorrent_add.py tests/unit/test_qbittorrent.py -q 2>&1 | tail -8
```

- [ ] **7. Lint**

```bash
cd /Users/izno/dev/PersonnalScaper && make lint 2>&1 | tail -5
```

- [ ] **8. Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add personalscraper/api/torrent/qbittorrent.py tests/unit/test_qbittorrent_add.py && git commit -m "feat(torrent-write): implement QBitClient.add() with idempotence and inline limits (D1/D7/D8)"
```
