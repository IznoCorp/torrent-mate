# Phase 03 — `TorrentItem.tags` Field + Mapper Updates

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Add `tags: list[str] = field(default_factory=list)` to `TorrentItem`; update `_torrent_item()` in both `qbittorrent.py` (split CSV) and `transmission.py` (D5 labels round-trip). 1 commit.

**Tech Stack:** Python 3.11, `dataclasses`, `qbittorrentapi`, `transmission_rpc`, pytest

---

## Gate

- `TorrentAdder`, `TorrentLimiter` importable from `_contracts.py`.
- `make lint` passes.

---

## Files

- Modify: `personalscraper/api/torrent/_base.py`
- Modify: `personalscraper/api/torrent/qbittorrent.py` (mapper `_torrent_item`)
- Modify: `personalscraper/api/torrent/transmission.py` (mapper `_torrent_item`)
- Modify: `tests/unit/test_qbittorrent.py` (add tags tests)

---

## Steps

- [ ] **1. Write failing tests** — add to `tests/unit/test_qbittorrent.py`:

```python
from personalscraper.api.torrent._base import TorrentItem

class TestTorrentItemTagsField:
    """TorrentItem.tags field — D4."""

    def test_default_empty_list(self) -> None:
        item = TorrentItem(hash="h", name="n", size_bytes=0, progress=0.0, state="up")
        assert item.tags == [] and isinstance(item.tags, list)

    def test_qbit_mapper_splits_csv(self) -> None:
        mock = MagicMock()
        mock.hash = "h"; mock.name = "n"; mock.total_size = 0
        mock.progress = 0.0; mock.state = "up"; mock.ratio = 0.0
        mock.content_path = ""; mock.category = ""; mock.added_on = 0
        mock.tags = "action,drama,2024"
        assert _torrent_item(mock).tags == ["action", "drama", "2024"]

    def test_qbit_mapper_empty_tags(self) -> None:
        mock = MagicMock()
        mock.hash = "h"; mock.name = "n"; mock.total_size = 0
        mock.progress = 0.0; mock.state = "up"; mock.ratio = 0.0
        mock.content_path = ""; mock.category = ""; mock.added_on = 0
        mock.tags = ""
        assert _torrent_item(mock).tags == []
```

Create `tests/unit/test_transmission_tags.py`:

```python
"""Tests for Transmission _torrent_item labels→tags round-trip (D5)."""
from __future__ import annotations
from unittest.mock import MagicMock
from personalscraper.api.torrent.transmission import _torrent_item

def _mock(labels=None):
    t = MagicMock()
    t.hash_string = "h"; t.name = "n"; t.total_size = 0
    t.percent_done = 0.0; t.status = "stopped"
    t.download_dir = None; t.added_date = None
    t.get_files.return_value = []
    t.labels = labels
    t.ratio = 0.0
    return t

def test_labels_round_trip_category_and_tags():
    item = _torrent_item(_mock(labels=["movies", "action", "2024"]))
    assert item.category == "movies"
    assert item.tags == ["action", "2024"]

def test_labels_category_only():
    item = _torrent_item(_mock(labels=["movies"]))
    assert item.category == "movies"
    assert item.tags == []

def test_labels_none():
    item = _torrent_item(_mock(labels=None))
    assert item.category is None
    assert item.tags == []
```

- [ ] **2. Run — confirm failures**

```bash
cd /Users/izno/dev/PersonnalScaper && pytest tests/unit/test_qbittorrent.py::TestTorrentItemTagsField tests/unit/test_transmission_tags.py -q 2>&1 | tail -8
```

Expected: `AttributeError` — `tags` field missing.

- [ ] **3. Add `tags` field to `TorrentItem` in `_base.py`**

In `TorrentItem`, add after the `category` field:

```python
    tags: list[str] = field(default_factory=list)
```

Add `    tags: List of tag labels (default ``[]``).` to the docstring Attributes section.

- [ ] **4. Update `_torrent_item()` in `qbittorrent.py`** (line ~259)

Change the return statement to include:

```python
    raw_tags = getattr(t, "tags", "") or ""
    tags = [tag.strip() for tag in raw_tags.split(",") if tag.strip()]
    return TorrentItem(
        hash=t.hash, name=t.name, size_bytes=t.total_size,
        progress=float(t.progress), state=t.state,
        ratio=float(t.ratio or 0.0),
        content_path=Path(content_path) if content_path else None,
        category=t.category if t.category else None,
        tags=tags,
        added_on=datetime.fromtimestamp(t.added_on) if t.added_on else None,
    )
```

- [ ] **5. Update `_torrent_item()` in `transmission.py`** (line ~259)

Replace the `labels = ...` / `category = ...` block with the D5 round-trip:

```python
    labels: list[str] = list(getattr(t, "labels", None) or [])
    category = labels[0] if labels else None
    tags = list(labels[1:]) if len(labels) > 1 else []
```

Add `tags=tags` to the `TorrentItem(...)` constructor call.

- [ ] **6. Run all tests**

```bash
cd /Users/izno/dev/PersonnalScaper && pytest tests/unit/test_qbittorrent.py tests/unit/test_transmission_tags.py tests/unit/test_torrent_capabilities_composition.py tests/unit/test_torrent_factory.py -q 2>&1 | tail -8
```

Expected: all pass.

- [ ] **7. Lint**

```bash
cd /Users/izno/dev/PersonnalScaper && make lint 2>&1 | tail -5
```

- [ ] **8. Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add personalscraper/api/torrent/_base.py personalscraper/api/torrent/qbittorrent.py personalscraper/api/torrent/transmission.py tests/unit/test_qbittorrent.py tests/unit/test_transmission_tags.py && git commit -m "feat(torrent-write): add TorrentItem.tags field and update qBit/Transmission mappers (D4/D5)"
```

---

## Phase gate

```bash
cd /Users/izno/dev/PersonnalScaper && make check 2>&1 | tail -10
```

Expected: exits 0.
