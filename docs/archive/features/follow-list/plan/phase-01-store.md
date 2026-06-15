# Phase 1 — Store CRUD (`_FollowSubStore` completion + Protocol)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `FollowedSeries.id`, `find_by_ref`, `list_active`, `list_all`, `set_active` to `_FollowSubStore` and update `FollowSubStore` Protocol in `_ports.py`.

**Architecture:** All changes are inside `acquire/` (imports `core/conf/stdlib` only). `FollowedSeries.id` mirrors the `WantedItem.id` pattern already shipped. `_row_to_followed` must carry `id`. Every write uses `_write_tx`.

**Tech Stack:** Python 3.12+, SQLite WAL, `_write_tx` context manager (~L226 store.py), frozen dataclasses.

## Gate (start of phase)

This phase has no predecessor. The `acquire.db` schema already has a `followed_series` table with an `id` INTEGER PRIMARY KEY (see `acquire/migrations/001_init.sql`). `_FollowSubStore.add` and `.get` already exist. `FollowedSeries` does **not** yet carry `id`. Verify:

```bash
rg "id.*int.*None" personalscraper/acquire/domain.py --type py
# Expected: WantedItem has it but FollowedSeries does not
rg "find_by_ref\|list_active\|list_all\|set_active" personalscraper/acquire/store.py --type py
# Expected: no matches
```

---

## Task 1: Add `FollowedSeries.id` field + update `_row_to_followed`

**Files:**

- Modify: `personalscraper/acquire/domain.py` (~L24 — `FollowedSeries` dataclass)
- Modify: `personalscraper/acquire/store.py` (~L139 — `_row_to_followed`)

### Sub-phase 1.1 — `FollowedSeries.id` field

- [ ] **Step 1.1.1: Add `id: int | None = None` to `FollowedSeries`**

  Mirror the `WantedItem.id` pattern (domain.py ~L79). Add the field **after** `cadence_json` so default-less fields come first:

  ```python
  # personalscraper/acquire/domain.py  (~L24)
  @dataclass(frozen=True)
  class FollowedSeries:
      """A TV series or movie the user wants to automatically acquire.

      Attributes:
          media_ref: Provider-ID key (tvdb_id primary).
          title: Human-readable title (for logging/display).
          active: Whether this series is actively searched.
          added_at: Unix epoch seconds when the series was followed.
          quality_profile_json: Nullable JSON string; rich profile = RP3a.
          cadence_json: Nullable JSON string; RP9/D2.
          id: SQLite rowid — populated by ``find_by_ref()`` / ``list_active()`` /
              ``list_all()`` / ``get()``; ``None`` for an as-yet-unpersisted item.
              The follow CLI needs it to call ``set_active`` (Follow D1).
      """

      media_ref: MediaRef
      title: str
      added_at: int
      active: bool = True
      quality_profile_json: str | None = None
      cadence_json: str | None = None
      id: int | None = None
  ```

- [ ] **Step 1.1.2: Update `_row_to_followed` to carry `id` (store.py ~L139)**

  Add `id=row["id"]` — the column is already in the schema. The existing `get()` SELECT does NOT include `id`; fix it too:

  ```python
  def _row_to_followed(row: sqlite3.Row) -> FollowedSeries:
      """Map a ``followed_series`` row to a :class:`FollowedSeries`.

      Args:
          row: A :class:`sqlite3.Row` from a ``followed_series`` SELECT.
              Must include the ``id`` column.

      Returns:
          The frozen :class:`FollowedSeries` value object with ``id`` set.
      """
      return FollowedSeries(
          id=row["id"],
          media_ref=_media_ref_from_json(row["media_ref_json"]),
          title=row["title"],
          added_at=row["added_at"],
          active=bool(row["active"]),
          quality_profile_json=row["quality_profile_json"],
          cadence_json=row["cadence_json"],
      )
  ```

- [ ] **Step 1.1.3: Fix `_FollowSubStore.get` SELECT to include `id`**

  Existing SELECT at ~L310 omits `id`. Replace with:

  ```python
  row = self._conn.execute(
      """
      SELECT id, media_ref_json, title, active,
             quality_profile_json, cadence_json, added_at
      FROM followed_series WHERE id = ?
      """,
      (followed_id,),
  ).fetchone()
  ```

- [ ] **Step 1.1.4: Write a failing test**

  In `tests/acquire/test_store.py`, add after the existing `test_follow_round_trip`:

  ```python
  def test_follow_get_round_trips_id(store: ConcreteAcquireStore) -> None:
      """follow.get populates FollowedSeries.id with the rowid."""
      series = FollowedSeries(
          media_ref=MediaRef(tvdb_id=10001),
          title="Id Roundtrip Show",
          added_at=1_700_000_000,
          active=True,
      )
      row_id = store.follow.add(series)
      fetched = store.follow.get(row_id)
      assert fetched is not None
      assert fetched.id == row_id, f"Expected id={row_id}, got {fetched.id}"
  ```

- [ ] **Step 1.1.5: Run test to confirm it fails**

  ```bash
  python -m pytest tests/acquire/test_store.py::test_follow_get_round_trips_id -v
  ```

  Expected: FAIL (AttributeError or assertion error because `id` is absent).

- [ ] **Step 1.1.6: Run test to confirm it passes**

  ```bash
  python -m pytest tests/acquire/test_store.py::test_follow_get_round_trips_id -v
  ```

  Expected: PASS.

- [ ] **Step 1.1.7: Commit**

  ```bash
  git add personalscraper/acquire/domain.py personalscraper/acquire/store.py tests/acquire/test_store.py
  git commit -m "feat(follow-list): add FollowedSeries.id + carry id in _row_to_followed"
  ```

---

## Task 2: Add `find_by_ref`, `list_active`, `list_all`

**Files:**

- Modify: `personalscraper/acquire/store.py` (`_FollowSubStore` class, ~L259)

### Sub-phase 1.2 — read methods

- [ ] **Step 1.2.1: Write failing tests for `find_by_ref` + `list_active` + `list_all`**

  Add to `tests/acquire/test_store.py`:

  ```python
  def test_follow_find_by_ref_returns_none_when_absent(store: ConcreteAcquireStore) -> None:
      """find_by_ref returns None when no matching row exists."""
      assert store.follow.find_by_ref(MediaRef(tvdb_id=99999)) is None


  def test_follow_find_by_ref_round_trips_id(store: ConcreteAcquireStore) -> None:
      """find_by_ref locates the row and populates .id correctly (LOAD-BEARING dedup check)."""
      series = FollowedSeries(
          media_ref=MediaRef(tvdb_id=55555),
          title="Dedup Show",
          added_at=1_700_000_000,
          active=True,
      )
      row_id = store.follow.add(series)
      found = store.follow.find_by_ref(MediaRef(tvdb_id=55555))
      assert found is not None
      assert found.id == row_id
      assert found.media_ref == series.media_ref

      # LOAD-BEARING: second call with the same ref finds the SAME row (1 row only).
      found2 = store.follow.find_by_ref(MediaRef(tvdb_id=55555))
      assert found2 is not None
      assert found2.id == row_id  # same rowid, no duplicate


  def test_follow_list_active_excludes_inactive(store: ConcreteAcquireStore) -> None:
      """list_active returns only active=True rows (LOAD-BEARING filter check)."""
      active_series = FollowedSeries(
          media_ref=MediaRef(tvdb_id=1001),
          title="Active Show",
          added_at=1_700_000_001,
          active=True,
      )
      inactive_series = FollowedSeries(
          media_ref=MediaRef(tvdb_id=1002),
          title="Inactive Show",
          added_at=1_700_000_002,
          active=False,
      )
      store.follow.add(active_series)
      store.follow.add(inactive_series)

      active_list = store.follow.list_active()
      assert len(active_list) == 1, f"Expected 1 active row, got {len(active_list)}"
      assert active_list[0].title == "Active Show"
      assert active_list[0].active is True


  def test_follow_list_all_includes_both(store: ConcreteAcquireStore) -> None:
      """list_all returns all rows regardless of active flag."""
      store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=2001), title="A", added_at=1, active=True))
      store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=2002), title="B", added_at=2, active=False))
      all_rows = store.follow.list_all()
      assert len(all_rows) == 2
      tvdb_ids = {r.media_ref.tvdb_id for r in all_rows}
      assert tvdb_ids == {2001, 2002}
  ```

- [ ] **Step 1.2.2: Run tests to confirm they fail**

  ```bash
  python -m pytest tests/acquire/test_store.py -k "find_by_ref or list_active or list_all" -v
  ```

  Expected: FAIL (AttributeError — methods don't exist yet).

- [ ] **Step 1.2.3: Implement `find_by_ref`, `list_active`, `list_all` in `_FollowSubStore`**

  Add these methods inside `_FollowSubStore` (after the existing `get` method, ~L318):

  ```python
  def find_by_ref(self, media_ref: MediaRef) -> FollowedSeries | None:
      """Return the :class:`FollowedSeries` keyed on *media_ref*, or ``None``.

      Matches on the canonical ``media_ref_json`` serialization so that any
      combination of provider IDs (tvdb/tmdb/imdb) deduplicates correctly.
      Used by the follow CLI to enforce the idempotent-add / reactivate logic.

      Args:
          media_ref: Provider-ID key to look up.

      Returns:
          The :class:`FollowedSeries` (with ``id`` populated) if found, else
          ``None``.
      """
      self._conn.row_factory = sqlite3.Row
      row = self._conn.execute(
          """
          SELECT id, media_ref_json, title, active,
                 quality_profile_json, cadence_json, added_at
          FROM followed_series
          WHERE media_ref_json = ?
          LIMIT 1
          """,
          (_media_ref_to_json(media_ref),),
      ).fetchone()
      return _row_to_followed(row) if row is not None else None

  def list_active(self) -> list[FollowedSeries]:
      """Return all active ``followed_series`` rows, ordered by id.

      Returns:
          A list of :class:`FollowedSeries` where ``active=True``,
          possibly empty.
      """
      self._conn.row_factory = sqlite3.Row
      rows = self._conn.execute(
          """
          SELECT id, media_ref_json, title, active,
                 quality_profile_json, cadence_json, added_at
          FROM followed_series
          WHERE active = 1
          ORDER BY id
          """
      ).fetchall()
      return [_row_to_followed(r) for r in rows]

  def list_all(self) -> list[FollowedSeries]:
      """Return all ``followed_series`` rows (active and inactive), ordered by id.

      Used by ``follow list --all``.

      Returns:
          A list of all :class:`FollowedSeries`, possibly empty.
      """
      self._conn.row_factory = sqlite3.Row
      rows = self._conn.execute(
          """
          SELECT id, media_ref_json, title, active,
                 quality_profile_json, cadence_json, added_at
          FROM followed_series
          ORDER BY id
          """
      ).fetchall()
      return [_row_to_followed(r) for r in rows]
  ```

- [ ] **Step 1.2.4: Run tests to confirm they pass**

  ```bash
  python -m pytest tests/acquire/test_store.py -k "find_by_ref or list_active or list_all" -v
  ```

  Expected: all 4 tests PASS.

- [ ] **Step 1.2.5: Commit**

  ```bash
  git add personalscraper/acquire/store.py tests/acquire/test_store.py
  git commit -m "feat(follow-list): add find_by_ref, list_active, list_all to _FollowSubStore"
  ```

---

## Task 3: Add `set_active`

**Files:**

- Modify: `personalscraper/acquire/store.py` (`_FollowSubStore` class)

### Sub-phase 1.3 — `set_active` write method

- [ ] **Step 1.3.1: Write failing test for `set_active`**

  Add to `tests/acquire/test_store.py`:

  ```python
  def test_follow_set_active_flips_flag(store: ConcreteAcquireStore) -> None:
      """set_active(id, False) soft-unfollows; set_active(id, True) reactivates (LOAD-BEARING)."""
      series = FollowedSeries(
          media_ref=MediaRef(tvdb_id=77777),
          title="Flip Show",
          added_at=1_700_000_000,
          active=True,
      )
      row_id = store.follow.add(series)

      # Soft unfollow.
      store.follow.set_active(row_id, False)
      after_unfollow = store.follow.get(row_id)
      assert after_unfollow is not None
      assert after_unfollow.active is False, "Expected active=False after set_active(id, False)"

      # Reactivate — must be the SAME row, not a new one.
      store.follow.set_active(row_id, True)
      after_reactivate = store.follow.get(row_id)
      assert after_reactivate is not None
      assert after_reactivate.active is True, "Expected active=True after set_active(id, True)"
      assert after_reactivate.id == row_id, "Reactivate must update the existing row, not insert a new one"

      # list_active reflects the change.
      active_list = store.follow.list_active()
      assert any(s.id == row_id for s in active_list), "Reactivated row must appear in list_active()"
  ```

- [ ] **Step 1.3.2: Run test to confirm it fails**

  ```bash
  python -m pytest tests/acquire/test_store.py::test_follow_set_active_flips_flag -v
  ```

  Expected: FAIL (AttributeError).

- [ ] **Step 1.3.3: Implement `set_active` in `_FollowSubStore`**

  Add after `list_all` (~L370 once the previous methods are added):

  ```python
  def set_active(self, followed_id: int, active: bool) -> None:
      """Set the ``active`` flag on a ``followed_series`` row.

      Used for both soft unfollow (``active=False``) and refollow
      (``active=True``).  Runs inside a single ``_write_tx`` BEGIN IMMEDIATE
      so concurrent callers serialize correctly.

      Args:
          followed_id: Rowid of the ``followed_series`` row.
          active: ``True`` to refollow; ``False`` to soft-unfollow.
      """
      with _write_tx(self._conn):
          self._conn.execute(
              "UPDATE followed_series SET active = ? WHERE id = ?",
              (1 if active else 0, followed_id),
          )
  ```

- [ ] **Step 1.3.4: Run test to confirm it passes**

  ```bash
  python -m pytest tests/acquire/test_store.py::test_follow_set_active_flips_flag -v
  ```

  Expected: PASS.

- [ ] **Step 1.3.5: Commit**

  ```bash
  git add personalscraper/acquire/store.py tests/acquire/test_store.py
  git commit -m "feat(follow-list): add set_active to _FollowSubStore"
  ```

---

## Task 4: Update `FollowSubStore` Protocol in `_ports.py`

**Files:**

- Modify: `personalscraper/acquire/_ports.py` (~L37 — `FollowSubStore` Protocol)

### Sub-phase 1.4 — Protocol completeness

- [ ] **Step 1.4.1: Write failing test for Protocol conformance**

  Add to `tests/acquire/test_store.py`:

  ```python
  def test_follow_substore_satisfies_protocol(store: ConcreteAcquireStore) -> None:
      """_FollowSubStore satisfies the FollowSubStore Protocol (all new methods present)."""
      from personalscraper.acquire._ports import FollowSubStore as FollowSubStoreProto

      follow_sub = store.follow
      assert isinstance(follow_sub, FollowSubStoreProto), (
          "Expected _FollowSubStore to satisfy the FollowSubStore Protocol; "
          f"missing: {[m for m in ('add','get','find_by_ref','list_active','list_all','set_active') if not hasattr(follow_sub, m)]}"
      )
  ```

- [ ] **Step 1.4.2: Run test to confirm it fails**

  ```bash
  python -m pytest tests/acquire/test_store.py::test_follow_substore_satisfies_protocol -v
  ```

  Expected: FAIL (Protocol mismatch — new methods missing from Protocol).

- [ ] **Step 1.4.3: Add new methods to `FollowSubStore` Protocol**

  In `personalscraper/acquire/_ports.py`, extend the `FollowSubStore` Protocol (~L37):

  ```python
  @runtime_checkable
  class FollowSubStore(Protocol):
      """Writer + reader for the ``followed_series`` table."""

      def add(self, series: FollowedSeries) -> int:
          """Insert a :class:`FollowedSeries` row and return its rowid."""
          ...

      def get(self, followed_id: int) -> FollowedSeries | None:
          """Return the :class:`FollowedSeries` for *followed_id*, or ``None``."""
          ...

      def find_by_ref(self, media_ref: MediaRef) -> FollowedSeries | None:
          """Return the :class:`FollowedSeries` keyed on *media_ref*, or ``None``."""
          ...

      def list_active(self) -> list[FollowedSeries]:
          """Return all active ``followed_series`` rows, ordered by id."""
          ...

      def list_all(self) -> list[FollowedSeries]:
          """Return all ``followed_series`` rows (active and inactive), ordered by id."""
          ...

      def set_active(self, followed_id: int, active: bool) -> None:
          """Set the ``active`` flag on a ``followed_series`` row."""
          ...
  ```

  Add the `MediaRef` import at the top of `_ports.py` if absent:

  ```python
  from personalscraper.core.identity import MediaRef
  ```

- [ ] **Step 1.4.4: Run test to confirm it passes**

  ```bash
  python -m pytest tests/acquire/test_store.py::test_follow_substore_satisfies_protocol -v
  ```

  Expected: PASS.

- [ ] **Step 1.4.5: Run the full acquire test suite**

  ```bash
  python -m pytest tests/acquire/ -v
  ```

  Expected: all tests PASS, 0 errors.

- [ ] **Step 1.4.6: Smoke test import**

  ```bash
  python -c "from personalscraper.acquire._ports import FollowSubStore; print('ok')"
  ```

  Expected: `ok`.

- [ ] **Step 1.4.7: Commit**

  ```bash
  git add personalscraper/acquire/_ports.py tests/acquire/test_store.py
  git commit -m "feat(follow-list): extend FollowSubStore Protocol with find_by_ref/list_active/list_all/set_active"
  ```

---

## Phase 1 completion check

```bash
python -m pytest tests/acquire/ -v
# Expected: all existing + new tests pass, 0 errors.

rg "find_by_ref\|list_active\|list_all\|set_active" personalscraper/acquire/store.py --type py
# Expected: 4 method definitions

rg "find_by_ref\|list_active\|list_all\|set_active" personalscraper/acquire/_ports.py --type py
# Expected: 4 method stubs in the Protocol

python -c "from personalscraper.acquire.domain import FollowedSeries; s = FollowedSeries.__dataclass_fields__; print('id' in s)"
# Expected: True
```
