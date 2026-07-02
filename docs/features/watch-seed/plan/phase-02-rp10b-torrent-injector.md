# Phase 2 — RP10b: TorrentInjector protocol + QBitClient inject

## Gate

- **Requires Phase 1**: `TorrentLayout` + `parse_torrent_layout()` + `structural_match()` importable from `personalscraper.api.torrent._layout`.
- **Produces for Phase 4**: `TorrentInjector` protocol (importable from `_contracts.py`), `inject()` / `list_files()` / `properties()` on `QBitClient`, extended `TorrentItem` with `save_path` + `completion_on` — all ready for `CrossSeedService` consumption.

## Overview

Create the `@runtime_checkable` `TorrentInjector` protocol in `api/torrent/_contracts.py` alongside existing protocols (`TorrentLister`, `TorrentAdder`, etc.). Implement `inject()`, `list_files()`, and `properties()` on `QBitClient`. Extend the `TorrentItem` dataclass mapper with `save_path` + `completion_on` (currently dropped). TransmissionClient opts out cleanly (does not implement `TorrentInjector`).

### Sub-phases (5 commits)

| #   | Commit                                                                               | Scope      |
| --- | ------------------------------------------------------------------------------------ | ---------- |
| 2.1 | `feat(watch-seed): add TorrentInjector protocol to _contracts.py`                    | Protocol   |
| 2.2 | `feat(watch-seed): add list_files and properties methods to QBitClient`              | Read APIs  |
| 2.3 | `feat(watch-seed): add inject method to QBitClient`                                  | Inject API |
| 2.4 | `feat(watch-seed): extend TorrentItem with save_path and completion_on`              | Mapper     |
| 2.5 | `test(watch-seed): add integration tests for RP10b inject + list_files + properties` | Tests      |

## Sub-phase 2.1 — TorrentInjector protocol

**Files:**

- Modify: `personalscraper/api/torrent/_contracts.py` (add `TorrentInjector`)

Follow the existing pattern of `@runtime_checkable` protocols in the same file. The protocol exposes three methods:

```python
@runtime_checkable
class TorrentInjector(Protocol):
    """Capability: inject a .torrent at a specified save path with recheck.

    Composed by :class:`~personalscraper.api.torrent.qbittorrent.QBitClient`.
    Not implemented by :class:`TransmissionClient` — Transmission lacks
    ``savepath`` on add (D2) and 1:1 recheck semantics.
    """

    def inject(
        self,
        torrent_bytes: bytes,
        *,
        save_path: str,
        recheck: bool = True,
        paused: bool = True,
    ) -> str:
        """Inject a .torrent into the client, pointed at an existing data path.

        Args:
            torrent_bytes: Raw .torrent file bytes.
            save_path: Absolute path to the existing data directory
                (the source torrent's ``save_path``).
            recheck: Whether to run a recheck after adding (default True).
            paused: Whether to add in paused state (default True).

        Returns:
            The info-hash (v1) of the injected torrent.

        """

        ...

    def list_files(self, info_hash: str) -> list[tuple[str, int]]:
        """Return ``(name, size)`` for every file in a torrent.

        Wraps qBittorrent ``torrents/files``.

        Args:
            info_hash: V1 info-hash of an active torrent.

        Returns:
            Ordered list of (relative_path, byte_size) for each file.
        """
        ...

    def properties(self, info_hash: str) -> dict[str, object]:
        """Return the raw ``torrents/properties`` dict for *info_hash*.

        Args:
            info_hash: V1 info-hash.

        Returns:
            The full properties dictionary. The ``piece_size`` key is
            the torrent's ``piece_length`` in bytes.
        """
        ...
```

Update `__all__` to include `"TorrentInjector"`. Re-export in `api/torrent/__init__.py` if the module has a convenience re-export.

## Sub-phase 2.2 — list_files + properties on QBitClient

**Files:**

- Modify: `personalscraper/api/torrent/qbittorrent.py`

Add two methods to `QBitClient`:

```python
def list_files(self, info_hash: str) -> list[tuple[str, int]]:
    """Return ``(name, size)`` for every file in a torrent."""
    self._ensure_logged_in()
    data = self._transport.get(
        "/api/v2/torrents/files",
        {"hash": info_hash},
    )
    return [
        (entry["name"], entry["size"])
        for entry in data
    ]


def properties(self, info_hash: str) -> dict[str, object]:
    """Return the raw ``torrents/properties`` dict."""
    self._ensure_logged_in()
    return self._transport.get(
        "/api/v2/torrents/properties",
        {"hash": info_hash},
    )
```

Reuse the existing `_ensure_logged_in()` + `_transport.get()` pattern. Both methods are read-only and use the existing `TORRENT_LISTING_ERRORS` except-tuple.

## Sub-phase 2.3 — inject on QBitClient

**Files:**

- Modify: `personalscraper/api/torrent/qbittorrent.py`

```python
def inject(
    self,
    torrent_bytes: bytes,
    *,
    save_path: str,
    recheck: bool = True,
    paused: bool = True,
) -> str:
    """Inject a .torrent at *save_path*, add paused, optionally recheck.

    Sends the .torrent as a multipart file upload. After adding, if
    *recheck* is True, issues a ``/api/v2/torrents/recheck`` and waits
    for the check phase to complete (poll ``torrents/info`` state).

    Args:
        torrent_bytes: Raw .torrent file content.
        save_path: Absolute path to existing data.
        recheck: Run recheck after adding (default True).
        paused: Add in paused state (default True).

    Returns:
        The torrent's v1 info-hash.

    Raises:
        Conflict409: Torrent with this hash already present.
        QBitAuthError: Authentication failed.
        QBitError: Recheck timeout or API error.
    """
    self._ensure_logged_in()
    files = {"torrents": ("candidate.torrent", torrent_bytes, "application/x-bittorrent")}
    params = {
        "savepath": save_path,
        "skip_checking": "false",
        "paused": "true" if paused else "false",
    }
    self._transport.post("/api/v2/torrents/add", data=params, files=files)
    info_hash = _bencode_info_hash(torrent_bytes)
    if recheck:
        self._transport.post("/api/v2/torrents/recheck", {"hashes": info_hash})
    return info_hash
```

`Conflict409` detection is already present in the transport's POST handling — existing pattern.

## Sub-phase 2.4 — extend TorrentItem mapper

**Files:**

- Modify: `personalscraper/api/torrent/qbittorrent.py` (the `_torrent_item` function)

The `TorrentItem` dataclass currently drops `save_path` and `completion_on`. Add both fields to `TorrentItem` (in `api/torrent/_base.py` if defined there — check) and populate them from the qBittorrent API response:

- `save_path: str` — from the `save_path` field in `torrents/info`.
- `completion_on: int | None` — from `completion_on` (Unix timestamp, None if never completed).

```python
@dataclass(frozen=True, slots=True)
class TorrentItem:
    # ... existing fields ...
    save_path: str
    completion_on: int | None = None
```

Update `_torrent_item()` to read `item.get("save_path", "")` and `item.get("completion_on")`. Check `api/torrent/_base.py` for the dataclass definition.

## Sub-phase 2.5 — integration tests

**Files:**

- Create: `tests/integration/api/torrent/test_rp10b_injector.py`

Integration tests against a mocked `QBitClient` (or fake transport):

- `test_inject_posts_with_correct_savepath` — asserts `savepath` = source.save_path, `skip_checking=false`, `paused=true`.
- `test_inject_recheck_called` — asserts `/api/v2/torrents/recheck` was called with the info-hash.
- `test_inject_conflict409_raises` — when the transport returns HTTP 409.
- `test_list_files_returns_name_size_pairs` — raw API response → correct list-of-tuples.
- `test_properties_includes_piece_size` — verifies `piece_size` key present.
- `test_torrent_injector_isinstance_qbit` — `isinstance(QBitClient(), TorrentInjector)` is True.
- `test_torrent_injector_not_transmission` — `isinstance(TransmissionClient(), TorrentInjector)` is False (ACC-3).
- `test_torrent_item_save_path_and_completion_on` — mapper reads both fields from API response.

## Gate check (before advancing to Phase 3)

- [ ] `make lint` — 0 errors.
- [ ] `python -c "from personalscraper.api.torrent._contracts import TorrentInjector; from personalscraper.api.torrent.qbittorrent import QBitClient; print(hasattr(QBitClient,'inject') and hasattr(QBitClient,'list_files'))"` → `True` (ACC-3).
- [ ] `python -m pytest tests/integration/api/torrent/test_rp10b_injector.py -q` — all pass.
- [ ] Module size: `api/torrent/qbittorrent.py` stays under soft limit (if near, consider extracting the inject methods into a mixin or separate module).
