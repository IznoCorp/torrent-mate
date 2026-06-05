# Phase 05 — `QBitClient.apply_limits()` + Composition Assertions

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Implement `QBitClient.apply_limits()` (TorrentLimiter). Add `TorrentAdder`/`TorrentLimiter` isinstance assertions to the composition test. 1 commit.

**Tech Stack:** `qbittorrentapi`, `unittest.mock`, pytest

---

## Gate

- `QBitClient.add()` and `_limit_kwargs()` present and tested.
- `make lint` passes.

---

## Files

- Modify: `personalscraper/api/torrent/qbittorrent.py`
- Modify: `tests/unit/test_qbittorrent_add.py`
- Modify: `tests/unit/test_torrent_capabilities_composition.py`

---

## Steps

- [ ] **1. Write failing tests** — add class to `tests/unit/test_qbittorrent_add.py`:

```python
from personalscraper.api.torrent._contracts import TorrentLimiter

class TestQBitClientApplyLimits:
    def test_qbit_is_torrent_limiter(self): assert isinstance(_c(), TorrentLimiter)

    def test_apply_ratio_calls_set_share_limits(self):
        c = _c()
        c.apply_limits("abc", TorrentLimits(ratio=1.5))
        c._client.torrents_set_share_limits.assert_called_once_with(
            torrent_hashes="abc", ratio_limit=1.5, seeding_time_limit=-2)

    def test_apply_upload_calls_set_upload_limit(self):
        c = _c()
        c.apply_limits("abc", TorrentLimits(up_bytes_per_s=512))
        c._client.torrents_set_upload_limit.assert_called_once_with(
            torrent_hashes="abc", limit=512)

    def test_apply_download_calls_set_download_limit(self):
        c = _c()
        c.apply_limits("abc", TorrentLimits(down_bytes_per_s=1024))
        c._client.torrents_set_download_limit.assert_called_once_with(
            torrent_hashes="abc", limit=1024)

    def test_all_none_is_noop(self):
        c = _c()
        c.apply_limits("abc", TorrentLimits())
        c._client.torrents_set_share_limits.assert_not_called()
        c._client.torrents_set_upload_limit.assert_not_called()
        c._client.torrents_set_download_limit.assert_not_called()

    def test_seed_time_converted_to_seconds(self):
        c = _c()
        c.apply_limits("abc", TorrentLimits(seed_time_minutes=30))
        kw = c._client.torrents_set_share_limits.call_args[1]
        assert kw["seeding_time_limit"] == 1800
```

- [ ] **2. Run — confirm AttributeError**

```bash
cd /Users/izno/dev/PersonnalScaper && pytest tests/unit/test_qbittorrent_add.py::TestQBitClientApplyLimits -q 2>&1 | tail -5
```

- [ ] **3. Implement `apply_limits()` in `QBitClient`** (in the mutations section):

```python
    def apply_limits(self, info_hash: str, limits: TorrentLimits) -> None:
        """Apply transfer limits to an existing torrent (D2/§5.4).

        Only non-None fields trigger API calls. All-None TorrentLimits is
        a no-op.

        Args:
            info_hash: Lowercase hex info_hash of the target torrent.
            limits: Limits to apply.
        """
        if limits.ratio is not None or limits.seed_time_minutes is not None:
            self._client.torrents_set_share_limits(
                torrent_hashes=info_hash,
                ratio_limit=limits.ratio if limits.ratio is not None else -2,
                seeding_time_limit=(
                    limits.seed_time_minutes * 60
                    if limits.seed_time_minutes is not None
                    else -2
                ),
            )
        if limits.up_bytes_per_s is not None:
            self._client.torrents_set_upload_limit(
                torrent_hashes=info_hash, limit=limits.up_bytes_per_s)
        if limits.down_bytes_per_s is not None:
            self._client.torrents_set_download_limit(
                torrent_hashes=info_hash, limit=limits.down_bytes_per_s)
```

- [ ] **4. Add composition assertions** to `tests/unit/test_torrent_capabilities_composition.py`:

```python
from personalscraper.api.torrent._contracts import TorrentAdder, TorrentLimiter

def test_qbit_client_is_torrent_adder() -> None:
    """QBitClient satisfies TorrentAdder."""
    assert isinstance(_qbit(), TorrentAdder)

def test_qbit_client_is_torrent_limiter() -> None:
    """QBitClient satisfies TorrentLimiter."""
    assert isinstance(_qbit(), TorrentLimiter)
```

- [ ] **5. Run all affected tests**

```bash
cd /Users/izno/dev/PersonnalScaper && pytest tests/unit/test_qbittorrent_add.py tests/unit/test_torrent_capabilities_composition.py -q 2>&1 | tail -8
```

Expected: all pass.

- [ ] **6. Full quality gate**

```bash
cd /Users/izno/dev/PersonnalScaper && make check 2>&1 | tail -10
```

Expected: exits 0.

- [ ] **7. Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add personalscraper/api/torrent/qbittorrent.py tests/unit/test_qbittorrent_add.py tests/unit/test_torrent_capabilities_composition.py && git commit -m "feat(torrent-write): implement QBitClient.apply_limits() and add composition assertions"
```
