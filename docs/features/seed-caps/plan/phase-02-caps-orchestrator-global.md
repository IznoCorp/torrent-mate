# Phase 2 — Per-torrent caps + global caps (protocol, qBit impl, wiring)

**Gate**: Phase 1 complete — `BandwidthConfig` importable from `personalscraper.conf.models.acquire`, `DownloadMarksStore` importable from `personalscraper.acquire._download_marks`, `download_marks` table schema exists (migration 014 applied).

## Scope

New `GlobalRateLimiter` runtime-checkable protocol, qBittorrent implementation via `transfer_set_upload_limit` / `transfer_set_download_limit`, per-torrent caps wired into `GrabOrchestrator.add()` path, global caps applied at acquire run entry in `AcquisitionService`.

---

## Sub-phase 2.1: GlobalRateLimiter protocol + qBittorrent implementation

**Commit**: `feat(seed-caps): add GlobalRateLimiter protocol + qBittorrent global limits impl`

### Files
- **Modify**: `personalscraper/api/torrent/_contracts.py` — add `GlobalRateLimiter` protocol
- **Modify**: `personalscraper/api/torrent/qbittorrent.py` — implement `apply_global_limits`
- **Create**: `tests/api/torrent/test_global_rate_limiter.py`

### Implementation

**Protocol** in `_contracts.py` (after `TorrentLimiter`, around line 182):

```python
@runtime_checkable
class GlobalRateLimiter(Protocol):
    """Capability — apply global transfer limits (O4/D5).

    Composed by QBitClient only. Transmission deliberately omits this.
    Callers gate via ``isinstance(client, GlobalRateLimiter)``.
    """

    def apply_global_limits(
        self,
        up_bytes_per_s: int | None = None,
        down_bytes_per_s: int | None = None,
    ) -> None:
        """Set the client's global transfer limits.

        A ``None`` field is a no-op — the current client setting is left
        untouched (D2: never reset limits the operator set by hand).
        """
        ...
```

Add `"GlobalRateLimiter"` to `__all__`.

**qBittorrent impl** in `qbittorrent.py`: Add `GlobalRateLimiter` to `QBitClient` bases and implement:

```python
def apply_global_limits(
    self,
    up_bytes_per_s: int | None = None,
    down_bytes_per_s: int | None = None,
) -> None:
    """Set global transfer limits via qBittorrent API (O4/D5)."""
    if down_bytes_per_s is not None:
        self._client.transfer_set_download_limit(down_bytes_per_s)
    if up_bytes_per_s is not None:
        self._client.transfer_set_upload_limit(up_bytes_per_s)
```

### Tests

In `tests/api/torrent/test_global_rate_limiter.py`:
- `test_qbit_is_global_rate_limiter` — `QBitClient` satisfies `isinstance(client, GlobalRateLimiter)`
- `test_both_set` — mocks `_client`, verifies both transfer_set_* called with correct args
- `test_down_only` — `up=None` → `transfer_set_upload_limit` NOT called
- `test_both_none_noops` — neither method called when both are None

### Gate
```bash
pytest tests/api/torrent/test_global_rate_limiter.py -v   # all pass
```

---

## Sub-phase 2.2: Orchestrator per-torrent caps wiring

**Commit**: `feat(seed-caps): wire per-torrent bandwidth caps into GrabOrchestrator.add()`

### Files
- **Modify**: `personalscraper/acquire/orchestrator.py` — `__init__` accepts `BandwidthConfig`, apply at add time
- **Modify**: `personalscraper/acquire/_factory.py:169` — wire `config.acquire.bandwidth` into constructor
- **Create**: `tests/acquire/test_orchestrator_bandwidth_caps.py`

### Implementation

In `orchestrator.py.__init__`, add parameter `bandwidth: BandwidthConfig` (required), store as `self._bandwidth`, add flag `self._limits_unsupported_warned = False` (D4).

In the add path (around line 890), before `self._torrent_client.add(...)`, build `TorrentLimits` when caps configured:

```python
from personalscraper.api.torrent._base import TorrentLimits
from personalscraper.api.torrent._contracts import TorrentLimiter

limits: TorrentLimits | None = None
bw = self._bandwidth
if bw.per_torrent_down is not None or bw.per_torrent_up is not None:
    if isinstance(self._torrent_client, TorrentLimiter):
        limits = TorrentLimits(
            down_bytes_per_s=bw.per_torrent_down,
            up_bytes_per_s=bw.per_torrent_up,
            # ratio/seed_time_minutes stay None — out of scope (#173/#174)
        )
    elif not self._limits_unsupported_warned:
        self._limits_unsupported_warned = True
        structlog.get_logger(__name__).warning(
            "acquire.grab.limits_unsupported",
            client_type=type(self._torrent_client).__name__,
        )

info_hash = self._torrent_client.add(source, category=None, tags=[top.provider], limits=limits)
```

In `_factory.py:169`, add `bandwidth=config.acquire.bandwidth` to `GrabOrchestrator(...)`.

### Tests

In `tests/acquire/test_orchestrator_bandwidth_caps.py`, extract limits-building logic into `_build_limits(bw, *, client_is_limiter: bool) -> TorrentLimits | None` and test:
- No config → `None`
- Down-only → correct `down_bytes_per_s`, `up_bytes_per_s is None`
- Up-only → correct `up_bytes_per_s`, `down_bytes_per_s is None`
- Both → both fields set
- `ratio` and `seed_time_minutes` always `None` (§7)
- Unsupported client → `None` (no crash)

### Gate
```bash
pytest tests/acquire/test_orchestrator_bandwidth_caps.py -v   # all pass
make lint                                                       # zero errors
```

---

## Sub-phase 2.3: Global caps call site in AcquisitionService

**Commit**: `feat(seed-caps): apply global bandwidth caps at acquire run start`

### Files
- **Modify**: `personalscraper/acquire/service.py` — apply global caps at run entry
- **Create**: `tests/acquire/test_global_caps_service.py`

### Implementation

In `service.py`, at the top of the acquire run entry method, add (D5):

```python
bw = self._config.acquire.bandwidth
if bw.global_down is not None or bw.global_up is not None:
    from personalscraper.api.torrent._contracts import GlobalRateLimiter

    tc = self._torrent_client  # or stored reference from orchestrator
    if isinstance(tc, GlobalRateLimiter):
        try:
            tc.apply_global_limits(
                down_bytes_per_s=bw.global_down,
                up_bytes_per_s=bw.global_up,
            )
        except ApiError as exc:
            structlog.get_logger(__name__).warning(
                "acquire.global_limits.failed", error=str(exc),
            )
```

Note: The exact torrent client reference access depends on how `AcquisitionService` holds it. Use the stored reference; if it's via `self._orchestrator._torrent_client`, access it there.

### Tests

In `tests/acquire/test_global_caps_service.py`, extract `_apply_global_caps(client, bw)` and test:
- Applies when client supports `GlobalRateLimiter` and caps configured
- Noop when no caps configured (all None)
- Noop when client unsupported (no crash — D4/D5)
- Fail-soft on `ApiError` (no raise — D5)

### Gate
```bash
pytest tests/acquire/test_global_caps_service.py tests/acquire/test_orchestrator_bandwidth_caps.py tests/api/torrent/test_global_rate_limiter.py -v
make lint
python -c "import personalscraper"
```

---

## Phase 2 Gate (before proceeding to Phase 3)

```bash
make lint
pytest tests/acquire/test_orchestrator_bandwidth_caps.py tests/acquire/test_global_caps_service.py tests/api/torrent/test_global_rate_limiter.py -v
python -c "import personalscraper"
```

**Produces for Phase 3**: Caps are live — per-torrent limits applied at `add()` time, global limits re-asserted at run start. `BandwidthConfig` flows from config through `_factory.py` to orchestrator and service.
