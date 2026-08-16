# Changelog

All notable changes to TorrentMate (engine package `personalscraper`) are
documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **⚠️ Partial coverage — read this first.**
>
> This file was maintained through `0.19.0` (2026-06-01), then sporadically for
> `0.55.0`–`0.65.2` (July 2026). Versions `0.20`–`0.54`, and `0.66` and later,
> are **not** logged here, and will not be back-filled from memory —
> **a false changelog is worse than an absent one** (constitution §méthode).
> The authoritative history for those versions lives in:
>
> - the **git log** (`git log --oneline`), and
> - the **squash-merged pull requests** on GitHub, each carrying its dated
>   proof run (constitution §10).
>
> Every PR bumps the version (§10-3, enforced by the CI `version-bump` job),
> so `git tag` / `personalscraper.__version__` + the PR that bumped it is the
> per-version record. Systematic changelog keeping **resumes at `1.0.0`** (the
> first production release), when the SemVer contract and a maintained
> changelog both begin.
>
> The entries below are kept for their historical record.

## [0.65.2] — 2026-07-31

### Fixed

- **Plex scan after dispatch finally triggered on the crons (#346, recurring bug).**
  The pipeline/dispatch crons run from the deploy checkout, whose `.env` was missing
  `PLEX_TOKEN` → the Plex refresh subscriber was never wired
  (`plex_refresh_disabled reason=no_token`) → media acquired + dispatched + indexed but
  invisible in Plex (Supergirl, Rooster…). `Settings` now loads a `.env` overlay: the
  canonical `.env` (next to the `config/` shared via `PERSONALSCRAPER_CONFIG`) fills in
  the keys missing from the local `.env`, without overwriting local secrets. Fully
  backward compatible.

### Changed

- **Product constitution v3** (`docs/reference/product-intent.md`): §4 "the chain runs
  through to Plex visibility" (acquisition→pipeline→dispatch→Plex scan) + §5 "identity
  preserved at scraping" (media recovered via acquisition keeps the follow's ID).

## [0.65.1] — 2026-07-31

### Fixed

- **Acquisitions — status polish (#344).**
  - #23: in « Suivis retirés », the « Réactiver » button no longer wraps to the
    next line on a long title (mobile) — the row no longer wraps, the title
    truncates, the button stays in place.
  - #24: « En attente » and « Non vérifié » no longer share the same color —
    `non_verifie` (tone `muted`) moves from a dashed grey to a faint dashed
    info-blue, distinct from the solid grey of « En attente », in both the follow
    card AND the episode matrix.

## [0.65.0] — 2026-07-29

### Added

- **Auto-switch of a stalled release + seeders strengthened in the score (#342).**
  A grabbed torrent that does not start (unreachable swarm, broken payload, stuck
  beyond a delay) is automatically replaced by ANOTHER release:
  - seeders strengthened in the score (weight 1 → 2, refined thresholds) to favor
    well-seeded releases (config only, no code change);
  - swarm observability (`TorrentItem.swarm_seeds` from qBit `num_complete`)
    - `classify_stall` (HEALTHY / STALLED_RECOVERABLE / STALLED_DEAD);
  - memory of the hashes already tried (`wanted.tried_hashes_json`, migration 009) +
    exclusion at ranking time (`rank(..., exclude_hashes=…)`) — never the same
    dead release twice;
  - `reswitch_stalled` actor (in the `grab` CLI): deletes the dead torrent,
    requeues the item, emits `GrabReswitched`; toast + live refresh on the UI side.
  - Honest guardrail: all sources tried → `en_attente` (never a fake
    « en cours »).

## [0.64.0] — 2026-07-29

### Changed

- **More readable, full-width Acquisitions UI (4 operator requests).**
  - #12 — each tab's content is no longer boxed inside a `Card`: it takes the
    full width (especially at 390 px), with no double box+section margin.
  - #21 — the title search and the add-by-ID form merge into a single surface
    (`MediaSearchAdd`); the « Ajouter par ID » accordion of `FollowedPanel` is
    removed, and the « Recherchez un média / Tapez un titre… » empty-state no
    longer shows at rest (no more wasted space).
  - #19 — after a successful « Suivre », the search is reset.
  - #20 — the follows list splits into « Séries » / « Films » sub-tabs
    (client-side filter on `item.kind`, active + removed section).

## [0.63.0] — 2026-07-29

### Fixed

- **A followed series is no longer split under two TVDB identities at scrape time.**
  The scraper freely re-matched every staging folder; for a followed series with
  TVDB duplicates (e.g. « Rooster » 457770 vs « ニワトリ・ファイター »
  452575), it could resolve the wrong record, dispatch a 2nd folder and
  **break the acquisition reconcile** (episodes stayed « en cours
  d'acquisition » forever). Now, when a show folder originates from a follow's
  `wanted` queue (grabbed episodes matched by season/episode + a title-similarity
  guard), the scrape **forces the follow's TVDB ID**
  (`scrape_tvshow_forced`) instead of re-matching. Precision-first: forcing
  happens only when a single follow covers the folder AND the title agrees,
  otherwise free match (backward compatible). Fail-soft end to end (never blocks
  the scrape). TVDB remains the detection primary.

## [0.62.0] — 2026-07-29

### Added

- **Follow a media item by IMDB or TMDB ID, no longer TVDB only.** The
  « Ajouter par ID » form (« Suivis » tab) now offers a TVDB / TMDB / IMDB
  provider selector: an integer for TVDB/TMDB, a `tt…` identifier for IMDB
  (validated client-side). Since episode detection (`poll_known`) needs a
  TVDB ID, the server **resolves the TVDB** of a series followed via TMDB/IMDB
  at follow time — `TMDBClient.get_tvdb_id` reads the raw TVDB ID from
  `/tv/{id}/external_ids`, and `find_by_imdb` bridges IMDB → TMDB → TVDB. TVDB
  remains the detection primary; TMDB/IMDB serve only to resolve it
  (multi-provider separation). If a series' TVDB cannot be resolved, the
  follow is **created but flagged** (`tvdb_unresolved`, warning toast) —
  never a silently inert follow (§méthode). Movies (title cycle §5) do not
  need TVDB and are followed as-is.

## [0.61.0] — 2026-07-28

### Added

- **Games (disc images) are detected and hidden from the library.** A game
  release — a disc image (`.iso`/`.bin`/`.mds`/…) carrying a game signal
  (a known repack group like Mephisto/FitGirl/DODI, a `vX.Y.Z` version token,
  or a console platform) — was classified `OTHER` by the sorter (`.iso` is neither
  video nor app) and surfaced as an item to sort in the Medias UI, even though it
  is not a media item. `is_game_release` (`personalscraper/sorter/game.py`) detects it,
  and the staging read-model (`scan_staging_media`) no longer surfaces it, logging
  `staging_game_hidden` (never a silent disappearance). **Precision-first**:
  a MOVIE/series disc image (which always carries a video-release token like
  `1080p`/`BluRay`) is never mistaken for a game, a video child or a TV marker
  vetoes the detection, and a PlayStation token (`PS5` contains `S5`) is no longer
  read as a TV season — so no real media disappears from sorting. The existing
  `Marvels.Spider-Man.2` item is hidden with no move and no migration.

## [0.60.0] — 2026-07-28

### Added

- **« Annoncé » episodes — known future releases are visible.** The airing
  cache now keeps **all** episodes with a known date (future ones included),
  not just the aired ones. A new `annonce` episode state is derived when
  `air_date > today`: the chip appears in the « Détail par épisode » matrix of
  `/acquisition` before the episode even airs. Invariant preserved: a future
  episode goes to the cache but **never** to the `wanted` queue (we do not search
  for an episode not yet released), and `annonce` does not degrade the card's
  `FollowStatus` — a series whose aired episodes are all owned stays « À jour »
  even with announced episodes ahead. A single provider call per series
  (no double-poll).
- **Color legend for the episode chips.** Below the matrix, a legend derived
  **directly** from `meta.ts` (single source) maps a distinct color to each
  of the 6 states — « En médiathèque » (green), « À récupérer » (amber),
  « En cours d'acquisition » (blue), « En attente » (solid grey),
  « Non vérifié » (dotted grey), « Annoncé » (purple). A test verifies that
  the legend lists exactly the keys of `EPISODE_STATE_LABEL` (drift = failure).
  `--upcoming` token added (purple), `muted` badge variant (dotted) — readable
  in light **and** dark themes.
- **Air date on chip click.** A portaled popover (not clipped by the
  mobile-shell guard) shows « Diffusé le {date} » for a past episode,
  « Sortie prévue le {date} » for an announced one, in long French format
  (« 3 août 2026 »), never the raw ISO token. Keyboard accessible.
- **Version + commit in the mobile side menu.** The `VersionCard` (already
  single-source, until now `hidden md:flex` in the sidebar) is added to the
  mobile menu's `SheetContent` — the version number and build SHA are now
  visible on mobile, no longer desktop-only.

## [0.59.1] — 2026-07-28

### Fixed

- **The mobile web UI no longer scrolls horizontally.** At 390 px the `/`
  (Contrôle) route scrolled 13 px sideways, which made the `position: fixed`
  bottom tab bar drift with the page; four other routes had children reaching up
  to 444 px, clipped only by an ancestor `overflow-hidden` (latent bombs). Two
  layers of fix:
  - **Structural clamp (the net).** `AppShell` root `<div>` gains
    `overflow-x-clip` and `<main>` gains `min-w-0 overflow-x-clip`, so no child
    can ever widen the layout viewport and no page-level horizontal scroll is
    possible — whatever a future page does. `BottomTabBar` tabs gain `min-w-0`
    so a label truncates instead of widening the fixed bar. `clip`, not
    `hidden`, so the shell never becomes an accidental scroll container. Guarded
    by a class-contract test (JSDOM does not lay out, so a `scrollWidth`
    assertion would be vacuous; the real 390 px Chrome proof is out-of-band).
  - **The two culprits, fixed at source** (so the content is right, not merely
    clipped): the `/` "À traiter" row now lays title + reason in a
    `flex-wrap min-w-0` row where the title truncates and the reason **wraps**
    (it is the actionable "why", never hidden); the `/acquisition` search row
    now lets the input shrink (`min-w-0`) and wraps (`flex-wrap`) so the
    « Chercher » button drops below the kind filter on a narrow viewport instead
    of overflowing to 430 px. Desktop (≥ sm/md) layout is unchanged.

## [0.59.0] — 2026-07-28

### Added

- **Plex library refresh after every dispatch**. The storage disks are
  macFUSE/NTFS mounts that deliver no filesystem events to Plex, so dispatched
  media stayed **invisible** until someone scanned by hand (proven by the Margin
  Call incident, 2026-07-28: acquisition → dispatch → indexation all green, film
  on disk with NFO and artwork, absent from Plex).
  - `api/plex.py` — `PlexClient`: sections fetched once per process, and a
    PARTIAL scan `GET /library/sections/{id}/refresh?path=<folder>` of the one
    folder just written. The section is resolved by **longest `Location` prefix**
    on a path boundary, never a hardcoded id — the four disks each carry several
    libraries with nested roots, where a first-match resolver scans the wrong
    one.
  - `subscribers/plex.py` — `PlexSubscriber`, modelled on `TelegramSubscriber`:
    reacts to `ItemDispatched`, refreshes off-thread, **fail-soft absolute**
    (Plex down, 401, unknown path, client bug ⇒ a warning, and the dispatch
    stays a success).
  - `PLEX_URL` (default `http://localhost:32400`) + `PLEX_TOKEN` in `Settings`
    and `.env.example`. **No token ⇒ nothing wired and zero requests.** The token
    travels in the `X-Plex-Token` header, never a URL, and appears in no log,
    repr, exception **or rendered console line** — see below, the record-level
    guarantee alone was not enough.
  - Wired through `build_plex_subscriber`, the single owner of the gate, from
    **both** dispatch composition roots (`run` and the standalone
    `personalscraper dispatch`): the step-by-step path emits `ItemDispatched`
    like the full run, so wiring only `run` left it dispatching media that never
    reached Plex.
  - `docs/reference/plex-api.md` — auth, endpoints, section mapping, the cache
    lifetime and the no-circuit-breaker trade-off.

### Security

- **The Plex token could be printed in clear on stderr.** `PlexSubscriber`
  logged its fail-soft warning with `exc_info=True`, and the console renderer
  (`structlog.dev.ConsoleRenderer`) expands a traceback **with frame locals** —
  every frame between the client and the socket holds the `X-Plex-Token` header.
  Any exception that was not a `requests.RequestException` (e.g.
  `UnicodeEncodeError`, raised when an undecodable macFUSE/NTFS filename reaches
  the URL) therefore printed the credential to the operator's terminal, PM2 log
  capture and cron mail. The JSON log file was never affected (`format_exc_info`
  renders no locals). Three changes close it: no `exc_info` on this path (only
  `error=type(exc).__name__`), `PlexClient.refresh` catches `Exception` so no
  token-bearing stack escapes, and `allow_redirects=False` so a 302 cannot hand
  the header to another origin (`requests` strips only `Authorization`). Pinned
  by tests asserting on the **rendered** output of the production formatter —
  the pre-existing `caplog.records` assertions could not see a renderer leak.
- **`ItemDispatched.target_path`** (additive, defaults to `None`): the exact
  destination FOLDER of a transfer, filled by the dispatcher for the three
  actions (moved / merged / replaced). `target_disk` alone is a mount point — a
  consumer acting on the media itself could not reconstruct the folder without
  duplicating the naming rules.

## [0.58.0] — 2026-07-28

### Changed

- **Film cards follow the same row-selection rule as episodes** (D3 — VISIBLE
  CHANGE, three distinct deltas). `compute_movie_truth` now delegates to
  `select_wanted_facts`: only OPEN `wanted` rows speak, newest first. The
  affected set is _a film follow with **no open row** and at least one closed
  one_ (`done` / `abandoned`) — not only the single-row case. What an operator
  actually sees, per sub-case:

  1. **Pill.** A film whose last closed verdict concluded nothing takeable read
     **« En attente »** and now reads **« Non vérifié »** — a queue state for an
     item that is in no queue, carried by the stale verdict of a finished
     acquisition.
  2. **« Récupérer maintenant » button disappears.** A film whose last closed
     verdict was `available` with `found > 0` read **« À récupérer »**, which is
     the one state that renders the grab action (`canGrabNow`). The button is
     gone — and it was a **false affordance**: the grab pass walks OPEN rows
     only, so pressing it on a follow that has none was already a guaranteed
     no-op. This removes a promise the backend never kept, not a capability.
  3. **Reason line disappears.** A film whose last closed verdict was
     inconclusive already read « Non vérifié »; the pill is unchanged, but the
     explanatory line under it (`followWaitingReason`, fed by
     `movie_facts.last_search_outcome`) is now empty — there is no open row to
     explain.

  **API payload**: `FollowedSeriesItem.movie_facts` is now `null` for every
  affected follow (it previously carried the closed row's
  `status` / `last_search_outcome` / `last_search_found`). Any consumer reading
  those fields sees the change even where the pill did not move.

  This settles an item the PR #320 review left « à arbitrer »: the film card
  kept a most-recent-row-of-any-status fallback the episode matrix never had,
  justified by « a film has no episode matrix to contradict it ». The
  arbitration is **one rule everywhere** — a closed row is history, not state.
  Ownership is untouched: a film on disk whose row was closed still reads
  « À jour », because the library fact is read separately from the queue facts.
  Open-row cases are byte-identical.

- **A broken tracker key can finally be concluded — after being confirmed
  twice** (m15 / D4). `SearchOutcome` carries `errors: {tracker: taxon}`
  (`auth` / `circuit` / `api`) alongside the historical `errored_names`, and a
  UNANIMOUS failure mode now names itself: all-`auth` ⇒ terminal
  `tracker_auth`, all-`circuit` ⇒ `circuit_open`, anything mixed ⇒
  `trackers_unavailable` (unchanged). Because that verdict is terminal and a
  passkey rotation briefly invalidates every key at once, it is **debounced**:
  the first all-auth search records the verdict but leaves the row queued, and
  only a second _consecutive_ one abandons. Any other verdict in between resets
  the streak.

### Fixed

- **A failed `add()` no longer strands its wanted row** (M9, release half). The
  intent hash reserved before `add()` was never given back when the add
  _failed_ rather than crashing, and the row it sat on became unreachable:
  `reclaim_stale_searching` refuses a hash-carrying row, the grab pass's hash
  guard short-circuits any re-claim, the search pass only walks `pending`, and
  the pre-claim gate returned `skipped` _before_ the cutoff check — so the row
  was not even aged out. The only actor left was the reconciliation, and only
  with a reachable torrent client: precisely what is missing when `add()` failed
  because the client was down. `clear_grab_intent` now releases the reservation
  on every non-success disposition, before the status write.

- **The crash-window hash is written before `add()`, not after** (M9). The
  chosen hash is reserved on the still-`searching` row so an interruption
  between `add()` and the status write leaves a _replayable intent_ instead of
  an orphan torrent: the reconciliation confirms it against the client
  (recording the seed obligation the grab-time writer never reached) or clears
  it if the torrent never landed. Recovery is a replay of the decision already
  taken, never a fresh search that could pick a different release.

- **A broken passkey during a SEARCH is now classified as one** (m15). It was
  raised in exactly one place — the grab stage's `.torrent` download — so a
  search-time auth failure surfaced as a generic `ApiError`, taxon `api`,
  retried forever; the `tracker_auth` verdict was unreachable for both
  configured trackers. `TorznabClient` classifies its own auth failures (Torznab
  error codes 100-102 and HTTP 401/403).

- **Provider I/O inside a web request is bounded and released** (M6 / m23).
  The request-scoped registry is built with `max_attempts=1` through a real
  construction seam, bounding a dead provider to its timeouts instead of a full
  backed-off retry loop (~60-75 s per lookup before), and
  `scoped_provider_clients` closes the registry — and its `requests.Session`
  pool — in a `finally` instead of leaving it to the garbage collector.

- **`GET /api/acquisition/followed` no longer scans `pipeline_run`** (m24):
  indexer migration `016_pipeline_run_open_command` adds
  `idx_pipeline_run_open_command ON pipeline_run (command) WHERE ended_at IS NULL`.
  Partial by design — only the handful of open runs are indexed, so it stays
  tiny on an append-only table nothing prunes, and rows leave it as soon as
  `ended_at` is stamped. Applied at web boot by the lifespan migration pass
  (additive, no data change).

- **Grab runs report their recovered acquisitions.** `confirmed_grabbed` — grabs
  recovered out of the crash window — is persisted on the run row and printed,
  alongside `closed_owned` and `requeued_missing`. It was computed, logged, then
  dropped.

### Internal

- **The acquisition service is split into its two passes** (D6). `service.py`
  keeps the run loops and the public surface; the per-item work moves to
  `_search_pass.py`, `_grab_pass.py` and the shared `_pass_gates.py`, mixed into
  the same class. Behaviour-preserving: the moved bodies are byte-identical
  moves, same logger, same event names. `service.py` drops from 945 to ~480
  non-blank LOC — one module-size warning fewer.

## [0.57.0] — 2026-07-28

### Added

- **Generic Torznab client** (`personalscraper/api/tracker/torznab.py`):
  `TorznabDescriptor` (frozen dataclass — provider, base URL, API path, `t=`
  endpoint names, category mapping, dialect quirks, transport tuning) +
  `TorznabClient` carrying the whole protocol (HTTP call, XML parse,
  `torznab:attr` flattening, caps flattening, error taxonomy). Extracted
  verbatim from the production-proven C411 client, whose behaviour stays pinned
  byte-identical by its untouched test suite. **Adding a Torznab tracker is now
  a descriptor plus a logic-free class.**
- **Tr4ker tracker** (`personalscraper/api/tracker/tr4ker.py`): the second named
  config — `https://tr4ker.net`, API path `/api/torznab`, activation gated on
  the single `TR4KER_PASSKEY` secret (sent as the Torznab `apikey=` parameter,
  per this host's one-variable-per-tracker convention). Enabled in `config/`
  with priority `["c411", "tr4ker"]`.
- **`docs/reference/tr4ker-api.md`**: distilled reference — auth, endpoints
  (`/api/torznab` search, `/api` alias, `/api/torznab/all` cross-seed documented
  but not wired, `/api/rss` passkey feeds), response mapping, RSS category
  slugs, operational rules, release-naming grammar, known errors. No secret.

### Changed

- **`TrackerResult.tmdb_id` has a producer again**: the generic client maps the
  Torznab `tmdbid` attr, which restores the TMDB identity hard-filter (the
  anti-remake guard) for c411 and tr4ker. Parsing is defensive — absent, empty
  or non-numeric degrades to `None` (filter no-op), never a wrong drop.
- **`config.example/tracker.json5`** ships a `tr4ker` entry (disabled) and the
  updated `PROVIDER_CREDS` comments.

### Removed

- **Torr9 tracker** (`torr9.py`, 578 L, plus its unit suite): torr9.net closed
  2026-07. `ProviderName.TORR9`, both activation entries, the factory class-map
  entry, the config providers, `docs/reference/torr9-api.md` and its four sample
  captures are gone; every test that named it was retargeted to tr4ker. **The
  historical rows it left in `acquire.db` are untouched** and a dedicated test
  pins that they stay readable and still veto a deletion (the seeding floors
  live on the row, and no read path coerces a tracker name into the enum).
- **`TrackerProviderConfig.enrich_seeders` / `enrich_seeders_top_k`**: consumed
  only by the removed client (it owned the sole per-torrent detail endpoint) and
  set by no config file.

## [0.55.0] — 2026-07-27

### Added

- **Five veridical acquisition states** (`personalscraper/web/acquisition/states.py`):
  one derivation, five episode states (`en_mediatheque`, `a_recuperer`,
  `en_acquisition`, `en_attente`, `non_verifie`) and seven follow states
  (adding `disabled`, `verification_en_cours`, `a_jour`). Every acquisition
  surface — followed cards, the completeness matrix, episode chips — reads
  its state from this single module.
- **Search/grab split** (`personalscraper/acquire/service.py`):
  `AcquisitionService.run_search` runs the search pass (search→filter→rank,
  persists verdict; never touches the torrent client);
  `AcquisitionService.run` runs the grab pass (takes `list_available()` only,
  re-searches each item, adds the torrent). The split is what makes « À
  récupérer » a visible state — before it, the operator could never see what
  was available but not yet taken.
- **`search` CLI command** (`personalscraper search`): runs the search pass
  over `list_pending()`, states availability without downloading.
- **Scheduled search + grab crons** (launchd): detect 03:00 → search 03:10 /
  15:10 → grab 03:20 / 15:20 — three timed passes scoped by status so new
  episodes are queued before the search pass lists them.
- **Follow priming on creation**: `POST /api/acquisition/followed` spawns a
  detached prime runner (`follow detect --series N` → `search --followed-id N`
  → `grab --followed-id N`) so a freshly followed series is detected +
  searched + grabbed immediately rather than waiting for the next cron tick.
- **Server-side metadata enrichment** on `POST /api/acquisition/followed`:
  when the client supplies no poster/overview/year, the server queries the
  provider (TVDB/TMDB) and backfills the card columns. Fail-soft — a provider
  outage never blocks the follow creation.
- **« Récupérer maintenant » per-follow trigger** (`POST
/api/acquisition/followed/{id}/grab`): spawns `grab --followed-id N` alone —
  no catalog poll, no search, just claim what a previous search already marked
  `available`.
- **Coherence-guard extension**: `scripts/check-acquisition-coherence.py` now
  checks all five states (`en_mediatheque` / `a_recuperer` /
  `en_acquisition` / `en_attente` / `non_verifie`) against the library × the
  wanted queue × the torrent client, exiting with the anomaly count.

### Changed

- **`grab` CLI now walks `list_available()` only** (post-split): the pending
  backlog is invisible to the grab pass — it takes only items a previous
  search already concluded takeable.
- **No more attempts cap**: `MAX_ATTEMPTS` retired. `attempts` counts
  cadence-paced searches; capping the grab pass on it would abandon a
  known-available item after one flaky add. The 30-day cutoff bounds infinite
  retries instead.
- **`not_found` grab disposition** (no candidates / all filtered / wrong
  episode): reverts honestly to `'pending'` with the new verdict recorded — the
  torrent vanished between the two passes, so the row stays queued rather than
  freezing on « À récupérer » or adding something else.
- **RETRYABLE at grab keeps status `'available'`** with the verdict untouched:
  the search pass's `available` conclusion still stands (the grab's own
  re-search did not conclude), so status and verdict stay in sync.
- **`panne ≠ absence`**: inconclusive search outcomes (`trackers_unavailable`,
  `circuit_open`, `search_api_error`, `no_seeders`) persist `found=NULL`, never
  `0`. The derivation reads them as `non_verifie` — reporting an outage as
  « rien de prenable » would claim knowledge we do not have.
- **Acquisition guardrail test**: `tests/unit/test_global_guard_cannot_spawn_real_acquisition_runners.py`
  — a `conftest` autouse fixture neutralizes every `_spawn_prime_runner` /
  `subprocess.Popen` call, so a test can never accidentally hit the production
  DBs or the trackers.

### Removed

- **`VERSION` file**: version is now exclusively in `pyproject.toml` +
  `personalscraper/__init__.py:__version__`. The CI `version-bump` job +
  `GET /api/version` boot-cached contract made the file redundant.

## [0.19.0] — 2026-06-01

### Changed

- **Library / Indexer consolidation (lib-fold)**: the standalone top-level
  `library/` package was deleted and its responsibilities folded into the
  indexer, `insights/`, `maintenance/`, and `verify/`.
  - `library-index --mode full` is now **self-sufficient**: it runs the item
    stage (rich `media_item` rows) as pass 1, then the file walk as pass 2, in a
    single invocation. No prior `library-scan` step is required.
  - `library-scan` is now a **visible alias** of `library-index --mode full`
    (kept in `--help` for backwards compatibility; no longer exposes `--mode`).
  - **Single `media_item` creator**: both dispatch write paths now share the
    `_item_stage` primitives — `rebuild()` (auto-rebuild) delegates to
    `scan_and_stage_dir` (full rich rows: seasons + issues), and `add()`
    (per-dispatch) builds via `build_item_row` — eliminating the prior
    `canonical_provider=None` degradation on the dispatch path.
  - **Kind-deterministic canonical SSOT**: `canonical_provider` is derived from
    kind + provider IDs via `_canonical.derive_canonical_provider` (show → tvdb
    when a tvdb_id exists, movie → tmdb when a tmdb_id exists).
  - **Season-dir regex widened**: `naming_patterns.SEASON_DIR_RE` now matches the
    FR + EN + `Specials` union; new `season_number_from_dir()` helper added.
  - NFO helpers (`parse_title_year`, `extract_nfo_ids`, `extract_nfo_metadata`)
    moved to `personalscraper.nfo_utils`.
  - `write_json` / `read_json` moved to `personalscraper.io_utils`.
  - The redundant inline **ffprobe re-scan was dropped** from `library-analyze`
    and `library-recommend` — both now read enrich-populated `media_stream` rows
    from the indexer DB (`hdr_format` / `is_atmos` columns pre-existed and are
    populated by `library-index --mode enrich`). The `--from-index` flag is now
    accepted-but-ignored (the DB is always the sole source).
  - `library-doctor` / `library audit` now surface items without a valid NFO
    (the `nfo_missing` / `nfo_incomplete` `item_issue` rows) with a repair hint
    pointing at `library-rescrape --only nfo`.

### Added

- `personalscraper/insights/` — read-only analytics package over the indexer DB
  (`analytics.py`, `reporter.py`, `recommender.py`, `models.py`); backs
  `library-analyze`, `library-recommend`, and `library-report`.
- `personalscraper/maintenance/` — operator-upkeep package (`disk_cleaner.py`,
  `rescraper.py`); backs `library-clean` and `library-rescrape`.
- `personalscraper/verify/library_checks.py` — standalone re-home of the former
  `library/validator.py` (NFO / artwork / naming conformity), backing
  `library-validate`; registerable in the future Check plugin system.
- `personalscraper/naming_patterns.season_number_from_dir()` helper.

### Removed

- `personalscraper/library/` package (all modules) — responsibilities re-homed
  into `indexer/scanner/_modes/_item_stage*`, `insights/`, `maintenance/`, and
  `verify/library_checks.py`.

## [0.18.0] — 2026-05-29

### Added

- **Multi-filesystem support** (`FilesystemCapability` strategy table,
  `personalscraper/indexer/_fs_capability.py`): the pipeline now adapts rsync
  flags and indexer tier-1 drift behaviour per destination filesystem type.
  Supported keys: `ntfs_macfuse` (unchanged), `apfs`, `hfsplus`, `exfat`,
  `ext4` (data-only), and `unknown` (NTFS-safe restrictive fallback).
- `resolve_capability(path, fs_type_override)`
  (`personalscraper/indexer/_fs_capability.py`): a **single shared resolver**
  consumed by **both** the transfer layer (`dispatch.dispatcher.Dispatcher`)
  and the indexer scanner (`indexer/scanner/_scan_orchestrator.py`). This
  guarantees a disk's filesystem type is honoured uniformly end-to-end —
  transfer and scan can never diverge. An explicit `DiskConfig.fs_type`
  override beats `probe_mount` auto-detection.
- `FsProbe` (`personalscraper/indexer/_fs_probe.py`): single cached `mount`
  shell-out replacing three independent parsers (`db.py`,
  `scanner/_spotlight.py`, `scanner/__init__.py`). `canonical_fs_type` matches
  macFUSE/NTFS driver tokens by substring, fixing the `ufsd_NTFS` exact-token
  dead branch in `_spotlight.try_attach`.
- FS-aware tier-1 fingerprint helpers `normalize_tier1` and `round_mtime_ns`
  (`personalscraper/indexer/fingerprint.py`), consumed by the live scanner
  modes `scanner/_modes/incremental.py` and `scanner/_modes/quick.py`. On
  exFAT, ctime is dropped from the tier-1 tuple and mtime is floored to a
  2-second bucket; on HFS+, mtime is floored to a 1-second bucket. NTFS / APFS
  / ext4 keep the legacy `(size, mtime_ns, ctime_ns)` 3-tuple unchanged.
- FS-aware Merkle and dir-mtime **gating** layer: the Merkle root short-circuit,
  the `compute_merkle_delta` bulk-change freeze guard, and the dir-mtime subtree
  skip now bucket mtime per the disk capability
  (`_walker.py::_build_disk_fingerprints` / `_sample_fresh_fingerprints` and the
  dir-mtime compares in incremental / quick). On a coarse filesystem (HFS+ 1 s,
  exFAT 2 s) sub-bucket mtime jitter can no longer defeat the Merkle
  short-circuit nor spuriously trip the bulk-change freeze on a healthy disk;
  NTFS / APFS / ext4 (granularity 1) keep a byte-identical Merkle root.
- `DiskConfig.fs_type` optional override: escape hatch for unrecognised
  macFUSE driver tokens; falls back to the NTFS-safe `unknown` capability for
  any unrecognised value. The scanner override map is keyed on the **stable**
  `DiskConfig.id` (== the immutable `DiskRow.label`), not on the mutable
  `mount_path`, so a runtime remount can no longer drop the operator override.

### Changed (per-FS dispatch)

- Per-FS illegal-filename relaxation now applies **end-to-end**: the
  illegal-name gate in `dispatch/_movie.py` / `_tv.py` runs **after** the
  destination disk is resolved and uses that disk's
  `capability.illegal_name_regex`. A `:`-titled item is no longer skipped when
  the destination is a POSIX filesystem (APFS / HFS+ / exFAT / ext4, where the
  regex is `None`); on an NTFS / `unknown` destination it is still skipped.
- `multifs` pytest marker: capability / probe / argv / tier-1 / scan /
  diskconfig tests tagged; no real disks required (faked mount/stat fixtures).

### Fixed

- `_spotlight.try_attach` dead branch: `ufsd_NTFS` mounts were not recognised
  as macFUSE volumes due to exact-token vs substring asymmetry. Now fixed via
  substring matching in `canonical_fs_type`.

### Changed

- Probe timeout for the `db.py` pre-open check: 5 s → 10 s (single cached
  shell-out shared with the scanner modules). Intentional; documented in
  `docs/reference/storage.md`.
- `rsync()` and `rsync_merge()` in `dispatch/_transfer.py` now read flags from
  `FilesystemCapability.rsync_flags` (defaulting to `NTFS_MACFUSE`) instead of
  hardcoded literals. The NTFS argv is pinned byte-for-byte by a golden test
  (`tests/dispatch/test_transfer_argv.py`).

## [0.17.0] — 2026-05-29

### Added

- `core/_contracts.py`: canonical home for `CircuitOpenError`, `ApiError`, `MediaType`
  (re-exported from `api/_contracts.py` for backward compatibility).
- `conf/models/_ranking.py`: canonical home for `ThresholdEntry`, `RankingCriterion`,
  `RankingBonuses`, `RankingConfig` (re-exported from `api/tracker/_ranking.py`).
- `core/media_types.py`: canonical home for `VIDEO_EXTENSIONS`, `FileType`,
  `is_trailer_filename` (promoted from `sorter/file_type.py`).
- `schema_version: int = 1` field on the `Event` base class — threads through
  `event_to_envelope` / `event_from_envelope`.
- `tests/architecture/test_layering.py`: AST-based guard enforcing that `core/`
  and `conf/` do not import upward into `api/` or upper layers.
- `tests/architecture/test_event_schema_version.py`: invariant tests for `schema_version`.
- `tests/architecture/test_registry_events_contract.py`: invariant tests asserting all
  5 registry events subclass `Event` and are envelope-round-trippable.

### Changed

- 5 provider-registry events (`ProviderFallbackTriggered`, `ProviderExhaustedEvent`,
  `LockedCapabilityUnresolved`, `RegistryFanOutCompleted`, `RegistryBootValidated`)
  now subclass `Event` (`frozen=True, kw_only=True`); auto-registered in
  `_EVENT_CLASS_REGISTRY`; production event catalog grows from 18 to 23.
- `sorter/file_type.py` no longer exports shared constants — `detect_file_type` and
  `detect_dir_type` remain; 23 non-`sorter` import lines rewritten to `core.media_types`.
- `core/circuit.py` and `conf/classifier.py` import from `core._contracts` instead of
  `api._contracts`; `conf/models/api_config.py` imports from `conf/models/_ranking`.

### Fixed

- Removed `# type: ignore[arg-type]` suppression on registry event `emit()` call
  (`api/metadata/registry/__init__.py`) — no longer needed now that events subclass `Event`.

### Architecture

- Closes the P1 roadmap prerequisite for the Web Management UI, Watcher Service,
  and Web UI Registry Consumer items (see `ROADMAP.md` P2 entries).

## [0.16.0] — 2026-05-27

### Added

- **Provider Registry** (`personalscraper/api/metadata/registry/`): `ProviderRegistry`
  class with `chain`, `fan_out`, and `locked` operations. Config-driven provider
  ordering via `config/providers.json5`. Circuit-breaker aware. Boot-time validation
  with aggregated `RegistryConfigError`. EventBus events for all dispatch outcomes.
- `personalscraper info providers` CLI command: prints per-provider circuit state snapshot.
- `conf/models/providers.py`: `ProvidersConfig` Pydantic model.
- `config.example/providers.json5`: provider ordering template.
- `AppContext.provider_registry`: feature delivered at boundary, threaded through pipeline and CLI commands.

### Changed

- `scraper/orchestrator.py`, `movie_service.py`, `tv_service.py`: hardcoded
  `self._tmdb`/`self._tvdb` replaced by `registry.chain(...)`. No façade.
- `trailers/orchestrator.py`, `library/rescraper.py`, `commands/library/scan.py`:
  migrated to registry injection.
- All direct `TMDBClient`/`TVDBClient` consumer files now route through the registry
  (verified via ACC-02: `rg TMDBClient personalscraper/ | grep -v api/metadata/` returns no constructor calls).

### Internal

- Characterization tests (`tests/integration/scraper/test_legacy_fallback_snapshot.py`)
  lock in pre-refactor behavior as the equivalence anchor through Phase 1+2 migration.
- 15 HTTP-level integration tests (`tests/integration/api/metadata/registry/test_registry_http.py`)
  cover chain fallback, HALF_OPEN probe semantics, locked + IDCrossRef escape, fan_out partial.
- 40 unit tests (`tests/unit/api/metadata/registry/`) cover all 11 capability Protocols + boot validation.
- Event-bus required-signature contract preserved (no `EventBus | None` in registry public API).

### Phase 7 — Chain semantics in production

- `scraper/movie_service.py` and `scraper/tv_service.py` migrated from
  transitional `registry.get("tmdb")` direct access to
  `registry.chain(MovieDetailsProvider)` and `registry.chain(TvDetailsProvider)`
  per DESIGN §6.2.
- `ProviderFallbackTriggered` event emitted on every per-provider classified
  failure (circuit_open / network); `ProviderExhaustedEvent` emitted when every
  chain provider failed (commits `fba4f0b4`, `f3ce3c8c`).
- `fan_out()` return widened from raw list to `FanOutResult[C]` carrying
  `values` + `attempted` (commit `8900f7e1`) — synchronous callers gain
  provenance without subscribing to the bus.

### Phase 8 — Type design hardening

- `Mode` enum promoted to `StrEnum` (Python 3.12+; commit `9377a9e6`).
- Exhaustive `@overload` partition on `chain` / `fan_out` / `locked`: every
  capability has its own overload signature, narrowing the union return at
  type-check time.
- `LockedProvider[C]` preserves the capability type parameter end-to-end
  (Generic[C] retained through `_make_locked`).
- `RegistryProviderName` (semantic NewType over `str`) documented and used
  uniformly at every registry boundary as the canonical "provider name" type.

### Phase 9 — Test infrastructure cleanup

- `typed_settings_stub` fixture introduced for CLI tests (commit `153f7986`)
  — 79 call sites pivoted (commits `120281e8`, `6321c121`, `a937b5ef`,
  `a8535a00`). Replaces ad-hoc settings mocks with a single typed factory that
  composes correctly with the real `ProviderRegistry` boot.

### Phase 10 — `existing_validator` module-size extraction

- `personalscraper/scraper/existing_validator.py` split into three files
  (commit `9e14296a`): `existing_validator.py` orchestration, plus
  `existing_validator_drift.py` and `existing_validator_repair.py` for the
  two main branches. LOC dropped from 1125 → 702 (under the 800-LOC soft
  ceiling, well under the 1000-LOC hard ceiling).

### Phase 11 — Indexer backfill migrated to registry

- `personalscraper/indexer/backfill_ids.py` now receives
  `registry: ProviderRegistry` (commit `c463a330`) — no more typed-client
  extraction via `try/except UnknownProviderError`.
- Ratings aggregation routed through `registry.fan_out(RatingProvider)`;
  canonical details lookup routed through `registry.chain(MovieDetailsProvider)`
  / `registry.chain(TvDetailsProvider)` filtered to the canonical provider
  name.
- CLI `library backfill-ids` passes the registry instead of constructing typed
  clients (commit `c55ccfed`).
- Tests pivoted to registry-aware mocks (commits `1f94e50e`, `34c2ca84`).

### Phase 12 — Roadmap entries for deferrals

- ROADMAP P2/P3 entries added (commit `9ac85eee`) for the three deferrals
  noted during PR review: Web UI Registry Consumer, Active Health Scoring,
  and Hot-Swap Provider Configuration. No code change.

### Phase 13 — Pre-existing flaky-test audit (NO_OP)

- Cited flaky test was already absent from the suite; documented as NO_OP
  in the phase plan (commit `988ccb22`).

### Phase 14 — TVDB lazy bootstrap

- `TVDBClient.__init__` no longer performs the login HTTP call (commit
  `734046fc`). Authentication is deferred to the first capability call,
  letting `ProviderRegistry` boot succeed offline / in tests without an
  outbound TCP connection.

### Phase 15 — Autouse CLI fixture removed

- `_patch_provider_registry_for_cli_tests` autouse fixture removed (commit
  `ed71a98e`). CLI tests now boot the real `ProviderRegistry` on top of
  `typed_settings_stub` (Phase 9). Eliminates the last hidden monkey-patch
  divergence between test and production registry construction.

### Phase 16 — Chain exhaustion contract restored

- `ProviderExhausted` carries `last_exception` (commit `d3baa04b`). Chain
  exhaustion in `movie_service` and `tv_service` now raises
  `ProviderExhausted` (commits `ab32c3f2`, `903c7f51`) per DESIGN §6.2
  contract; callers catch and surface the exception's `last_exception` in
  `result.error` — ACC-13 (error-message preservation) anchor preserved.

### Phase 17 — Protocol `provider_id` widened to `int | str`

- `MovieDetailsProvider.get_movie` and `TvDetailsProvider.get_tv` widened
  to `provider_id: int | str` (commit `6c7b4cc8`). ACC-02 exemption count
  tightened from 6 to 4 remaining episode-specific cast sites (commit
  `a3db3132`).

### Phase 18 — Module-size hard-ceiling fixes

- `scraper/tv_service.py` split: chain helpers extracted to
  `tv_service_episodes.py` (commit `1cb8915c`).
- `indexer/backfill_ids.py` split: canonical-init helpers extracted to
  `backfill_ids_canonical.py` (commit `26b81908`).
- All registry-related modules now under the 800-LOC soft warning.
