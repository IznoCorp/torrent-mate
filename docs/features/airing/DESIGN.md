# DESIGN — RP9: air-date set-poll (which followed episodes have aired)

| Field                        | Value                                                                                                                                                                                                                                                                                       |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Codename (proposed)**      | `airing`                                                                                                                                                                                                                                                                                    |
| **Roadmap item**             | RP9 (P2, prérequis) — "capacité de poll des dates de diffusion sur un ensemble"                                                                                                                                                                                                             |
| **Type**                     | minor                                                                                                                                                                                                                                                                                       |
| **Version bump**             | 0.30.0 → 0.31.0                                                                                                                                                                                                                                                                             |
| **Date**                     | 2026-06-15                                                                                                                                                                                                                                                                                  |
| **Depends on (all shipped)** | metadata `provider_registry` (`chain(EpisodeFetcher)` / `chain(TvDetailsProvider)`), `EpisodeInfo.air_date` + `MediaDetails.seasons` (per-(series,season) episode capability), `acquire/domain.FollowedSeries` + `core.identity.MediaRef`, the `title_resolver` stateless-service precedent |
| **Unblocks**                 | Follow D2 (calendar-first detection → wanted enqueue)                                                                                                                                                                                                                                       |
| **Scope decisions**          | A (stateless `acquire/airing.py`, no AcquireContext handle), B (full per-season enumeration over the existing `get_episodes` — no metadata-model change), C (poll non-special seasons, exclude season 0), D (capability-only — no wanted/ownership/cadence)                                 |

> Follow D2's calendar-trigger needs to know **which episodes of the followed series have aired** (air-date
> passed). Today air-dates are only reachable series-by-series. RP9 adds the **set-poll**: given a set of
> followed series, enumerate their episodes via the existing metadata capability and surface the **aired**
> ones. Like RP6/RP4, RP9 ships the capability **wired but not consumed** — Follow D2 turns the aired set
> into `wanted` entries (skipping owned ones via RP6, with cadence backoff). RP9 is **only the calendar half**.

---

## 1. The boundary (Decision D — capability-only, the load-bearing rule)

RP9 surfaces facts; D2 applies policy. The ROADMAP D2 = "calendrier-d'abord (RP9) + file wanted + cadence
backoff + ownership (RP6)" — RP9 is the **calendrier-d'abord** half ONLY. RP9 (verified against the
title_resolver/orchestrator precedents):

- **Returns a value object** (`list[AiredEpisode]`), performs **zero `store.wanted.*` writes** (D2's job).
- Does **NOT** call `ownership.owns(...)` — surfacing an _owned_ aired episode is correct RP9 behavior; filtering it is D2's concern (RP6's `owns` has zero call sites today; D2 is its first consumer).
- Does **NOT** read `FollowedSeries.cadence_json` — cadence governs how often the wanted _search_ repeats (D2 + the AcquisitionService loop), not the air-date poll. `cadence_json` stays a pure passthrough.
- Three **NEGATIVE tests** encode this boundary so a future refactor can't fold D2 logic into RP9.

## 2. Home + statelessness (Decision A)

`personalscraper/acquire/airing.py` — a **stateless** service (mirrors `acquire/title_resolver.py`). It takes
the metadata `ProviderRegistry` as a direct argument (already an `AppContext` field) and the series set as a
parameter. **No `AcquireContext` handle / field / close()** — RP9 owns no resource and crosses no forbidden
boundary (unlike RP6, whose impl crossed into `indexer` and thus needed a port+field). `acquire/` may import
`api/metadata` (downward) + `core` + `acquire.domain`; `api/metadata` could not import `acquire` (it would
lose the `FollowedSeries` binding) — so the home is `acquire/`, not `api/`.

## 3. Signature + output VO

```python
@dataclass(frozen=True)
class AiredEpisode:            # acquire/domain.py
    media_ref: MediaRef        # the followed series' ref (tvdb primary)
    season: int
    episode: int
    air_date: date             # the parsed air-date (always a real date — only aired episodes are emitted)
    title: str = ""            # episode title (for display/logging)

def poll_aired(
    series: Sequence[FollowedSeries],
    registry: ProviderRegistry,
    *, today: date,            # injected "now" (date-only) for determinism/testability
) -> list[AiredEpisode]: ...
```

- `series` is **passed in** (D2 reads `store.follow.list_active()` and passes it — RP9 does **not** read the store).
- `today` injected (no hidden `date.today()`) so tests pin the boundary deterministically.

## 4. The poll (Decision B — full per-season enumeration; Decision C — non-special seasons)

Per followed series (keyed on `media_ref.tvdb_id`, the primary; skip a series with no tvdb_id):

1. `registry.chain(TvDetailsProvider)` → `get_tv(tvdb_id)` → `MediaDetails.seasons` (the season list).
2. For each `SeasonInfo` with `season_number >= 1` (**exclude season 0 / specials**, Decision C): `registry.chain(EpisodeFetcher)` → `get_episodes(tvdb_id, season_number)` → `list[EpisodeInfo]`.
3. Flatten → keep the **aired** ones (§5) → map to `AiredEpisode(media_ref, season, episode, parsed air_date, title)`.

**Decision B**: full per-season enumeration over the **existing** `get_episodes` — **no metadata-model change**.
The cheaper alternatives (series-level `next/last_episode_to_air` (TMDB) / `nextAired` (TVDB), or a batched
`append_to_response=season/N` path) are **not parsed today** and would require net-new parser/model work; they
are deferred as a future optimization. Cost is bounded by the (small) followed-set and protected by the shared
rate-limiter (TVDB 20 rps / TMDB 40 rps) + circuit (`chain()` skips OPEN providers). **§10 notes the cost
tradeoff** (all-seasons re-polls old seasons each tick; D2's ownership/cadence throttle downstream).

**Provider order**: `chain()` returns TVDB-primary then TMDB-fallback (config order) — RP9 iterates the chain
with a fall-through (a primary that errors/returns empty → try the next eligible provider), mirroring
`scraper/tv_service_episodes.py::fetch_season_with_fallback`.

## 5. The aired predicate (Decision D-date) — net-new, defensive

`EpisodeInfo.air_date` is a plain **`str`** (default `""`, date-only `"YYYY-MM-DD"`, `""` = unknown/TBA; NOT
date/None). No helper parses it today. RP9 owns:

```
aired ⇔ air_date != "" AND parse_date(air_date) is not None AND parsed <= today
```

- `""` / malformed / unparseable → **not aired** (skip, never raise — a TBA/unscheduled episode is not aired).
- Date-only, `<= today` **inclusive** (an episode whose air-date is today counts as aired — the day-boundary
  ambiguity is acceptable for the calendar-trigger; documented).
- Parse defensively (`datetime.strptime(air_date, "%Y-%m-%d").date()` in a try/except → None on failure).

## 6. Fail-soft (per series + per season)

One bad series/season must not poison the whole poll: wrap each series' poll (and each `get_episodes`) so an
`ApiError` / `CircuitOpenError` / unexpected `Exception` → log (`acquire.airing.poll_failed`, series ref) +
**continue** to the next series; the others are still polled. `chain()` returning `[]` (no eligible provider) →
that series yields nothing, no crash. Mirrors `title_resolver`'s fail-soft (catch ApiError/CircuitOpenError +
bare Exception, log, continue).

## 7. Layering

`acquire/airing.py` imports `api.metadata` (registry + protocols + EpisodeInfo/MediaDetails), `acquire.domain`
(FollowedSeries + the new AiredEpisode), `core.identity` (MediaRef), stdlib `datetime` — downward only. No
store/indexer import. The acquire/ layering guard stays green.

## 8. Verification (non-vacuous — mocked `provider_registry` with KNOWN air-dates)

**Golden (assert WHICH episodes, not len>0)**: past air-date → surfaced; future → absent; `air_date == today`
→ surfaced (the `<= today` boundary, pinned); `air_date == ""` / malformed → absent, no crash. **Set-poll**:
2-3 series each with a mix → the aggregate contains exactly the aired episodes from ALL series, each carrying
its series' `media_ref` (so D2 can build `WantedItem.followed_id`). **Fail-soft (load-bearing)**: one series'
`get_episodes` raises ApiError / CircuitOpenError / Exception → the OTHER series still polled, no propagation.
**Empty chain**: `chain()` → `[]` → empty, no crash. **Season selection (anti-hidden-bug)**: assert
`get_episodes.call_args_list` covers the non-special seasons and **excludes season 0** (a poller that silently
polls only season 1 would pass a naive test). **NEGATIVE boundary (load-bearing)**: assert `poll_aired` makes
**no `store.wanted.*` call**, **no `ownership.owns` call**, and **does not read `cadence_json`** (inject spies;
assert call_count == 0) — encodes the RP9↔D2 boundary as executable tests.

## 9. Phase decomposition (4 phases)

1. **AiredEpisode VO + aired predicate** — `acquire/domain.py` `AiredEpisode` (frozen) + the `air_date` str→date parse + `<= today` predicate (a small helper in airing.py) + unit tests (past/future/today/empty/malformed).
2. **The set-poll service** — `acquire/airing.py` `poll_aired` (per-series get_tv→seasons→get_episodes fan-out, non-special seasons, chain fallback, fail-soft) + golden + set-poll + fail-soft + season-selection tests.
3. **Negative-boundary tests + wiring touchpoint** — the NEGATIVE tests (no wanted/ownership/cadence) + confirm RP9 is reachable (a free function callable by a future D2; no AcquireContext change needed) + layering test.
4. **Docs + ACCEPTANCE + gate** — architecture.md (acquire/ airing service + the RP9↔D2 boundary), reference doc, ACCEPTANCE.md, make check + design-gaps.

## 10. Deferred / notes (not gaps)

- Consumption (Follow D2: aired → wanted, ownership-skip, cadence) → Follow D2.
- **Cost optimization**: full all-season enumeration re-polls old seasons each tick; a series-level
  `next/last_episode_to_air` (TMDB) / `nextAired` (TVDB) shortcut — or a batched `append_to_response=season/N`
  path — would cut it to ~1 call/series, but both need net-new parser/model work → deferred. D2's cadence +
  ownership throttle the downstream cost meanwhile.
- Series **status** (continuing/ended) is not on `MediaDetails` → RP9 can't skip ended series cheaply (re-polls
  them); adding `status` parsing is a future optimization.
- Specials (season 0) excluded from the aired set (Decision C) — a follow rarely wants specials auto-grabbed.
