# Phase 05 — Dispatch-time writer + per-site wiring

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement `record_dispatch` (basename+size torrent correlation, write-before-move,
lock-free fail-soft, HIT/MISS logging), inject `DeletePermit` and `SeedObligationRecorder` into
`dispatch/run.py` and `maintenance/disk_cleaner.py`, and apply the three-state per-site policy
in `dispatch/_movie.py` / `dispatch/_tv.py`.

**Architecture:** `record_dispatch` correlates staging source to a live seeding torrent by
basename + total size against a single cached `get_completed()` call — NOT by `content_path`
(DESIGN §7.2). Write is lock-free + fail-soft (raw `sqlite3` + `busy_timeout`), write-before-move.
Dispatch policy: seedtime/ratio MET → ALLOW + `satisfied_at`; NOT met → proceed + `breached_at` +
`acquire.hnr_risk` warning; `disk_cleaner` VETO → hard skip counted as `skipped_by_obligation`.
Deleters import only `core.delete_permit` types — never `acquire/`.

**Tech stack:** `core.delete_permit.{DeletePermit,SeedObligationRecorder,AllowAllPermit}`,
`dispatch/run.py`, `dispatch/_movie.py`, `dispatch/_tv.py`, `maintenance/disk_cleaner.py`.

---

## Gate (from Phase 4)

- `personalscraper/core/delete_permit.py` exists; `AllowAllPermit`, `DeletePermit`,
  `SeedObligationRecorder` importable.
- `personalscraper/acquire/delete_authority.py` exists; `build_delete_authority` importable.
- `AcquireContext.delete_authority` slot present.
- Adversarial fail-open tests all pass.
- `make check` green.

---

## File map

| Action | Path                                                                             |
| ------ | -------------------------------------------------------------------------------- |
| Modify | `personalscraper/acquire/delete_authority.py` (`record_dispatch` implementation) |
| Modify | `personalscraper/dispatch/run.py` (inject permit + recorder)                     |
| Modify | `personalscraper/dispatch/dispatcher.py` (add permit/recorder params)            |
| Modify | `personalscraper/dispatch/_movie.py` (three-state policy)                        |
| Modify | `personalscraper/dispatch/_tv.py` (three-state policy)                           |
| Modify | `personalscraper/maintenance/disk_cleaner.py` (hard-skip on VETO)                |
| Create | `tests/acquire/test_record_dispatch.py`                                          |
| Create | `tests/acquire/test_crash_window.py`                                             |

---

### Task 1 — Implement `record_dispatch` in `delete_authority.py`

> **⚠ CORRECTIVE NOTE (sub-phase 5.1, real-API grounding).** The Step-1/Step-3
> code blocks below code against a **fictional torrent API** and MUST NOT be
> copied verbatim. They were superseded during implementation. The shipped
> implementation uses the REAL API:
>
> - **`TorrentItem`** (`api/torrent/_base.py`) fields: `hash` (the info hash, NOT
>   `info_hash`), `name`, `size_bytes` (NOT `total_size`), `tags`, `state`,
>   `progress`, `ratio`. There is **NO** `item.is_seeding()` method.
> - **Seeding check** is a **client** method: `client.is_seeding(item)` per
>   `TorrentStateInspector` (`api/torrent/_contracts.py`) — NOT an item method.
> - **Correlation**: `item.name == staging_source.name` AND
>   `item.size_bytes == staging_source.stat().st_size`. Zero → MISS
>   `no-live-torrent`; >1 → MISS `name+size-ambiguous`; not seeding → MISS
>   `not-seeding`.
> - **Tracker resolution + economy**: `DeleteAuthority.__init__` (and
>   `build_delete_authority`) gain `torrent_client` and
>   `economy: dict[str, TrackerEconomyConfig] | None`. The factory builds the
>   economy map from `config.tracker.providers` (`{name: p.economy for name, p
in providers.items() if p.economy is not None}`). The source tracker is
>   resolved by intersecting `item.tags` with `economy.keys()` (RP1 tag
>   convention). No matching tag → MISS `tracker-unresolved` (no global default
>   invented — manually-added torrents legitimately MISS here today). On HIT the
>   obligation snapshots `economy.min_seed_time` / `economy.min_ratio` (note: the
>   field is `min_seed_time`, in seconds).
> - **HIT write**: `store.seed.add(SeedObligation(info_hash=item.hash, …,
dispatched_path=str(dispatched_dest)))` — write-before-move; store-write
>   errors are swallowed + logged `acquire.record_dispatch.write_failed`. Writes
>   go through the regular `store.seed.add` (lock-free WAL + `BEGIN IMMEDIATE`),
>   NOT a raw `sqlite3.connect` against `self._store._db_path`.
>
> **`mark_breach` port (replaces the brittle raw-SQL breach hack in Task 3).**
> A `mark_breach(self, path: Path) -> None` method was added to the
> `SeedObligationRecorder` Protocol + `AllowAllPermit` (no-op) +
> `DeleteAuthority` (fail-soft → `store.seed.mark_breached_under(path,
int(time.time()))`). A new boundary-safe `mark_breached_under(path,
breached_at) -> int` was added to `_SeedSubStore` (and the `SeedSubStore`
> Protocol in `_ports.py`). Task 3 MUST call `self._recorder.mark_breach(path)`
> instead of the `_recorder._store.seed._conn` raw-SQL fetch/update.

**Files:**

- Modify: `personalscraper/acquire/delete_authority.py`
- Test: `tests/acquire/test_record_dispatch.py`

- [ ] **Step 1: Write failing tests for `record_dispatch`**

```python
# tests/acquire/test_record_dispatch.py
"""Tests for DeleteAuthority.record_dispatch: basename+size correlation, HIT/MISS."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.acquire.delete_authority import DeleteAuthority, build_delete_authority
from personalscraper.acquire.store import build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig


def _make_torrent_item(name: str, size: int, is_seeding: bool = True) -> MagicMock:
    item = MagicMock()
    item.name = name
    item.total_size = size
    item.is_seeding.return_value = is_seeding
    item.info_hash = "deadbeef" + name[:8].ljust(8, "0")
    return item


@pytest.fixture()
def store(tmp_path: Path):
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s = build_acquire_store(cfg)
    yield s
    s.close()


def test_record_dispatch_hit_writes_obligation(store, tmp_path: Path) -> None:
    """HIT: basename+size match on a seeding torrent → obligation written before move."""
    staging = tmp_path / "staging" / "MyShow.S01E01.mkv"
    staging.parent.mkdir()
    staging.write_bytes(b"x" * 1024)
    dest = tmp_path / "library" / "MyShow.S01E01.mkv"

    torrent = _make_torrent_item("MyShow.S01E01.mkv", size=1024, is_seeding=True)
    mock_client = MagicMock()
    mock_client.get_completed.return_value = [torrent]

    auth = DeleteAuthority(store=store, torrent_client=mock_client)
    auth.record_dispatch(staging_source=staging, dispatched_dest=dest)

    # Obligation must be written before the move (i.e., before dest exists)
    conn = sqlite3.connect(str(tmp_path / "acquire.db"))
    rows = conn.execute("SELECT info_hash, dispatched_path FROM seed_obligation").fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0][1] == str(dest)


def test_record_dispatch_miss_no_seeding_torrent(store, tmp_path: Path) -> None:
    """MISS: torrent exists but is_seeding=False → no obligation written."""
    staging = tmp_path / "staging" / "MyShow.S01E01.mkv"
    staging.parent.mkdir()
    staging.write_bytes(b"x" * 1024)
    dest = tmp_path / "library" / "MyShow.S01E01.mkv"

    torrent = _make_torrent_item("MyShow.S01E01.mkv", size=1024, is_seeding=False)
    mock_client = MagicMock()
    mock_client.get_completed.return_value = [torrent]

    auth = DeleteAuthority(store=store, torrent_client=mock_client)
    auth.record_dispatch(staging_source=staging, dispatched_dest=dest)

    conn = sqlite3.connect(str(tmp_path / "acquire.db"))
    rows = conn.execute("SELECT * FROM seed_obligation").fetchall()
    conn.close()
    assert len(rows) == 0


def test_record_dispatch_miss_no_matching_torrent(store, tmp_path: Path) -> None:
    """MISS: no torrent matches basename+size → no obligation written."""
    staging = tmp_path / "staging" / "Movie.mkv"
    staging.parent.mkdir()
    staging.write_bytes(b"x" * 512)
    dest = tmp_path / "library" / "Movie.mkv"

    torrent = _make_torrent_item("OtherMovie.mkv", size=512, is_seeding=True)
    mock_client = MagicMock()
    mock_client.get_completed.return_value = [torrent]

    auth = DeleteAuthority(store=store, torrent_client=mock_client)
    auth.record_dispatch(staging_source=staging, dispatched_dest=dest)

    conn = sqlite3.connect(str(tmp_path / "acquire.db"))
    rows = conn.execute("SELECT * FROM seed_obligation").fetchall()
    conn.close()
    assert len(rows) == 0


def test_record_dispatch_fail_soft_on_client_error(store, tmp_path: Path) -> None:
    """If torrent client raises, record_dispatch swallows the error (fail-soft)."""
    staging = tmp_path / "staging" / "Movie.mkv"
    staging.parent.mkdir()
    staging.write_bytes(b"x" * 512)
    dest = tmp_path / "library" / "Movie.mkv"

    mock_client = MagicMock()
    mock_client.get_completed.side_effect = RuntimeError("client unreachable")

    auth = DeleteAuthority(store=store, torrent_client=mock_client)
    # Must NOT raise
    auth.record_dispatch(staging_source=staging, dispatched_dest=dest)


def test_record_dispatch_no_client_is_noop(store, tmp_path: Path) -> None:
    """No torrent client → record_dispatch is a silent no-op."""
    staging = tmp_path / "staging" / "Movie.mkv"
    staging.parent.mkdir()
    staging.write_bytes(b"x" * 512)
    dest = tmp_path / "library" / "Movie.mkv"

    auth = DeleteAuthority(store=store, torrent_client=None)
    auth.record_dispatch(staging_source=staging, dispatched_dest=dest)
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/acquire/test_record_dispatch.py -v 2>&1 | tail -15
```

Expected: failures (record_dispatch is currently a no-op and `DeleteAuthority.__init__` does not
accept `torrent_client`).

- [ ] **Step 3: Update `DeleteAuthority.__init__` and implement `record_dispatch`**

In `personalscraper/acquire/delete_authority.py`:

1. Add `torrent_client` param to `__init__` (TYPE_CHECKING import for the torrent client union):

```python
if TYPE_CHECKING:
    from personalscraper.api.torrent.qbittorrent import QBitClient
    from personalscraper.api.torrent.transmission import TransmissionClient

class DeleteAuthority:
    def __init__(
        self,
        store: "ConcreteAcquireStore | None",
        torrent_client: "QBitClient | TransmissionClient | None" = None,
    ) -> None:
        self._store = store
        self._torrent_client = torrent_client
```

2. Replace the no-op `record_dispatch` with the real implementation:

```python
def record_dispatch(
    self,
    *,
    staging_source: Path,
    dispatched_dest: Path,
) -> None:
    """Correlate staging_source to a live seeding torrent and write a seed obligation.

    Write-before-move guarantee: called BEFORE the FS move.
    Lock-free + fail-soft: uses a raw sqlite3 connection with busy_timeout,
    swallows all errors so the caller is never interrupted.

    Correlation method: basename + total_size match against get_completed().
    Only is_seeding=True torrents carry a live obligation.

    Logs HIT/MISS with miss-reason (no-client | no-live-torrent | not-seeding
    | name+size-ambiguous).

    Args:
        staging_source: Absolute path of the file in the staging area.
        dispatched_dest: Absolute path of the destination after dispatch.
    """
    if self._store is None or self._torrent_client is None:
        log.debug(
            "acquire.record_dispatch.miss",
            miss_reason="no-client",
            staging_source=str(staging_source),
        )
        return

    try:
        completed = self._torrent_client.get_completed()
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "acquire.record_dispatch.miss",
            miss_reason="client-error",
            error=str(exc),
            staging_source=str(staging_source),
        )
        return

    basename = staging_source.name
    try:
        size = staging_source.stat().st_size
    except OSError:
        log.warning(
            "acquire.record_dispatch.miss",
            miss_reason="stat-error",
            staging_source=str(staging_source),
        )
        return

    # Filter to seeding torrents with matching basename + size
    matches = [
        t for t in completed
        if t.name == basename and t.total_size == size and t.is_seeding()
    ]

    if not matches:
        log.debug(
            "acquire.record_dispatch.miss",
            miss_reason="no-live-torrent",
            basename=basename,
            size=size,
        )
        return

    if len(matches) > 1:
        log.warning(
            "acquire.record_dispatch.miss",
            miss_reason="name+size-ambiguous",
            basename=basename,
            match_count=len(matches),
        )
        return

    torrent = matches[0]

    # Write obligation BEFORE the move (lock-free fail-soft raw connection)
    try:
        import sqlite3 as _sqlite3
        db_path = self._store._db_path
        conn = _sqlite3.connect(str(db_path), timeout=5.0)
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute(
            """
            INSERT INTO seed_obligation
              (info_hash, source_tracker, dispatched_path,
               min_seed_time_s, min_ratio, added_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                torrent.info_hash,
                getattr(torrent, "tracker", "unknown"),
                str(dispatched_dest),
                0,   # min_seed_time_s: filled by Phase 5 economy lookup
                0.0, # min_ratio: filled by Phase 5 economy lookup
                int(time.time()),
            ),
        )
        conn.commit()
        conn.close()
        log.info(
            "acquire.record_dispatch.hit",
            info_hash=torrent.info_hash,
            basename=basename,
            dispatched_dest=str(dispatched_dest),
        )
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "acquire.record_dispatch.write_failed",
            error=str(exc),
            basename=basename,
        )
```

- [ ] **Step 4: Update `build_delete_authority` signature**

```python
def build_delete_authority(
    store: "ConcreteAcquireStore | None",
    torrent_client=None,
) -> DeleteAuthority:
    return DeleteAuthority(store=store, torrent_client=torrent_client)
```

- [ ] **Step 5: Run record_dispatch tests — expect PASS**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/acquire/test_record_dispatch.py -v 2>&1 | tail -15
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add personalscraper/acquire/delete_authority.py tests/acquire/test_record_dispatch.py
git commit -m "feat(acquire-store): record_dispatch — basename+size correlation, write-before-move, HIT/MISS log"
```

---

### Task 2 — Inject permit + recorder into `dispatch/run.py` and `Dispatcher`

**Files:**

- Modify: `personalscraper/dispatch/run.py`
- Modify: `personalscraper/dispatch/dispatcher.py`

- [ ] **Step 1: Add `permit` and `recorder` params to `Dispatcher.__init__`**

In `personalscraper/dispatch/dispatcher.py`:

Add to imports (TYPE_CHECKING to avoid circular):

```python
from personalscraper.core.delete_permit import AllowAllPermit, DeletePermit, SeedObligationRecorder
```

Add params to `Dispatcher.__init__` with `AllowAllPermit()` defaults:

```python
def __init__(
    self,
    config: Config,
    settings: Settings,
    index: MediaIndex,
    dry_run: bool = False,
    *,
    event_bus: EventBus,
    permit: DeletePermit = AllowAllPermit(),    # injected at composition root
    recorder: SeedObligationRecorder = AllowAllPermit(),
):
    ...
    self._permit = permit
    self._recorder = recorder
```

Update docstring to document `permit` and `recorder` params.

- [ ] **Step 2: Forward permit/recorder from `run_dispatch` to `Dispatcher`**

In `personalscraper/dispatch/run.py`, update `run_dispatch` signature and `Dispatcher(...)` call:

```python
from personalscraper.core.delete_permit import AllowAllPermit, DeletePermit, SeedObligationRecorder

def run_dispatch(
    ...,
    permit: DeletePermit = AllowAllPermit(),
    recorder: SeedObligationRecorder = AllowAllPermit(),
) -> StepReport:
    ...
    dispatcher = Dispatcher(
        ...,
        permit=permit,
        recorder=recorder,
    )
```

- [ ] **Step 3: Wire from `DispatchStep` via `AppContext`**

In the composition root / pipeline step that invokes `run_dispatch`, forward
`ctx.app.acquire.delete_authority` as both `permit=` and `recorder=`. Locate the dispatch
step class:

```bash
rg "run_dispatch\|DispatchStep" --type py /Users/izno/dev/PersonnalScaper/personalscraper/ 2>/dev/null | head -20
```

In that file, change the `run_dispatch(...)` call to pass:

```python
authority = getattr(getattr(ctx.app, "acquire", None), "delete_authority", None)
from personalscraper.core.delete_permit import AllowAllPermit
permit = authority if authority is not None else AllowAllPermit()
run_dispatch(..., permit=permit, recorder=permit)
```

- [ ] **Step 4: Verify dispatch still works**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/dispatch/ -x -q 2>&1 | tail -15
```

Expected: all pass (defaults are `AllowAllPermit()` so existing tests unaffected).

- [ ] **Step 5: Commit**

```bash
git add personalscraper/dispatch/dispatcher.py personalscraper/dispatch/run.py
git commit -m "feat(acquire-store): inject DeletePermit + SeedObligationRecorder into Dispatcher"
```

---

### Task 3 — Three-state dispatch policy in `_movie.py` and `_tv.py`

**Files:**

- Modify: `personalscraper/dispatch/_movie.py`
- Modify: `personalscraper/dispatch/_tv.py`

- [ ] **Step 1: Locate the deletion sites in `_movie.py` and `_tv.py`**

```bash
rg "shutil.rmtree\|os.unlink\|\.unlink\|rmtree\|delete\|remove" --type py \
  /Users/izno/dev/PersonnalScaper/personalscraper/dispatch/_movie.py \
  /Users/izno/dev/PersonnalScaper/personalscraper/dispatch/_tv.py 2>/dev/null | head -20
```

- [ ] **Step 2: Apply three-state policy at each deletion site in `_movie.py`**

> **CORRECTIVE NOTE (sub-phase 5.3, applied):** the original draft below reached into
> `self._recorder._store.seed._conn` with raw SQL + `hasattr` probing. That is replaced by
> the clean `mark_breach(path)` port method added to the `SeedObligationRecorder` Protocol in
> sub-phase 5.1 (`AllowAllPermit.mark_breach` is the fail-soft no-op default). Dispatch code
> NEVER touches the store internals — it depends only on `core.delete_permit`. Also note the
> dispatch sub-modules are FREE functions taking `dispatcher`, so the call sites use
> `dispatcher._permit` / `dispatcher._recorder` (not `self.`), and the whole block is gated on
> `not dispatcher.dry_run` so dry-run stays side-effect-free. The implemented pattern:

```python
from personalscraper.core.delete_permit import ALLOW

# In the replace (movie) / merge (tv) branch, after the dry-run early-return,
# BEFORE the replace()/merge() FS move (dest = existing on-disk path):
decision = dispatcher._permit.may_delete(dest)
if decision is not ALLOW:
    # Real media wins (O3) — proceed anyway, but record the breach (never silent).
    # Relocate-not-delete is deferred to O2/O3.
    log.warning("acquire.hnr_risk", path=str(dest), reason=str(decision), action="replace")  # "merge" in _tv
    dispatcher._recorder.mark_breach(dest)
# Write-before-move (DESIGN §7.2): record the NEW media's obligation BEFORE the
# FS move so a crash mid-move never loses the safety constraint. Fail-soft.
dispatcher._recorder.record_dispatch(staging_source=movie_dir, dispatched_dest=dest)  # show_dir in _tv
success = replace(movie_dir, dest, capability=cap)  # merge(show_dir, dest, ...) in _tv
```

The `_move_new` (new-media) branch also calls `record_dispatch` write-before-move (the new
media may itself be seeding) but takes **no** permit consult / `mark_breach` — there is no
pre-existing library content to delete there. Apply the same pattern in `_tv.py` at the
merge-deletion site (`action="merge"`, `staging_source=show_dir`).

- [ ] **Step 3: Run dispatch tests**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/dispatch/ -x -q 2>&1 | tail -15
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add personalscraper/dispatch/_movie.py personalscraper/dispatch/_tv.py
git commit -m "feat(acquire-store): three-state dispatch policy — breached_at + acquire.hnr_risk log"
```

---

### Task 4 — Hard-skip on VETO in `disk_cleaner.py`

**Files:**

- Modify: `personalscraper/maintenance/disk_cleaner.py`

> **CORRECTIVE NOTE (2026-06-10, sub-phase 5.4):** Built as specified with the
> following refinements vs the original plan:
>
> - The VETO consult sits at the **top** of `_delete_dir` / `_delete_file`
>   **before the dry-run branch** so dry-run previews correctly show what would
>   be skipped — the plan's "before each real deletion" was corrected to
>   "before the dry-run/real branch".
> - `permit` threading reaches ALL deletion executors: `clean_library` →
>   `_clean_media_dir` → `_delete_dir` / `_delete_file`, AND the direct
>   `_delete_dir` call inside the `clean_library` orphan path.
> - Command wiring (Step 3) uses `per_step_boundary(config, settings)` like
>   `library_verify`, NOT a direct `AllowAllPermit()` placeholder — the real
>   `DeleteAuthority` is built at the boundary and injected fail-open:
>   `app_context.acquire.delete_authority` → `permit`, falling back to
>   `AllowAllPermit()` on any store/acquire failure (§9 fail-open).
> - `per_step_boundary` is independent of the existing `pipeline.lock`
>   (`acquire_lock`/`release_lock`) — both coexist without conflict.
> - Tests added: 5 hard-skip tests (VETO actor, VETO junk, dry-run skip
>   count, ALLOW permit, fail-open default) + 1 E2E event-expectation update.
> - disk_cleaner.py imports ONLY `core.delete_permit` — never `acquire/`.
> - `skipped_by_obligation` is reported in CLI output for both dry-run and
>   apply modes.
>
> Commits: `a8d60e66`, `aafeaa2e`

- [ ] **Step 1: Add `permit` param to `clean_library`**

In `personalscraper/maintenance/disk_cleaner.py`:

```python
from personalscraper.core.delete_permit import ALLOW, AllowAllPermit, DeletePermit

def clean_library(
    config: Config,
    apply: bool = False,
    only: str | None = None,
    disk_filter: str | None = None,
    category_filter: str | None = None,
    permit: DeletePermit = AllowAllPermit(),   # injected; defaults to fail-open
) -> CleanResult:
```

Update docstring to document `permit` param.

- [ ] **Step 2: Apply hard-skip at each deletion site**

Before each real deletion in `clean_library` / its helpers, add:

```python
decision = permit.may_delete(target_path)
if decision is not ALLOW:
    log.info(
        "disk_cleaner.skipped_by_obligation",
        path=str(target_path),
        reason=str(decision),
    )
    result.skipped_by_obligation += 1
    continue
```

Also add `skipped_by_obligation: int = 0` to `CleanResult` dataclass.

- [ ] **Step 3: Wire permit from `commands/library/maintenance.py`**

Locate the maintenance command that calls `clean_library`:

```bash
rg "clean_library" --type py /Users/izno/dev/PersonnalScaper/personalscraper/ 2>/dev/null | head -10
```

In that command file, build the delete authority and pass it:

```python
# maintenance has no AppContext — build at command boundary:
from personalscraper.core.delete_permit import AllowAllPermit
permit = AllowAllPermit()  # Phase 5 wires real authority; for now fail-open
clean_library(config, ..., permit=permit)
```

- [ ] **Step 4: Run maintenance tests**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/maintenance/ -x -q 2>&1 | tail -15
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add personalscraper/maintenance/disk_cleaner.py
git commit -m "feat(acquire-store): disk_cleaner hard-skip on VETO (skipped_by_obligation counter)"
```

---

### Task 5 — Crash-window tests + phase gate

**Files:**

- Create: `tests/acquire/test_crash_window.py`

- [ ] **Step 1: Write crash-window tests**

```python
# tests/acquire/test_crash_window.py
"""Crash-window tests for acquire/delete_authority (DESIGN §12).

Scenario 1: move-then-kill-before-obligation — storage path can't help but no
  over-delete because obligation absent → ALLOW is acceptable.
Scenario 2: obligation-then-kill-before-move — stale obligation inert via
  path-exists guard, re-run completes.
Scenario 3: concurrent acquire writer holds lock while dispatch writes —
  lock-free path does not hang, proceeds.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from personalscraper.acquire.delete_authority import DeleteAuthority, build_delete_authority
from personalscraper.acquire.domain import SeedObligation
from personalscraper.acquire.store import build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.delete_permit import ALLOW


@pytest.fixture()
def store(tmp_path: Path):
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s = build_acquire_store(cfg)
    yield s
    s.close()


def test_scenario1_no_obligation_after_move_allows(store, tmp_path: Path) -> None:
    """Scenario 1: obligation was never written (crash before record_dispatch).

    The deletion authority has no record → ALLOW (acceptable, safe).
    """
    path = tmp_path / "movie.mkv"
    path.write_text("fake")
    auth = build_delete_authority(store=store)
    # No obligation written — simulates crash before record_dispatch
    decision = auth.may_delete(path)
    assert decision is ALLOW


def test_scenario2_stale_obligation_inert_via_path_guard(store, tmp_path: Path) -> None:
    """Scenario 2: obligation written but move never happened (crash before move).

    dispatched_path does not exist → path-exists guard makes obligation inert → ALLOW.
    Re-run should proceed safely.
    """
    dest = tmp_path / "library" / "movie.mkv"
    # Do NOT create dest — simulates crash before the FS move
    ob = SeedObligation(
        info_hash="abc",
        source_tracker="lacale",
        min_seed_time_s=999999,
        min_ratio=1.0,
        added_at=int(time.time()),
        dispatched_path=str(dest),
    )
    store.seed.add(ob)
    auth = build_delete_authority(store=store)
    decision = auth.may_delete(dest)
    assert decision is ALLOW


def test_scenario3_concurrent_write_does_not_hang(tmp_path: Path) -> None:
    """Scenario 3: lock-free record_dispatch write does not block when DB is busy.

    The lock-free path uses raw sqlite3 + busy_timeout, so it does not
    attempt to acquire acquire.db.lock and cannot deadlock.
    """
    db_path = tmp_path / "acquire.db"
    cfg = AcquireConfig(db_path=db_path)
    store = build_acquire_store(cfg)

    staging = tmp_path / "staging" / "movie.mkv"
    staging.parent.mkdir()
    staging.write_bytes(b"x" * 100)
    dest = tmp_path / "library" / "movie.mkv"

    torrent = MagicMock()
    torrent.name = "movie.mkv"
    torrent.total_size = 100
    torrent.is_seeding.return_value = True
    torrent.info_hash = "deadbeef12345678"
    torrent.tracker = "lacale"

    mock_client = MagicMock()
    mock_client.get_completed.return_value = [torrent]

    auth = DeleteAuthority(store=store, torrent_client=mock_client)

    # Hold the DB writer lock in the "outer" process
    from personalscraper.core.sqlite._lock import db_lock
    with db_lock(db_path, timeout=0):
        # record_dispatch uses lock-free path — should NOT block or raise
        import threading
        result = {}

        def _call():
            try:
                auth.record_dispatch(staging_source=staging, dispatched_dest=dest)
                result["ok"] = True
            except Exception as exc:
                result["error"] = str(exc)

        t = threading.Thread(target=_call)
        t.start()
        t.join(timeout=5.0)
        assert result.get("ok") is True, f"record_dispatch hung or raised: {result}"

    store.close()
```

> **CORRECTIVE NOTE (sub-phase 5.5): Scenario 3 above is STALE.** Sub-phase 3.4
> dropped the lifetime FileLock; the real store uses lazy-open + SQLite-native
> single-writer (WAL + BEGIN IMMEDIATE + busy_timeout=5000) + lock-free reads
> (DESIGN §6.3). No `db_lock` is held for the store's lifetime, so there is no
> lock to "hold while dispatch writes." The implemented test
> (`test_scenario3_two_stores_same_db_no_deadlock`) proves the REAL model: two
> stores on the same `db_path` both open, read (lock-free WAL), and write
> (BEGIN IMMEDIATE serializes them; no hang, no AcquireLockError). The plan
> draft's `db_lock(db_path, timeout=0)` + threading scenario would fail because
> `record_dispatch` writes through the store (which uses `BEGIN IMMEDIATE`
> under the shared connection, NOT a raw sqlite3 path), and the FileLock is
> only held briefly around open+migrate — it is never held by the time
> `record_dispatch` runs. The new test is a correct, deterministic,
> single-process demonstration of the lock-free-concurrency model.

- [ ] **Step 2: Run crash-window tests — expect PASS**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/acquire/test_crash_window.py -v 2>&1 | tail -15
```

Expected: `5 passed` (4 scenarios; Scenario 2 split into stale-inert + re-runnable)

- [ ] **Step 3: Run full test suite**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/acquire/ tests/dispatch/ tests/maintenance/ -x -q 2>&1 | tail -20
```

Expected: all pass.

- [ ] **Step 4: Run make check (phase gate)**

```bash
cd /Users/izno/dev/PersonnalScaper && make check 2>&1 | tail -30
```

Expected: green.

- [ ] **Step 5: Commit**

```bash
git add tests/acquire/test_crash_window.py
git commit -m "chore(acquire-store): phase 5 gate — dispatch wiring + per-site policy + crash-window tests"
```
