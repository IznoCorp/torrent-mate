# DESIGN — RP6: "do I already own this?" ownership predicate

| Field                        | Value                                                                                                                                                                                                   |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Codename (proposed)**      | `ownership`                                                                                                                                                                                             |
| **Roadmap item**             | RP6 (P2, parallèle) — "prédicat « je possède déjà » dans la couche de requête de l'indexer"                                                                                                             |
| **Type**                     | minor                                                                                                                                                                                                   |
| **Version bump**             | 0.29.0 → 0.30.0                                                                                                                                                                                         |
| **Date**                     | 2026-06-14                                                                                                                                                                                              |
| **Status**                   | PREPARED (design only — not branched/committed; awaiting go)                                                                                                                                            |
| **Depends on (all shipped)** | indexer `library.db` (media_item/season/episode/media_release/media_file), indexer `query.py`, `core.identity.MediaRef`, the port+composition-root pattern from `core/delete_permit.py` (acquire-store) |
| **Unblocks**                 | Follow D2 (don't enqueue what you own), Ratio C1                                                                                                                                                        |
| **Scope decisions**          | A (owned = a live file exists), B (core port + indexer adapter + composition-root wiring — like delete_permit), C (RP6 provides+wires; D2/Ratio consume later)                                          |

> Follow D2 must not enqueue (and Ratio must not grab) media the library already has. There is no
> "do I own this?" predicate today. RP6 adds it **in the indexer query layer** (per ROADMAP) and
> exposes it **across the acquire⇄indexer boundary via a port** — `acquire/` consumes ownership
> without importing the indexer, exactly as it consumes deletion authority via `core.delete_permit`.
> RP6 ships the capability **wired but not yet consumed** (like RP4 events shipped muted); Follow D2
> and Ratio C1 are the consumers.

---

## 1. The boundary problem (the load-bearing design decision)

The ROADMAP places the predicate "dans la couche de requête de l'indexer" and says ownership is read
"**en SELECT-only à travers la frontière**" (line 49). But the consumer (Follow D2) lives in `acquire/`,
which by the layering guard imports **only** `api/core/conf/events` — **never triage** (and `indexer/`
is triage). So `acquire/` cannot `import personalscraper.indexer.query`.

**Solution — a port (mirrors `core/delete_permit.py`):**

- A neutral **`OwnershipChecker` Protocol** in `core/ownership.py` (`@runtime_checkable`), keyed on the
  neutral `MediaRef`. `acquire/` depends on the port, never the indexer.
- The **SQL predicate** lives in the indexer query layer (per ROADMAP).
- An **indexer-backed adapter** (`indexer/ownership.py::IndexerOwnershipChecker`) implements the port
  using the predicate. `indexer/` may import `core/` (the port) — allowed direction.
- The **composition root** builds the adapter from the `library.db` connection and injects it into the
  AppContext so the acquire lobe receives the port impl (it never sees the indexer).

This is the same shape as the deletion authority (core port ← indexer/acquire impls ← composition-root
wiring) — a proven pattern in this codebase.

## 2. Goals / Non-goals

**Goals**

1. `core/ownership.py` — `OwnershipChecker` Protocol + a `NullOwnershipChecker` default (fail-open: returns "not owned" when no library is available, so a wanted item is never silently skipped).
2. Indexer query-layer predicate (`indexer/query.py` or `indexer/ownership.py`): `is_owned(conn, *, kind, tvdb_id, tmdb_id, imdb_id, season=None, episode=None) -> bool` — SELECT-only.
3. `indexer/ownership.py::IndexerOwnershipChecker` — the port impl over the predicate.
4. Composition-root wiring: build the checker from the `library.db` read connection, inject into the AppContext (single handle), so Follow D2 / Ratio consume `ownership.owns(...)`.
5. Non-vacuous tests (golden: owned movie/episode → True; not-owned → False; soft-deleted file → not owned; provider-id matching tvdb→tmdb→imdb).

**Non-goals**

- ❌ Consuming the predicate (Follow D2 enqueue-skip, Ratio skip) — those are **D2/Ratio**. RP6 ships it wired-but-unconsumed (like RP4 events).
- ❌ Putting the predicate in the movie service (`scraper/movie_service.py` is already over budget — ROADMAP + tech-debt note). It lives in the **indexer query layer**.
- ❌ Quality-aware ownership ("I own it but at lower quality, so upgrade") — D1 scope is boolean "present"; a quality-aware variant is a later enhancement (Renouvellement / Follow D4).
- ❌ Write access — strictly SELECT-only across the boundary.

## 3. "Owned" definition (Decision A)

`owned == there exists a non-soft-deleted `media_file`linked (via`media_release`) to the matching
work` — i.e. a real file on disk, not merely a catalog row:

- **Movie**: `media_item(kind='movie')` matching the MediaRef (tvdb primary, then tmdb, then imdb) →
  `media_release(item_id=…)` → `media_file(deleted_at IS NULL)`. Owned ⇔ ≥1 live file.
  > **Schema note (corrected at impl time)**: migration `005_external_ids_json.sql` dropped the flat
  > `media_item.tvdb_id/tmdb_id/imdb_id` columns and consolidated provider IDs into
  > `media_item.external_ids_json`. The predicate matches via
  > `json_extract(external_ids_json, '$.tvdb.series_id')` (numeric tvdb/tmdb `CAST … AS INTEGER`, raw for
  > `tt…` imdb), covered by the `idx_external_ids_*` expression indexes — mirroring `indexer/query.py`.
- **Episode**: `media_item(kind='show')` matching the MediaRef → `season(number=season)` →
  `episode(number=episode)` → `media_release(episode_id=…)` → `media_file(deleted_at IS NULL)`. Owned ⇔ ≥1 live file.
- A show row with no episode files (catalog-only / metadata stub) is **not** owned at the episode level.
- `media_file.deleted_at IS NULL` is the liveness filter (soft-delete tombstones don't count as owned).

## 4. The port (`core/ownership.py`)

```python
@runtime_checkable
class OwnershipChecker(Protocol):
    def owns(self, media_ref: MediaRef, *, kind: Literal["movie", "episode"],
             season: int | None = None, episode: int | None = None) -> bool: ...
```

- `NullOwnershipChecker.owns(...) -> False` (fail-open default — "not owned" when no library is wired, so Follow never skips a wanted item it can't verify).
- Neutral: `MediaRef` + primitives only; no indexer types leak through the port.

## 5. Indexer predicate + adapter

- **Predicate** (`indexer/ownership.py`, SELECT-only): `is_owned(conn, *, kind, tvdb_id, tmdb_id, imdb_id, season, episode) -> bool` — the SQL of §3, matching on the first available provider id (tvdb→tmdb→imdb), `EXISTS (… media_file WHERE deleted_at IS NULL)`.
- **Adapter** (`indexer/ownership.py::IndexerOwnershipChecker`): holds a read connection; `owns(media_ref, kind, season, episode)` → `is_owned(self._conn, …)`. Read-only; fail-soft (a DB error → log + return False, never raises into the grab loop).
- Layering: `indexer/ownership.py` imports `core.ownership` (port) + `core.identity` — downward, allowed.

## 6. Composition-root wiring

Build the checker once from the `library.db` read connection at the composition root (where the indexer
DB path + the acquire context are both in scope), and expose it on the AppContext (a single handle /
one field, anti-service-locator). When no library.db is configured/available → `NullOwnershipChecker`.
Follow D2 / Ratio later read `ctx.ownership.owns(...)`. The adapter never grants write access.

## 7. Verification (non-vacuous)

Golden (real `library.db` fixture with seeded rows): (1) a movie with a live `media_file` matching a
tvdb_id → `owns(ref, kind=movie) is True`; (2) same movie but the only file is `deleted_at`-tombstoned →
`False` (soft-delete excluded); (3) an episode S01E03 with a live file → `owns(ref, episode, 1, 3) is True`,
S01E04 (no file) → `False`; (4) provider-id fallback — a row with only tmdb_id matched by a tmdb-only ref;
(5) a catalog-only show (no episode files) → episode ownership `False`; (6) `NullOwnershipChecker.owns(...)
is False` always; (7) adapter fail-soft — a closed/broken connection → `False`, no raise. Each asserts the
real boolean + the SQL actually joins to a live file (mutation: drop the `deleted_at IS NULL` filter → the
soft-delete test flips, proving the filter is load-bearing).

## 8. Phase decomposition (4 phases)

1. **Core port** — `core/ownership.py`: `OwnershipChecker` Protocol + `NullOwnershipChecker` + tests.
2. **Indexer predicate** — `indexer/ownership.py` `is_owned` SELECT-only (movie + episode, provider-id match, live-file filter) + golden tests on a seeded library.db.
3. **Adapter + wiring** — `IndexerOwnershipChecker` (port impl, fail-soft) + composition-root wiring + AppContext handle + NullOwnershipChecker fallback + integration test.
4. **Docs + ACCEPTANCE + gate** — architecture.md (indexer query layer + the ownership port boundary), reference doc, ACCEPTANCE.md, make check + design-gaps.

## 9. ACCEPTANCE preview (executable)

- pytest: owned movie/episode → True; soft-deleted-only → False; not-owned → False; provider-id fallback.
- pytest: `NullOwnershipChecker` always False; adapter fail-soft on a broken connection.
- A check that `acquire/` does NOT import `indexer/` (the boundary holds) — the layering test stays green; ownership crosses only via the core port.
- `make check` green.

## 10. Deferred (not gaps)

- Consumption (Follow D2 enqueue-skip, Ratio grab-skip) → D2 / Ratio C1.
- Quality-aware ownership (own-but-upgrade) → Renouvellement / Follow D4.
- RP9 (calendar-set air-date poll) — the OTHER Follow D2 prerequisite, separate feature.
