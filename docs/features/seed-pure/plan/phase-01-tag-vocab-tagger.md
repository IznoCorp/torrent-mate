# Phase 1 — Tag vocab + tagger capability

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to execute task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Create `core/tags.py` with the `SEED_PURE` constant, add the `TorrentTagger` protocol to `api/torrent/_contracts.py`, and implement `add_tags`/`remove_tags` on both `QBitClient` and `TransmissionClient` (Transmission uses a read-first write to preserve the category). Tests cover criteria 1-3.

**Architecture:** `core/tags.py` is the bottom layer — it imports nothing project-internal. `api/torrent/_contracts.py` gains a new `@runtime_checkable` `TorrentTagger` protocol alongside the existing atomic protocols. Both clients implement it: qBittorrent wraps `torrents_addTags`/`torrents_removeTags`; Transmission does a `get_torrent` → mutate labels set → `change_torrent` round-trip to preserve `labels[0]` (category).

**Tech Stack:** Python 3.11+, `qbittorrentapi`, `transmission-rpc`, `pytest`, `unittest.mock`

---

## Gate

_This is Phase 1 — no previous phase gate required._

---

## Sub-phase 1.1 — `core/tags.py` + `TorrentTagger` protocol

**Files:**

- Create: `personalscraper/core/tags.py`
- Modify: `personalscraper/api/torrent/_contracts.py` (add `TorrentTagger`; update `__all__`)
- Create: `tests/api/torrent/test_tagger.py` (skeleton — tests added in 1.2 and 1.3)

### Task 1: Create `personalscraper/core/tags.py`

- [ ] **Step 1: Create the module**

```python
"""Centralized tag vocabulary for the triage pipeline (seed-pure feature).

All layers — ``api/torrent``, ``ingest``, ``sorter``, ``process``,
``commands``, and a future Watcher — import tag constants from here
rather than using string literals, so a rename touches one file only.
``core/`` is the bottom layer: this module imports nothing project-internal.
"""

SEED_PURE = "seed-pure"
"""Tag applied to a torrent downloaded only for ratio seeding.

A torrent carrying this tag must be skipped by the triage pipeline
(ingest, sort, process) and by the Watcher before triggering a pipeline
run. The tag is set manually via ``personalscraper seed mark <hash>``
or automatically by Follow D3 / Ratio (future).
"""

__all__ = ["SEED_PURE"]
```

- [ ] **Step 2: Smoke-test the import**

```bash
python -c "from personalscraper.core.tags import SEED_PURE; assert SEED_PURE == 'seed-pure'; print('OK')"
```

Expected: `OK`

### Task 2: Add `TorrentTagger` protocol to `api/torrent/_contracts.py`

The current `__all__` in `_contracts.py` (lines 180-188) exports 7 protocols. We add `TorrentTagger` as the 8th, immediately before `__all__`.

- [ ] **Step 1: Verify the current `__all__` block to get exact text for the edit**

```bash
rg "__all__" --type py personalscraper/api/torrent/_contracts.py -n
```

Expected output: a line around 180 showing `__all__ = [`.

- [ ] **Step 2: Add `TorrentTagger` protocol after `TorrentLimiter` and update `__all__`**

Insert the following block immediately before the `__all__ = [` line in `personalscraper/api/torrent/_contracts.py`:

```python
@runtime_checkable
class TorrentTagger(Protocol):
    """Capability — add or remove tags on an existing torrent.

    Implemented by both ``QBitClient`` and ``TransmissionClient``.
    Both methods are **idempotent**: adding a tag that is already present
    is a no-op; removing a tag that is absent is a no-op. The torrent is
    identified by its lowercase-hex ``info_hash`` (``TorrentItem.hash``).

    Transmission requires a read-first write to preserve ``labels[0]``
    (the category); callers need not know the implementation detail.
    """

    def add_tags(self, info_hash: str, tags: Sequence[str]) -> None:
        """Add tags to an existing torrent (idempotent).

        Args:
            info_hash: Lowercase-hex info hash of the target torrent.
            tags: Tag strings to add. Already-present tags are ignored.
        """
        ...

    def remove_tags(self, info_hash: str, tags: Sequence[str]) -> None:
        """Remove tags from an existing torrent (idempotent).

        Args:
            info_hash: Lowercase-hex info hash of the target torrent.
            tags: Tag strings to remove. Absent tags are ignored.
        """
        ...
```

Update `__all__` to include `"TorrentTagger"`:

```python
__all__ = [
    "AuthenticatedClient",
    "TorrentAdder",
    "TorrentController",
    "TorrentInspector",
    "TorrentLimiter",
    "TorrentLister",
    "TorrentStateInspector",
    "TorrentTagger",
]
```

- [ ] **Step 3: Verify the import**

```bash
python -c "from personalscraper.api.torrent._contracts import TorrentTagger; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add personalscraper/core/tags.py personalscraper/api/torrent/_contracts.py
git commit -m "feat(seed-pure): add SEED_PURE constant + TorrentTagger protocol"
```

---

## Sub-phase 1.2 — `QBitClient.add_tags` / `remove_tags`

**Files:**

- Modify: `personalscraper/api/torrent/qbittorrent.py`
- Create: `tests/api/torrent/test_tagger.py`

### Task 3: Add `add_tags` / `remove_tags` to `QBitClient`

qBittorrent stores tags as a comma-delimited string internally (`_torrent_item` at line ~404 splits on `,`). The API calls are `torrents_addTags(torrent_hashes, tags)` and `torrents_removeTags(torrent_hashes, tags)` from `qbittorrentapi`.

- [ ] **Step 1: Add `TorrentTagger` to `QBitClient`'s composition list**

In `personalscraper/api/torrent/qbittorrent.py`, the class declaration (lines 50-57) reads:

```python
class QBitClient(
    TorrentLister,
    TorrentInspector,
    AuthenticatedClient,
    TorrentStateInspector,
    TorrentController,
    TorrentAdder,
    TorrentLimiter,
):
```

Add `TorrentTagger` to the import from `_contracts` and to the class bases:

```python
from personalscraper.api.torrent._contracts import (
    AuthenticatedClient,
    TorrentAdder,
    TorrentController,
    TorrentInspector,
    TorrentLimiter,
    TorrentLister,
    TorrentStateInspector,
    TorrentTagger,
)
```

```python
class QBitClient(
    TorrentLister,
    TorrentInspector,
    AuthenticatedClient,
    TorrentStateInspector,
    TorrentController,
    TorrentAdder,
    TorrentLimiter,
    TorrentTagger,
):
```

- [ ] **Step 2: Add `add_tags` and `remove_tags` methods**

Add these two methods inside `QBitClient`, after `apply_limits` (around line 340, before the `# -- Auth` block):

```python
def add_tags(self, info_hash: str, tags: Sequence[str]) -> None:
    """Add tags to an existing torrent in qBittorrent (idempotent).

    Wraps ``qbittorrentapi.torrents_addTags``. Tags already present on
    the torrent are silently ignored by the qBittorrent API — idempotent
    by the server's own semantics.

    Args:
        info_hash: Lowercase-hex info hash of the target torrent.
        tags: Tag strings to add.
    """
    if not tags:
        return
    self._client.torrents_addTags(torrent_hashes=info_hash, tags=",".join(tags))

def remove_tags(self, info_hash: str, tags: Sequence[str]) -> None:
    """Remove tags from an existing torrent in qBittorrent (idempotent).

    Wraps ``qbittorrentapi.torrents_removeTags``. Absent tags are silently
    ignored by the qBittorrent API — idempotent by the server's own
    semantics.

    Args:
        info_hash: Lowercase-hex info hash of the target torrent.
        tags: Tag strings to remove.
    """
    if not tags:
        return
    self._client.torrents_removeTags(torrent_hashes=info_hash, tags=",".join(tags))
```

### Task 4: Write failing tests for QBitClient tagger

- [ ] **Step 1: Create `tests/api/torrent/test_tagger.py`**

```python
"""Tests for TorrentTagger capability on QBitClient and TransmissionClient.

Covers DESIGN criteria 1 (SEED_PURE importable), 2 (qBit tagger endpoints +
idempotence), and 3 (Transmission category preservation).
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

if TYPE_CHECKING:
    from personalscraper.api.torrent.qbittorrent import QBitClient


# ---------------------------------------------------------------------------
# Criterion 1 — SEED_PURE constant
# ---------------------------------------------------------------------------


def test_seed_pure_importable_and_value():
    """SEED_PURE is importable from core.tags and equals 'seed-pure'."""
    from personalscraper.core.tags import SEED_PURE

    assert SEED_PURE == "seed-pure"


def test_seed_pure_in_all():
    """SEED_PURE is in core.tags.__all__."""
    import personalscraper.core.tags as m

    assert "SEED_PURE" in m.__all__


# ---------------------------------------------------------------------------
# Criterion 2 — QBitClient tagger
# ---------------------------------------------------------------------------


def _make_qbit_client() -> "QBitClient":
    """Build a QBitClient with a mocked underlying qbittorrentapi.Client."""
    from personalscraper.api.torrent.qbittorrent import QBitClient

    client = QBitClient.__new__(QBitClient)
    client._client = MagicMock()
    return client


def test_qbit_add_tags_calls_addTags():
    """add_tags calls torrents_addTags with correct hash and comma-joined tags."""
    client = _make_qbit_client()
    client.add_tags("abc123", ["seed-pure", "other"])
    client._client.torrents_addTags.assert_called_once_with(
        torrent_hashes="abc123", tags="seed-pure,other"
    )


def test_qbit_remove_tags_calls_removeTags():
    """remove_tags calls torrents_removeTags with correct hash and comma-joined tags."""
    client = _make_qbit_client()
    client.remove_tags("abc123", ["seed-pure"])
    client._client.torrents_removeTags.assert_called_once_with(
        torrent_hashes="abc123", tags="seed-pure"
    )


def test_qbit_add_tags_empty_is_noop():
    """add_tags with empty list makes no API call."""
    client = _make_qbit_client()
    client.add_tags("abc123", [])
    client._client.torrents_addTags.assert_not_called()


def test_qbit_remove_tags_empty_is_noop():
    """remove_tags with empty list makes no API call."""
    client = _make_qbit_client()
    client.remove_tags("abc123", [])
    client._client.torrents_removeTags.assert_not_called()


def test_qbit_tagger_protocol_compliance():
    """QBitClient satisfies the TorrentTagger protocol at runtime."""
    from personalscraper.api.torrent._contracts import TorrentTagger

    client = _make_qbit_client()
    assert isinstance(client, TorrentTagger)
```

> **Plan-drift note (1.2):** under `from __future__ import annotations`, the
> string annotation `-> "QBitClient"` with a function-local import trips ruff
> `F821` (undefined name). Resolved by adding a `TYPE_CHECKING` import for
> `QBitClient` at module top and dropping `, call, patch` from the
> `unittest.mock` import (neither is used → would trip `F401`). The unused
> function-local `QBitClient` import in `test_qbit_tagger_protocol_compliance`
> was removed (the client is built via `_make_qbit_client`).

- [ ] **Step 2: Run the qBit tagger tests (must PASS)**

```bash
pytest tests/api/torrent/test_tagger.py -k "qbit or seed_pure" -v
```

Expected: all qBit + criterion-1 tests pass. If any fail, fix before proceeding.

- [ ] **Step 3: Commit**

```bash
git add personalscraper/api/torrent/qbittorrent.py tests/api/torrent/test_tagger.py
git commit -m "feat(seed-pure): add QBitClient.add_tags/remove_tags + tests"
```

---

## Sub-phase 1.3 — `TransmissionClient.add_tags` / `remove_tags`

**Files:**

- Modify: `personalscraper/api/torrent/transmission.py`
- Modify: `tests/api/torrent/test_tagger.py`

### Task 5: Add `add_tags` / `remove_tags` to `TransmissionClient`

Transmission stores category + tags in a flat `labels` list: `labels = [category, *tags]`. The `_labels()` helper (line 362) and `_torrent_item()` (line 384) both encode this round-trip. To tag an existing torrent without wiping the category, we **must** read first.

The `transmission_rpc.Client` API:

- `get_torrent(info_hash, arguments=["labels"])` → `Torrent` object; `getattr(t, "labels", None) or []`
- `change_torrent(ids=info_hash, labels=[...])` → applies the new labels

- [ ] **Step 1: Add `TorrentTagger` to `TransmissionClient`'s composition**

In `personalscraper/api/torrent/transmission.py`, update the import block:

```python
from personalscraper.api.torrent._contracts import (
    TorrentAdder,
    TorrentController,
    TorrentInspector,
    TorrentLister,
    TorrentStateInspector,
    TorrentTagger,
)
```

Update the class bases:

```python
class TransmissionClient(
    TorrentLister,
    TorrentInspector,
    TorrentStateInspector,
    TorrentController,
    TorrentAdder,
    TorrentTagger,
):
```

Also update the module docstring's composition list to mention `TorrentTagger`.

- [ ] **Step 2: Add `add_tags` and `remove_tags` methods to `TransmissionClient`**

Add after the `delete` method (around line 297, before the `# -- Factory` block):

```python
def add_tags(self, info_hash: str, tags: Sequence[str]) -> None:
    """Add tags to an existing Transmission torrent (idempotent, read-first).

    Transmission stores category + tags in one flat ``labels`` list:
    ``labels = [category, *tags]``. We read the current labels, compute the
    new tag set (union, preserving order), then write back with the category
    at ``labels[0]`` intact. Adding an already-present tag is a no-op.

    Args:
        info_hash: Lowercase-hex info hash of the target torrent.
        tags: Tag strings to add.
    """
    if not tags:
        return
    t = self._client.get_torrent(info_hash, arguments=["labels"])
    current_labels: list[str] = list(getattr(t, "labels", None) or [])
    category = current_labels[0] if current_labels else None
    existing_tags = list(current_labels[1:]) if len(current_labels) > 1 else []
    new_tags = existing_tags[:]
    for tag in tags:
        if tag not in new_tags:
            new_tags.append(tag)
    self._client.change_torrent(ids=info_hash, labels=_labels(category, new_tags))

def remove_tags(self, info_hash: str, tags: Sequence[str]) -> None:
    """Remove tags from an existing Transmission torrent (idempotent, read-first).

    Reads current labels, removes the requested tags from the tag portion
    (``labels[1:]``), then writes back with the category at ``labels[0]``
    intact. Removing an absent tag is a no-op.

    Args:
        info_hash: Lowercase-hex info hash of the target torrent.
        tags: Tag strings to remove.
    """
    if not tags:
        return
    t = self._client.get_torrent(info_hash, arguments=["labels"])
    current_labels: list[str] = list(getattr(t, "labels", None) or [])
    category = current_labels[0] if current_labels else None
    existing_tags = list(current_labels[1:]) if len(current_labels) > 1 else []
    tags_to_remove = set(tags)
    new_tags = [tag for tag in existing_tags if tag not in tags_to_remove]
    self._client.change_torrent(ids=info_hash, labels=_labels(category, new_tags))
```

### Task 6: Write Transmission tagger tests (including the category-preservation golden)

- [ ] **Step 1: Append Transmission tests to `tests/api/torrent/test_tagger.py`**

```python
# ---------------------------------------------------------------------------
# Criterion 3 — TransmissionClient tagger (category preservation is the
# load-bearing correctness point)
# ---------------------------------------------------------------------------


def _make_tx_client() -> "TransmissionClient":
    """Build a TransmissionClient with a mocked underlying transmission_rpc.Client."""
    from personalscraper.api.torrent.transmission import TransmissionClient

    client = TransmissionClient.__new__(TransmissionClient)
    client._client = MagicMock()
    return client


def _mock_torrent(labels: list[str]) -> MagicMock:
    """Return a mock Transmission Torrent object with the given labels."""
    t = MagicMock()
    t.labels = labels
    return t


def test_tx_add_tags_preserves_category():
    """add_tags keeps labels[0] (category) and appends the new tag.

    Golden: category='movies', existing_tags=['tag1'],
    add_tags(['seed-pure']) → change_torrent called with
    labels=['movies', 'tag1', 'seed-pure'].
    """
    client = _make_tx_client()
    client._client.get_torrent.return_value = _mock_torrent(["movies", "tag1"])

    client.add_tags("abc123", ["seed-pure"])

    client._client.get_torrent.assert_called_once_with("abc123", arguments=["labels"])
    client._client.change_torrent.assert_called_once_with(
        ids="abc123", labels=["movies", "tag1", "seed-pure"]
    )


def test_tx_add_tags_idempotent_already_present():
    """add_tags does not duplicate a tag already in the list."""
    client = _make_tx_client()
    client._client.get_torrent.return_value = _mock_torrent(["movies", "seed-pure"])

    client.add_tags("abc123", ["seed-pure"])

    # labels must stay exactly ['movies', 'seed-pure'] — no duplicate
    client._client.change_torrent.assert_called_once_with(
        ids="abc123", labels=["movies", "seed-pure"]
    )


def test_tx_remove_tags_preserves_category():
    """remove_tags keeps labels[0] and removes only the requested tag."""
    client = _make_tx_client()
    client._client.get_torrent.return_value = _mock_torrent(["movies", "seed-pure", "other"])

    client.remove_tags("abc123", ["seed-pure"])

    client._client.change_torrent.assert_called_once_with(
        ids="abc123", labels=["movies", "other"]
    )


def test_tx_remove_tags_idempotent_absent():
    """remove_tags on an absent tag is a no-op (no error, category preserved)."""
    client = _make_tx_client()
    client._client.get_torrent.return_value = _mock_torrent(["movies", "other"])

    client.remove_tags("abc123", ["seed-pure"])

    client._client.change_torrent.assert_called_once_with(
        ids="abc123", labels=["movies", "other"]
    )


def test_tx_add_tags_empty_is_noop():
    """add_tags with empty list makes no API call."""
    client = _make_tx_client()
    client.add_tags("abc123", [])
    client._client.get_torrent.assert_not_called()
    client._client.change_torrent.assert_not_called()


def test_tx_remove_tags_empty_is_noop():
    """remove_tags with empty list makes no API call."""
    client = _make_tx_client()
    client.remove_tags("abc123", [])
    client._client.get_torrent.assert_not_called()
    client._client.change_torrent.assert_not_called()


def test_tx_tagger_protocol_compliance():
    """TransmissionClient satisfies the TorrentTagger protocol at runtime."""
    from personalscraper.api.torrent._contracts import TorrentTagger

    client = _make_tx_client()
    assert isinstance(client, TorrentTagger)
```

> **Plan-drift note (1.3):** same fix as 1.2 applied to the Transmission helper.
> `TransmissionClient` was added to the module-top `TYPE_CHECKING` block so the
> `-> "TransmissionClient"` string annotation resolves under
> `from __future__ import annotations` (avoids ruff `F821`), and the unused
> function-local `TransmissionClient` import in
> `test_tx_tagger_protocol_compliance` was removed (the client is built via
> `_make_tx_client`).

- [ ] **Step 2: Run all tagger tests**

```bash
pytest tests/api/torrent/test_tagger.py -v
```

Expected: all tests pass, `0 failed`.

- [ ] **Step 3: Commit**

```bash
git add personalscraper/api/torrent/transmission.py tests/api/torrent/test_tagger.py
git commit -m "feat(seed-pure): add TransmissionClient.add_tags/remove_tags (read-first, category-safe) + tests"
```

---

## Phase 1 Gate

- [ ] **Run `make lint`** — must exit 0 (ruff + mypy zero errors).
- [ ] **Run `make test`** — must show `0 failed`, `0 errors`.
- [ ] **Run `make check`** — must exit 0.
- [ ] **Smoke test:** `python -c "import personalscraper"` — must print nothing and exit 0.
- [ ] **Layering check:** `rg "indexer|scraper|sorter|ingest|commands|process" --type py personalscraper/core/tags.py` — must return no matches.
- [ ] **Protocol check:** `python -c "from personalscraper.api.torrent._contracts import TorrentTagger; print(TorrentTagger.__protocol_attrs__)"` — must include `add_tags` and `remove_tags`.
