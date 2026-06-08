# Phase 5a — `AppContext.tracker_registry` field

## Gate

**Requires Phase 4:**

```bash
python -c "
from personalscraper.api.tracker._registry import TrackerRegistry
from personalscraper.api.tracker._ranking import RankingConfig
TrackerRegistry(trackers={}, priority=[], ranking=RankingConfig()).close()
print('ok')
"
# Expected: ok
```

---

## Goal

Add `tracker_registry: "TrackerRegistry | None" = None` to the frozen
`AppContext` dataclass with a `TYPE_CHECKING` import. The `None` default
keeps every existing direct-construction test fixture valid without changes.
No change to the architecture boundary test allowlist — the field is a
data carrier, not a new module receiving `AppContext`.

---

## Files

- **Modify:** `personalscraper/core/app_context.py`

---

## Tasks

### Task 5a.1 — Add TYPE_CHECKING import

Open `personalscraper/core/app_context.py`. The existing `TYPE_CHECKING` block
already imports `ProviderRegistry`, `QBitClient`, `TransmissionClient`,
`Config`, `Settings`, `EventBus`. Add one line inside that block:

```python
    from personalscraper.api.tracker._registry import TrackerRegistry
```

The full block becomes:

```python
if TYPE_CHECKING:
    from personalscraper.api.metadata.registry import ProviderRegistry
    from personalscraper.api.torrent.qbittorrent import QBitClient
    from personalscraper.api.torrent.transmission import TransmissionClient
    from personalscraper.conf.models.config import Config
    from personalscraper.config import Settings
    from personalscraper.core.event_bus import EventBus
    from personalscraper.api.tracker._registry import TrackerRegistry
```

- [ ] Apply the edit.

---

### Task 5a.2 — Add the field

In the `AppContext` dataclass, after the `torrent_client` field:

```python
    torrent_client: "QBitClient | TransmissionClient | None" = None
```

add:

```python
    tracker_registry: "TrackerRegistry | None" = None  # RP5a — own port handle
```

Also extend the `Attributes:` section of the class docstring with:

```
        tracker_registry: Configured :class:`TrackerRegistry` built at boot
            by :func:`~personalscraper.cli_helpers.build_tracker_registry`,
            or ``None`` when no tracker is configured. In production
            ``_build_app_context`` always sets this to a real (possibly
            empty) registry. (RP5a — tracker-wiring.)
```

- [ ] Apply the edit.

- [ ] **Verify `None` default:**

  ```bash
  python -c "
  from unittest.mock import MagicMock
  from personalscraper.core.app_context import AppContext
  ctx = AppContext(
      config=MagicMock(), settings=MagicMock(),
      event_bus=MagicMock(), provider_registry=MagicMock(),
  )
  assert ctx.tracker_registry is None
  print('ok')
  "
  # Expected: ok
  ```

- [ ] **Verify existing construction with all fields still works:**
  ```bash
  python -c "
  from unittest.mock import MagicMock
  from personalscraper.core.app_context import AppContext
  ctx = AppContext(
      config=MagicMock(), settings=MagicMock(),
      event_bus=MagicMock(), provider_registry=MagicMock(),
      torrent_client=None, tracker_registry=None,
  )
  print('ok')
  "
  # Expected: ok
  ```

---

### Task 5a.3 — Confirm architecture boundary test still passes

The `tests/architecture/test_app_context_boundary.py` tests the allowlist of
modules that receive `AppContext`. Adding a field does not change that
allowlist. Verify:

```bash
python -m pytest tests/architecture/test_app_context_boundary.py -v
# Expected: all pass
```

---

### Task 5a.4 — Commit

```bash
git add personalscraper/core/app_context.py
git commit -m "feat(tracker-wiring): tracker_registry field on AppContext"
```

---

## Gate exit checklist

- [ ] `ctx.tracker_registry is None` default confirmed → `ok`
- [ ] `tests/architecture/test_app_context_boundary.py` → all pass
- [ ] `python -c "import personalscraper"` → exit 0
- [ ] Commit SHA recorded
