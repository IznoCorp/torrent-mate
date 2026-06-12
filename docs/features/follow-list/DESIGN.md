# DESIGN — Follow D1: followed-series list (store CRUD + `follow` CLI)

| Field                        | Value                                                                                                                                                                       |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Codename (proposed)**      | `follow-list`                                                                                                                                                               |
| **Roadmap item**             | Follow D1 (P2) — "store + CRUD de la liste suivie"                                                                                                                          |
| **Type**                     | minor                                                                                                                                                                       |
| **Version bump**             | 0.28.0 → 0.29.0                                                                                                                                                             |
| **Date**                     | 2026-06-12                                                                                                                                                                  |
| **Depends on (all shipped)** | RP3 acquire.db `followed_series` table + `_FollowSubStore.add/get`, RP5c acquire/ lobe + AppContext, metadata `provider_registry` (on AppContext), `core.identity.MediaRef` |
| **Unblocks**                 | Follow D2 (calendar detection → wanted enqueue consumes the followed list)                                                                                                  |
| **Scope decisions**          | A (id-based add + metadata title resolution), B (soft unfollow via `active`), C (idempotent dedup/reactivate)                                                               |

> grab-core (RP5b) consumes the `wanted` queue but **nothing populates it** yet. Follow D1 is the first
> producer-side step: it lets the operator **manage the list of series to auto-acquire**. D1 does NOT yet
> enqueue wanted items (that is D2's calendar-first detection) — it builds the followed-list CRUD + CLI
> that D2 will iterate. A followed series is event-emitting (RP4 `SeriesFollowed`/`SeriesUnfollowed`).

---

## 1. Goals / Non-goals

**Goals**

1. Complete the `_FollowSubStore` CRUD: `FollowedSeries.id`, `find_by_ref`, `list_active`/`list_all`, `set_active` (soft unfollow/refollow) + the `FollowSubStore` Protocol.
2. A `follow` CLI command group: `follow add`, `follow list`, `follow remove`.
3. Series identity by provider id (`--tvdb` primary), with the **canonical title resolved via the metadata `provider_registry`** (fail-soft fallback to a user-supplied `--title`).
4. Idempotent add (dedup on `media_ref`: reactivate if inactive, no-op if active — never a duplicate row).
5. Emit `SeriesFollowed` / `SeriesUnfollowed` (RP4 events, already shipped) on the bus.

**Non-goals**

- ❌ Enqueuing `wanted` items / detecting new episodes — that is **Follow D2** (calendar-first + cadence). Following a series does NOT auto-grab yet.
- ❌ Per-series quality profiles — `quality_profile_json` stays null (permissive grab); **Follow D4** owns per-series profiles.
- ❌ Cadence / backoff (`cadence_json`) — D2/RP9.
- ❌ Title-search add (`follow add "Breaking Bad"` → interactive pick) — D1 is id-based + deterministic; search-add is a later enhancement.
- ❌ Hard delete by default — unfollow is soft (`active=0`) to preserve history + any `wanted`/obligation rows referencing `followed_id`.

## 2. Store CRUD completion (`acquire/store.py` `_FollowSubStore` + `_ports.py`)

- **`FollowedSeries.id: int | None = None`** (mirror the `WantedItem.id` pattern from grab-core); `_row_to_followed` + every SELECT carries `id`. Pre-1.0 in-place VO evolution, no migration.
- **`find_by_ref(media_ref: MediaRef) -> FollowedSeries | None`** — dedup + addressing by series identity (keys on the canonical `media_ref_json`, reusing the store's existing `_media_ref_to_json`).
- **`list_active() -> list[FollowedSeries]`** (`WHERE active=1 ORDER BY id`) + **`list_all() -> list[FollowedSeries]`** (for `--all`).
- **`set_active(followed_id: int, active: bool) -> None`** in one `_write_tx` — soft unfollow (`active=0`) / refollow (`active=1`).
- **`FollowSubStore` Protocol** in `_ports.py` (add/get/find_by_ref/list_active/list_all/set_active) — the typed seam D2 will depend on.
- Module-size: `store.py` is ~756 LOC (under 800) — keep the new methods lean.

## 3. Title resolution (`acquire/` helper using `provider_registry`)

`follow add --tvdb <id>` resolves the canonical title via the metadata `provider_registry` (on the AppContext) so the stored `title` is human-readable. **Fail-soft**: if resolution errors (network/auth/not-found), fall back to `--title` if given, else a placeholder like `"tvdb:<id>"` — a metadata hiccup must NEVER block a follow. The lookup is a single provider call; keep it bounded (the registry already has circuit/timeout policy).

## 4. CLI `follow` command group (`commands/follow.py`)

Mirror `grab.py` (`@command_with_telemetry`, `@handle_cli_errors`, `per_step_boundary`). A Typer sub-group `follow` with:

- **`follow add --tvdb <id> [--tmdb <id>] [--imdb <id>] [--title <t>]`** — build `MediaRef` (≥1 id, tvdb primary), resolve title (§3), `find_by_ref`: if exists+inactive → `set_active(id, True)` (refollow) + emit `SeriesFollowed`; if exists+active → no-op message; else `add` + emit `SeriesFollowed`. Idempotent.
- **`follow list [--all]`** — rich table (id, title, tvdb/tmdb/imdb, active) of `list_active()` (or `list_all()`). Read-only (no torrent client needed).
- **`follow remove --tvdb <id>`** (or `--id <followed_id>`) — `find_by_ref` → `set_active(id, False)` (soft unfollow) + emit `SeriesUnfollowed`. Clear message if not followed.
- Events emitted on `app_context.event_bus` (the muted RP4 subscriber consumes them). Build with `build_torrent_client=False` (follow management needs no torrent client).

## 5. Layering + verification

- `commands/follow.py` is a CLI command (consumer layer); the store + helper live in `acquire/` (imports core/conf/api/events only — layering green).
- **Verification (non-vacuous)**: store unit tests (find_by_ref round-trips id + dedup; list_active excludes inactive; set_active flips; FollowedSeries.id round-trips rowid). CLI e2e (real seeded acquire.db): `follow add` twice → ONE row (idempotent); `follow add` after `remove` → reactivates (not a 2nd row); `follow list` shows it; `follow remove` → inactive + `list` (no --all) hides it; metadata-resolution failure → follow still succeeds with the fallback title (fail-soft). Event assertions: `SeriesFollowed`/`SeriesUnfollowed` emitted once each.

## 6. Phase decomposition (4 phases)

1. **Store CRUD** — `FollowedSeries.id` + `find_by_ref` + `list_active`/`list_all` + `set_active` + `FollowSubStore` Protocol + store tests.
2. **Title resolution helper** — `provider_registry` → canonical title, fail-soft + tests.
3. **`follow` CLI** — add/list/remove command group + dedup/reactivate + `SeriesFollowed`/`SeriesUnfollowed` emission + e2e tests.
4. **Docs + ACCEPTANCE + gate** — architecture.md (acquire/ + follow CLI), reference doc, ACCEPTANCE.md, make check + design-gaps.

## 7. ACCEPTANCE preview (executable)

- `personalscraper follow add --tvdb 81189` → adds "Breaking Bad"; repeating → still one row (a pytest selector / CLI e2e).
- `personalscraper follow list` shows the active series; `follow remove --tvdb 81189` → `list` hides it, `list --all` shows it inactive.
- A pytest selector proving metadata-resolution failure still follows (fallback title) + the dedup/reactivate path.
- `make check` green.

## 8. Deferred (not gaps)

- Wanted enqueue / new-episode detection → Follow D2 (calendar-first RP9 + cadence + ownership RP6).
- Per-series quality profiles (`quality_profile_json`) → Follow D4.
- Title-search add (interactive) → later enhancement.
