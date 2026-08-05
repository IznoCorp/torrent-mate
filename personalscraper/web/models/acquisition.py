"""Pydantic models for the acquisition API (acq-watch feature).

See docs/features/acq-watch/DESIGN.md §3.2–3.3 for the route contracts these
models serve.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, computed_field, model_validator

from personalscraper.web.acquisition.states import (
    EpisodeState,
    FollowStatus,
    derive_follow_status,
    derive_movie_status,
)

# ``EpisodeState`` is imported (not redefined) from
# :mod:`personalscraper.web.acquisition.states`: the OpenAPI schema and the
# runtime derivation therefore read the SAME five-state vocabulary and can never
# drift. The old three-value alias (``en_file`` / ``en_cours`` / ``manquant``)
# died with the local re-derivation that produced it (acq-states phase 5).


class MediaRefResponse(BaseModel):
    """Provider-ID key exposed in API responses (tvdb_id primary)."""

    tvdb_id: int | None = None
    tmdb_id: int | None = None
    imdb_id: str | None = None


class MovieFacts(BaseModel):
    """The single unit's facts a followed FILM derives its card status from.

    A film has no aired catalog (``aired_count`` stays ``None`` on its card), so
    instead of episode counts it carries the raw facts of its one ``wanted`` row
    plus library ownership — the exact arguments
    :func:`~personalscraper.web.acquisition.states.derive_episode_state` takes.
    Exposing the facts rather than a pre-chewed label keeps the derivation in the
    single states module and lets the UI explain WHY a film reads as it does.

    Attributes:
        owned: The library holds a live file for this film (disk presence by
            provider id). Beats a stale ``grabbed`` row.
        wanted_status: The film's ``wanted`` row status, or ``None`` when it has
            no row (never enqueued, or the row could not be read).
        last_search_outcome: Named outcome of its last search pass, or ``None``
            when never searched.
        last_search_found: Takeable candidates the last search reported, or
            ``None`` when the search did not conclude.
    """

    owned: bool = False
    wanted_status: str | None = None
    last_search_outcome: str | None = None
    last_search_found: int | None = None


class FollowedSeriesItem(BaseModel):
    """A single followed series or film in the list response."""

    id: int
    title: str
    media_ref: MediaRefResponse
    active: bool
    #: "show" (default) or "movie" — drives the §5 film lifecycle display
    #: (en attente / en cours d'acquisition / retiré une fois en médiathèque).
    kind: str = "show"
    cadence: dict[str, object] | None = None  # parsed from cadence_json
    added_at: float  # epoch seconds
    #: COUNT of ``pending``/``searching`` wanted rows — raw queue volume, shown
    #: as data. It does NOT drive :attr:`status` any more (acq-states phase 4):
    #: a counter knows nothing about ownership, about the aired catalog, or
    #: about whether a search ever concluded.
    wanted_pending: int
    #: COUNT of wanted rows status='grabbed' — raw volume, same caveat as
    #: :attr:`wanted_pending`: data only, never a status source.
    wanted_grabbed: int = 0
    quality_profile: dict[str, object] | None = None  # read-only, parsed from quality_profile_json
    # Card display metadata (webui-overhaul OBJ3): cached at follow time from the
    # search candidate (poster_url = remote provider image URL); year + season_count
    # additionally backfilled from the indexer when absent. All nullable.
    poster_url: str | None = None
    overview: str | None = None
    year: int | None = None
    season_count: int | None = None
    # Cadence readout (webui-overhaul OBJ3): the next epoch at which an automatic
    # search becomes due for this series (min over its pending wanted items), and
    # the governing temperature tier ("hot"/"warm"/"cold"/"cutoff"). Both are
    # ``None`` when nothing is pending (the series is up to date).
    next_search_at: float | None = None
    cadence_tier: str | None = None
    # Five-state truth facts (acq-states phase 4) — derived from the
    # aired-catalog cache × library ownership × wanted rows × the last search
    # verdict, one count per state. All ``None`` when the series has no cached
    # catalog yet, which now reads ``non_verifie`` (never ``a_jour``).
    #: Aired episodes known for this series (from the detect-written cache).
    #: ``None`` = no catalog knowledge at all. Always ``None`` for films (a film
    #: has no catalog — it carries :attr:`movie_facts` instead).
    aired_count: int | None = None
    #: Aired episodes with a live file in the library (``en_mediatheque``).
    owned_count: int | None = None
    #: Aired, unowned episodes with a takeable candidate known (``a_recuperer``).
    a_recuperer_count: int | None = None
    #: Aired, unowned episodes taken / carried by the pipeline (``en_acquisition``).
    en_acquisition_count: int | None = None
    #: Aired, unowned episodes searched with nothing takeable (``en_attente``).
    en_attente_count: int | None = None
    #: Aired, unowned episodes never searched or inconclusive (``non_verifie``).
    non_verifie_count: int | None = None
    #: Films only: the single unit's facts driving the card (``None`` for shows,
    #: and for a film whose provider ids could not be resolved — which then
    #: reads ``non_verifie``, the honest « we know nothing »).
    movie_facts: MovieFacts | None = None

    #: ``True`` when a priming run (``command='prime'``) is in flight for this
    #: follow — set by the route layer (phase 6), never by the state derivation
    #: itself (a runtime fact, not a property of the persisted counts).
    priming_running: bool = False

    #: ``True`` when a series was followed by TMDB/IMDB id but its TVDB id could
    #: not be resolved — episode detection (``poll_known``) needs a TVDB id, so
    #: the follow is created but flagged so the UI can warn (never a silent inert
    #: follow, §méthode). Always ``False`` for films and for TVDB follows. Set by
    #: the create route only; transient, never persisted.
    tvdb_unresolved: bool = False

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status(self) -> FollowStatus:
        """Lifecycle status — pure delegation to the single state derivation.

        The whole business rule lives in
        :mod:`personalscraper.web.acquisition.states` so the card, the
        completeness matrix and the episode chips can never disagree; this
        property only routes shows to
        :func:`~personalscraper.web.acquisition.states.derive_follow_status`
        (per-state episode counts) and films to
        :func:`~personalscraper.web.acquisition.states.derive_movie_status`
        (their single unit's facts).

        The legacy fallback onto the raw ``wanted_pending`` / ``wanted_grabbed``
        counters is GONE: those counters know nothing about ownership or about
        the aired catalog, and it is precisely their « no rows ⇒ up_to_date »
        branch that declared a freshly-followed series « À jour » while three
        aired episodes were missing (founding incident). They survive as data
        fields for display, never as a status source.

        A priming run in flight overrides the card to ``verification_en_cours``
        BEFORE any derived status (phase 6). The flag is set by the route layer
        from the live ``pipeline_run`` rows; it is never stored in ``acquire.db``
        and can never disagree with the run history.

        Returns:
            The derived lifecycle status.
        """
        if self.priming_running:
            return "verification_en_cours"
        if self.kind == "movie":
            facts = self.movie_facts or MovieFacts()
            return derive_movie_status(
                active=self.active,
                owned=facts.owned,
                wanted_status=facts.wanted_status,
                last_search_outcome=facts.last_search_outcome,
                last_search_found=facts.last_search_found,
            )
        return derive_follow_status(
            active=self.active,
            aired_count=self.aired_count,
            a_recuperer_count=self.a_recuperer_count,
            en_acquisition_count=self.en_acquisition_count,
            en_attente_count=self.en_attente_count,
            non_verifie_count=self.non_verifie_count,
        )


class FollowedResponse(BaseModel):
    """Response for GET /api/acquisition/followed."""

    items: list[FollowedSeriesItem]


class WantedItemResponse(BaseModel):
    """A single wanted item in the paginated list."""

    id: int
    title: str  # joined from followed_series
    kind: str  # "movie" | "episode"
    season: int | None = None
    episode: int | None = None
    status: str  # "pending" | "searching" | "available" | "grabbed" | "done" | "abandoned"
    attempts: int
    enqueued_at: float  # epoch seconds
    last_search_at: float | None = None  # epoch seconds


class WantedResponse(BaseModel):
    """Paginated response for GET /api/acquisition/wanted."""

    items: list[WantedItemResponse]
    total: int
    page: int
    page_size: int


class ObligationItem(BaseModel):
    """A seed obligation with its current ratio state.

    Attributes:
        title: Human-readable media title resolved server-side from
            ``acquire.db`` (wanted → followed_series join), or the
            ``dispatched_path`` basename when the join misses, or
            ``None`` when neither is available.
    """

    info_hash: str
    source_tracker: str
    title: str | None = None
    dispatched_path: str | None = None
    min_seed_time_s: int
    min_ratio: float
    added_at: float  # epoch seconds
    satisfied_at: float | None = None  # epoch seconds
    breached_at: float | None = None  # epoch seconds
    released_at: float | None = None  # epoch seconds
    # Joined from ratio_state (may be None if no ratio recorded)
    observed_ratio: float | None = None
    accumulated_seed_time_s: int | None = None
    hnr_count: int | None = None


class ObligationsResponse(BaseModel):
    """Response for GET /api/acquisition/obligations."""

    items: list[ObligationItem]


class RecentRun(BaseModel):
    """A recent acquisition-relevant pipeline run summary.

    Covers watcher-triggered pipeline runs AND the acquisition CLI runs
    (``follow-detect`` / ``grab``), each carrying its §5 numeric result when
    the CLI recorded one.
    """

    run_uid: str
    started_at: float  # epoch seconds
    ended_at: float | None = None  # epoch seconds
    outcome: str | None = None  # "success" | "error" | "killed" | None
    #: CLI command for acquisition runs ("follow-detect" | "grab"), else None.
    command: str | None = None
    #: What launched the run ("cron" | "cli" | "web" | watcher triggers).
    trigger: str | None = None
    #: §5 « résultat chiffré » — e.g. {"detected": 3, "enqueued": 2} for detect,
    #: {"grabbed": 1, "retried": 0, …} for grab. None when not recorded.
    result: dict[str, int] | None = None


class DeferredTorrent(BaseModel):
    """A completed torrent the watcher currently defers (transient skip).

    Ingest would re-skip it this cycle (ratio below threshold, source content
    unavailable, staging disk full), so the watcher excludes it from the
    pipeline trigger set — without this surface the state would be invisible
    (§1: les automatismes restent visibles).

    Attributes:
        name: Torrent display name.
        reason: Ingest skip reason (``ratio_below_threshold`` |
            ``content_missing`` | ``insufficient_space``).
    """

    name: str
    reason: str


class AcquisitionStatusResponse(BaseModel):
    """Response for GET /api/acquisition/status."""

    last_successful_run_at: float | None = None  # epoch seconds
    watcher_enabled: bool
    recent_runs: list[RecentRun] = []
    #: Torrents transiently deferred by the watcher this cycle (§1 visibility).
    #: Empty when the torrent client is unreachable (fail-soft).
    deferred: list[DeferredTorrent] = []


class MediaSearchResult(BaseModel):
    """One provider match returned by the acquisition media search.

    Mirrors a ``DecisionCandidate`` (provider identity + poster/overview/score)
    plus a ``kind`` tag so the add-by-search cards can show film vs série.

    Attributes:
        provider: The metadata provider (``"tmdb"`` or ``"tvdb"``).
        provider_id: The provider's numeric identifier.
        title: The matched title.
        year: The release year, or ``None`` when the provider did not return one.
        kind: ``"movie"`` or ``"tv"`` (which search chain produced the result).
        poster_url: The provider poster URL, or ``None``.
        overview: A short plot summary, or ``None``.
        score: The matching-engine confidence score (0.0–1.0).
    """

    provider: str
    provider_id: int
    title: str
    year: int | None = None
    kind: str
    poster_url: str | None = None
    overview: str | None = None
    score: float
    #: §5 replacement confirmation: ``True`` when the library already holds a
    #: live file for this provider id — the UI must ask before following (the
    #: pipeline will REPLACE the existing version once acquired).
    already_owned: bool = False


class MediaSearchResponse(BaseModel):
    """Response for GET /api/acquisition/search.

    Attributes:
        results: The scored matches across the requested kind(s), best first.
    """

    results: list[MediaSearchResult]


# ── Request models (write routes) ────────────────────────────────────────


class CreateFollowRequest(BaseModel):
    """Request body for POST /api/acquisition/followed.

    At least one provider ID is required (422 otherwise).  *title* is optional
    — when omitted the backend stores an empty string.  The web form will
    always send a title, but the route accepts ``None`` for programmatic
    clients.
    """

    tvdb_id: int | None = None
    tmdb_id: int | None = None
    imdb_id: str | None = None
    title: str | None = None
    #: "show" (default) or "movie" — the §5 film lifecycle starts here: a movie
    #: follow produces ONE wanted item at detect time and is auto-unfollowed
    #: once the acquired file reaches the library.
    kind: Literal["movie", "show"] = "show"
    # Optional card metadata captured from the add-by-search candidate (OBJ3).
    poster_url: str | None = None
    overview: str | None = None
    year: int | None = None

    @model_validator(mode="after")
    def _at_least_one_id(self) -> "CreateFollowRequest":
        """Validate that at least one provider ID is provided.

        Returns:
            The validated instance.

        Raises:
            ValueError: If all three provider IDs are ``None``.
        """
        if self.tvdb_id is None and self.tmdb_id is None and self.imdb_id is None:
            raise ValueError("At least one provider ID (tvdb_id, tmdb_id, or imdb_id) is required")
        return self


class CadenceShape(BaseModel):
    """Per-series search cadence override (editable).

    The shape mirrors what the backend ``effective_cadence`` resolver consumes
    from ``cadence_json``.  The PATCH endpoint validates incoming cadence
    against this schema before writing to ``cadence_json``.
    """

    interval_minutes: int
    # Future RP9/D2 fields added here (e.g. per-season windows).
    # For S7, interval_minutes is the only active field.


class UpdateFollowRequest(BaseModel):
    """Request body for PATCH /api/acquisition/followed/{id}.

    Every field is optional — only the provided fields are updated.
    *cadence* is validated against :class:`CadenceShape` before writing to
    ``cadence_json``.  ``quality_profile_json`` is intentionally ABSENT
    (RP3a deferred — do NOT expose an editor until the backend consumes it).
    """

    active: bool | None = None
    cadence: CadenceShape | None = None


class GrabTriggerResponse(BaseModel):
    """Response body for ``POST /api/acquisition/followed/{id}/search`` (OBJ3).

    Returned ``202`` when a per-series manual grab has been launched.

    Attributes:
        run_uid: The unique identifier of the launched grab run — the frontend
            polls ``GET /api/pipeline/history/{run_uid}`` for its outcome.
    """

    run_uid: str


# ── Completeness read-model (§5 series: aired vs library vs queue) ─────────


class EpisodeCompleteness(BaseModel):
    """One aired episode's acquisition state (§5 épisode par épisode).

    Attributes:
        episode: Episode number within the season.
        title: Episode title, or ``None`` when the provider omitted it.
        air_date: ISO ``YYYY-MM-DD`` air date.
        state: The five-state reading produced by
            :func:`~personalscraper.web.acquisition.states.derive_episode_state`
            — the SAME derivation the followed card aggregates, so the card and
            this matrix can never disagree about one episode:
            ``en_mediatheque`` (a live file exists in the library),
            ``en_acquisition`` (a torrent was taken, the pipeline carries it),
            ``a_recuperer`` (a takeable candidate is known), ``en_attente``
            (searched, concluded, nothing takeable) or ``non_verifie`` (never
            searched, or the last search did not conclude — panne ≠ absence).
        last_search_outcome: The named outcome of the GOVERNING ``wanted`` row's
            last search pass (``no_candidates`` / ``all_filtered`` /
            ``trackers_unavailable`` / …), or ``None`` when the episode was
            never searched. It is the very fact ``state`` was derived from, and
            it is exposed so the UI can say WHY an episode waits in French
            (« rien de conforme au profil ») rather than leaving the operator
            with a bare « En attente » (NE-DOIT-PAS-4). The raw token is a
            machine value: it MUST be mapped before display, never printed.
    """

    episode: int
    title: str | None = None
    air_date: str | None = None
    state: EpisodeState
    last_search_outcome: str | None = None


class SeasonCompleteness(BaseModel):
    """Per-season aggregate + per-episode detail (§5 saison par saison).

    Attributes:
        season: Season number (1-based; specials excluded by the poller).
        owned: Episodes reading ``en_mediatheque`` (a live library file).
        queued: Episodes « en mouvement » — ``a_recuperer`` + ``en_acquisition``.
            The field NAME is kept from the old three-value vocabulary to bound
            the phase-5 blast radius (the frontend accordion consumes
            ``owned`` / ``queued`` / ``total``); what it COUNTS is now the two
            five-state buckets where something is actually moving. Episodes
            reading ``en_attente`` or ``non_verifie`` are deliberately NOT
            counted here: nothing is in motion for them, and folding them in
            would re-create the « queue volume implies progress » lie the
            five states exist to kill. A rename is phase 8's call.
        total: Aired episodes in the season — the ``annonce`` (future) episodes
            are NOT counted here (nor in ``owned`` / ``queued``): a future
            episode has not aired, so it belongs to no acquisition tally. It is
            counted separately in ``announced``.
        announced: Future episodes of the season (``annonce``) — episode-states
            D2. Display-only: a count of what is coming, kept out of the aired
            tallies and out of the card aggregation entirely.
        episodes: The per-episode states, ordered by episode number (aired AND
            announced — the matrix shows both).
    """

    season: int
    owned: int
    queued: int
    total: int
    announced: int = 0
    episodes: list[EpisodeCompleteness]


class CompletenessResponse(BaseModel):
    """Response for ``GET /api/acquisition/followed/{id}/completeness``.

    Attributes:
        followed_id: The follow this completeness was computed for.
        title: The followed title (display).
        kind: ``"show"`` or ``"movie"`` (movies get an empty seasons list —
            their lifecycle lives on the card status instead).
        provider_catalog_empty: Reserved for a DETECT-confirmed empty catalog —
            « the provider KNOWS the series and lists no episode » (the Top Chef
            case). The web read path can no longer assert it: since acq-states
            phase 5 it never polls a provider, and the ``aired_episode`` cache
            has no marker distinguishing « polled, zero aired » from « never
            polled » (``replace_for_followed`` is skipped entirely on an empty
            poll, precisely so an outage cannot wipe a good cache). It is
            therefore always ``False`` today; an absent catalog surfaces as
            ``source="unknown"`` with empty ``seasons`` instead. The field
            stays in the contract for the day detect persists that marker.
        seasons: Season-by-season completeness, newest season first. Empty when
            no catalog is known — never a fabricated all-missing matrix.
        source: Where the aired catalog came from: ``"cache"`` (the
            detect-written ``aired_episode`` table — the ONLY catalog source)
            or ``"unknown"`` (nothing cached for this follow yet, so the panel
            asserts nothing; the card reads ``non_verifie`` from the same
            absence). The former ``"live"`` value died with the synchronous
            provider fallback (acq-states phase 5) — a web read never polls.
        catalog_refreshed_at: Epoch seconds of the detect pass that wrote the
            cached catalog, or ``None`` when the catalog is unknown — the UI can
            caption « catalogue du JJ/MM » honestly.
    """

    followed_id: int
    title: str
    kind: str
    provider_catalog_empty: bool = False
    seasons: list[SeasonCompleteness]
    source: Literal["cache", "unknown"] = "unknown"
    catalog_refreshed_at: float | None = None


#: Live state of a grabbed torrent, normalised across clients (A4). ``in_client``
#: is the fall-through when the raw client state is not one of the known buckets.
DownloadState = Literal["downloading", "stalled", "seeding", "paused", "queued", "in_client", "missing", "errored"]


class AcquisitionDownload(BaseModel):
    """One grabbed torrent surfaced in the acquisition downloads panel (A4).

    Attributes:
        media_ref: Provider-ID key of the wanted item.
        title: Followed-series/film display title (empty if the follow is gone).
        kind: ``"movie"`` or ``"episode"``.
        season: Season number (episodes only).
        episode: Episode number (episodes only).
        info_hash: The grabbed torrent's info hash.
        name: Torrent display name from the client (empty when ``missing``).
        progress: Download progress 0.0–1.0 (0.0 when the client has no record).
        state: Normalised live state. ``missing`` = grabbed row whose hash the
            client no longer knows (removed / not yet visible) — surfaced
            honestly rather than hidden. ``errored`` = the client reports the
            torrent as broken (see ``error_reason``).
        size_bytes: Total size from the client (0 when unknown).
        error_reason: French explanation when ``state == "errored"`` (e.g.
            "Fichiers manquants sur le disque"), else ``None``. Lets the panel
            show WHY a torrent is stuck rather than a bare state (§8).
    """

    media_ref: MediaRefResponse
    title: str
    kind: str
    season: int | None = None
    episode: int | None = None
    info_hash: str
    name: str = ""
    progress: float = 0.0
    state: DownloadState
    size_bytes: int = 0
    error_reason: str | None = None


class AcquisitionDownloadsResponse(BaseModel):
    """Response for ``GET /api/acquisition/downloads`` (A4).

    Attributes:
        downloads: Active/grabbed downloads, in-progress first then by recency.
        client_available: ``False`` when the torrent client could not be reached
            (the UI shows a soft "client injoignable" note instead of an empty
            list that would read as "no downloads").
    """

    downloads: list[AcquisitionDownload] = []
    client_available: bool = True


class RankingPreviewRelease(BaseModel):
    """One representative release scored under a candidate ranking (#18).

    The ranking editor scores a fixed, illustrative sample set against the
    operator's edited criteria so a weight/value change reorders visible rows —
    a live preview of the acquisition ranking WITHOUT running a real search.

    Attributes:
        title: Human-readable sample release title.
        provider: Tracker wire name the sample stands for (``tr4ker`` / ``c411``).
        resolution: Parsed resolution token (``2160p`` / ``1080p`` / …), if any.
        codec: Parsed video-codec token, if any.
        language: Parsed language / audio-track marker (``MULTI`` / ``VFF`` / …).
        source: Parsed media-source token (``BluRay`` / ``WEB-DL`` / …).
        seeders: Sample seeder count.
        leechers: Sample leecher count — paired with ``seeders`` so the preview
            table shows the supply/demand tension a live scorer considers.
        is_freeleech: Whether the sample is freeleech (earns ``bonuses.freeleech``).
        score: Total score under the candidate ranking.
        excluded: ``True`` when ``seeders`` is below the candidate ``min_seeders``
            — the real ``rank()`` would drop it; the preview keeps it (flagged)
            so the operator SEES the cutoff instead of a row silently vanishing.
    """

    title: str
    provider: str
    resolution: str | None = None
    codec: str | None = None
    language: str | None = None
    source: str | None = None
    seeders: int
    leechers: int
    is_freeleech: bool = False
    score: int
    excluded: bool = False


class RankingPreviewResponse(BaseModel):
    """Response for ``POST /api/acquisition/ranking/preview`` (#18).

    Attributes:
        ranked: The sample releases scored under the candidate ranking, highest
            score first (excluded-by-min_seeders rows sink to the end, flagged).
        known_trackers: The app's tracker roster sourced from the hardcoded factory
            map (:data:`personalscraper.api.tracker._factory._TRACKER_CLASSES`),
            in stable sorted order. The frontend uses this to populate the
            tracker-criterion key select so the operator picks from actual
            providers, not free-text.
    """

    ranked: list[RankingPreviewRelease] = []
    known_trackers: list[str] = []


class JourneyItem(BaseModel):
    """One acquisition's journey through the pipeline (provenance F1, kanban #358).

    Read straight off the F0 provenance registry (``staging_provenance``), joined
    with the follow title. The per-stage timestamps + ``status`` make the journey
    grabbed → ingested → scraped → dispatched legible in the « Parcours » view.

    Attributes:
        info_hash: The grabbed torrent hash (the journey key).
        kind: ``movie`` / ``episode`` (None when unknown).
        media_ref: Identity KNOWN at grab (the deterministic scrape seed).
        scraped_ref: Identity actually scraped, when recorded (audit / drift).
        followed_id: The follow this acquisition came from, if any.
        follow_title: The follow's title (joined) — the human-readable label.
        status: Journey status: grabbed / ingested / scraped / dispatched / reconciled.
        ingest_path: Staging folder created at ingest.
        current_path: Live staging folder (updated through sort/scrape rename).
        dispatch_path: Final destination after dispatch, when reached.
        grabbed_at / ingested_at / scraped_at / dispatched_at: Unix-epoch stage
            timestamps (None until that stage is reached).
        resolution_state: The scrape-arbiter projection (decisions-spine F2) —
            ``awaiting`` / ``resolved`` / ``dismissed``, or None when no decision
            was raised (a confident scrape).
        decision_id: The linked ``scrape_decision.id`` (deep-link target), if any.
        resolution_trigger: Why the item was enqueued (``below_threshold`` /
            ``mid_band`` / ``ambiguous``), for display.
        reconstructed_at: Epoch at which this journey was REBUILT from the surviving
            databases (§14.3), or None for a journey the pipeline wrote itself. On a
            rebuilt row an absent stage timestamp means « unknown », not « not reached ».
    """

    info_hash: str
    kind: str | None = None
    media_ref: MediaRefResponse
    scraped_ref: MediaRefResponse | None = None
    followed_id: int | None = None
    follow_title: str | None = None
    status: str | None = None
    ingest_path: str | None = None
    current_path: str | None = None
    dispatch_path: str | None = None
    grabbed_at: int | None = None
    ingested_at: int | None = None
    scraped_at: int | None = None
    dispatched_at: int | None = None
    resolution_state: str | None = None
    decision_id: int | None = None
    resolution_trigger: str | None = None
    grab_run_uid: str | None = None
    ingest_run_uid: str | None = None
    scrape_run_uid: str | None = None
    dispatch_run_uid: str | None = None
    # F4 (spine-actions): True when this in-flight item is stuck (folder still on disk,
    # no stage advanced it past the idle horizon) — the UI flags it as actionable.
    stuck: bool = False
    # §14.3: non-None when this journey was REBUILT from the surviving databases instead
    # of written by the pipeline as it happened. On such a row a NULL stage timestamp
    # means « unknown », never « stage not reached » — a dispatched media went through
    # ingest/sort/scrape by definition (§14.2). The UI reads this to say « inconnue »
    # instead of drawing a path that cannot exist.
    reconstructed_at: int | None = None


class JourneysResponse(BaseModel):
    """Response for ``GET /api/acquisition/journeys`` (provenance F1).

    Attributes:
        journeys: Acquisition journeys, most-recent (grabbed) first.
    """

    journeys: list[JourneyItem] = []


class AcquisitionOverviewResponse(BaseModel):
    """The « état de la machine » rollup (F5 capstone) — one page over the F0–F4 spine.

    Aggregates the four pillars: acquisitions (``by_status`` / ``in_flight``), en-attente
    (``stuck``), décisions (``awaiting_resolution``), and the watcher/last-run context.
    Every count is an UNCAPPED SQL aggregate (never a frontend count over the 200-capped
    journey list — product-intent §méthode rule 6).

    Attributes:
        by_status: ``{status: count}`` over the spine (grabbed/ingested/scraped/dispatched/reconciled).
        in_flight: Non-terminal total = grabbed + ingested + scraped.
        stuck: In-flight items stuck on disk past the idle horizon (F4 FS-truth).
        awaiting_resolution: The AUTHORITATIVE ``scrape_decision`` pending count.
        watcher_enabled: Whether the acquisition watcher is running (not paused).
        last_successful_run_at: Unix-epoch of the last successful pipeline run, or None.
    """

    by_status: dict[str, int] = {}
    in_flight: int = 0
    stuck: int = 0
    awaiting_resolution: int = 0
    watcher_enabled: bool = True
    last_successful_run_at: int | None = None


class SeasonGrabResponse(BaseModel):
    """Response for a season grab request (R4).

    Attributes:
        season_wanted_id: Rowid of the season wanted row (new or existing).
        season: Season number (1-based).
        absorbed_count: Number of episode rows absorbed by this season wanted.
        reused: ``True`` when an existing LIVE season row was returned (HTTP
            200) instead of a freshly created one (HTTP 201).
        run_started: Whether a scoped acquisition run was actually queued by this
            call. Reports the REAL outcome of the enqueue (§5 — a success toast
            over a dead run is forbidden): ``False`` when the indexer is
            unconfigured, the spawn failed, or the row was merely reused. The
            season row exists either way and the next cron will pick it up.
        run_uid: Identifier of the run to follow — freshly spawned, or the
            in-flight one this call joined. ``None`` when nothing runs. §5
            requires the manual trigger to SHOW the run: the UI polls this uid to
            its numbered result (« X détectés, Y disponibles, Z récupérés ») or
            to the real error, instead of toasting a blind success on the 201.
    """

    season_wanted_id: int
    season: int
    absorbed_count: int
    reused: bool = False
    run_started: bool = False
    run_uid: str | None = None
