/**
 * Typed fetch wrappers for the acquisition API (acq-watch feature).
 *
 * Every function binds through {@link apiFetch} so path, method, request body,
 * path params, and query params are all checked against the OpenAPI-generated
 * ``schema.d.ts`` — no ``any`` at any call site.
 *
 * Mutating endpoints carry the ``X-Requested-With`` header (reusing
 * ``XRW_HEADERS`` from client.ts).  Reads are header-free.
 */

import type { QueryParamsOf, SuccessBody } from "./_schema-helpers";
import type { components, paths } from "./schema";
import { XRW_HEADERS, apiFetch } from "./client";

// ---------------------------------------------------------------------------
// Response types
// ---------------------------------------------------------------------------

/** Response type for GET /api/acquisition/followed */
export type FollowedResponse = SuccessBody<
  paths["/api/acquisition/followed"]["get"]["responses"]
>;

/** A single FollowedSeriesItem from the array */
export type FollowedSeriesItem = FollowedResponse["items"][number];

/** Query params for GET /api/acquisition/followed */
export type FollowedParams = QueryParamsOf<
  paths["/api/acquisition/followed"]["get"]
>;

/** Response type for GET /api/acquisition/wanted */
export type WantedResponse = SuccessBody<
  paths["/api/acquisition/wanted"]["get"]["responses"]
>;

/** A single WantedItemResponse from the array */
export type WantedItem = WantedResponse["items"][number];

/** Query params for GET /api/acquisition/wanted */
export type WantedParams = QueryParamsOf<
  paths["/api/acquisition/wanted"]["get"]
>;

/** Response type for GET /api/acquisition/obligations */
export type ObligationsResponse = SuccessBody<
  paths["/api/acquisition/obligations"]["get"]["responses"]
>;

/** A single ObligationItem from the array */
export type ObligationItem = ObligationsResponse["items"][number];

/** Query params for GET /api/acquisition/obligations */
export type ObligationsParams = QueryParamsOf<
  paths["/api/acquisition/obligations"]["get"]
>;

/** Response type for GET /api/acquisition/status */
export type AcquisitionStatusResponse = SuccessBody<
  paths["/api/acquisition/status"]["get"]["responses"]
>;

/** Response type for GET /api/acquisition/search */
export type MediaSearchResponse = SuccessBody<
  paths["/api/acquisition/search"]["get"]["responses"]
>;

/** A single media search result from the array */
export type MediaSearchResult = MediaSearchResponse["results"][number];

/** Query params for GET /api/acquisition/search (``q`` required, ``kind`` optional). */
export type MediaSearchParams = QueryParamsOf<
  paths["/api/acquisition/search"]["get"]
>;

/** Request body for POST /api/acquisition/followed */
export type CreateFollowRequest =
  paths["/api/acquisition/followed"]["post"]["requestBody"]["content"]["application/json"];

/** Request body for PATCH /api/acquisition/followed/{followed_id} */
export type UpdateFollowRequest =
  paths["/api/acquisition/followed/{followed_id}"]["patch"]["requestBody"]["content"]["application/json"];

/** Response type for GET /api/acquisition/followed/{followed_id}/completeness (§5). */
export type CompletenessResponse = SuccessBody<
  paths["/api/acquisition/followed/{followed_id}/completeness"]["get"]["responses"]
>;

/** One season of the §5 completeness matrix. */
export type SeasonCompleteness = CompletenessResponse["seasons"][number];

/** One aired episode of the §5 completeness matrix. */
export type EpisodeCompleteness = SeasonCompleteness["episodes"][number];

/** A recent acquisition run (with its §5 numeric result when recorded). */
export type AcquisitionRecentRun =
  AcquisitionStatusResponse["recent_runs"][number];

/** Response type for GET /api/acquisition/downloads (A4 live progress). */
export type AcquisitionDownloadsResponse = SuccessBody<
  paths["/api/acquisition/downloads"]["get"]["responses"]
>;

/** One grabbed torrent's live progress row. */
export type AcquisitionDownload =
  AcquisitionDownloadsResponse["downloads"][number];

// ---------------------------------------------------------------------------
// Stable TanStack Query keys
// ---------------------------------------------------------------------------

/**
 * Stable React-Query keys for the acquisition domain.
 *
 * Exported so mutations and the event-stream patch can invalidate the exact
 * same cache entries.  Follows the established ``decisionsKeys`` /
 * ``pipelineKeys`` / ``maintenanceKeys`` pattern.
 */
export const acqKeys = {
  /** Root acquisition key: ``['acquisition']``.  Invalidated on any mutation. */
  all: ["acquisition"] as const,

  /** Followed list query key: ``['acquisition', 'followed', {active}]``. */
  followed: (params: FollowedParams = {}) =>
    [...acqKeys.all, "followed", params] as const,

  /** Wanted list query key: ``['acquisition', 'wanted', {status, page, page_size}]``. */
  wanted: (params: WantedParams = {}) =>
    [...acqKeys.all, "wanted", params] as const,

  /** Obligations list query key: ``['acquisition', 'obligations', {status}]``. */
  obligations: (params: ObligationsParams = {}) =>
    [...acqKeys.all, "obligations", params] as const,

  /** Acquisition status query key: ``['acquisition', 'status']``. */
  status: () => [...acqKeys.all, "status"] as const,

  /**
   * Tracked-run key: ``['acquisition', 'status', 'tracked', runUid]`` — the
   * status list scoped to one launched run's terminal poll (A4 / §5).
   */
  trackedRun: (runUid: string | null) =>
    [...acqKeys.status(), "tracked", runUid] as const,

  /** Media search query key — its OWN root, deliberately outside
   *  ``acqKeys.all``: every follow mutation invalidates that namespace, and a
   *  provider search re-fetching after each add burned quota for nothing.
   *  Nothing a mutation changes lives in a search result. */
  search: (params: MediaSearchParams) =>
    ["acquisition-search", params] as const,

  /** Completeness query key: ``['acquisition', 'completeness', id]`` (§5). */
  completeness: (id: number) => [...acqKeys.all, "completeness", id] as const,

  /** Downloads query key: ``['acquisition', 'downloads']`` (A4). */
  downloads: () => [...acqKeys.all, "downloads"] as const,

  /** Machine-state overview query key: ``['acquisition', 'overview']`` (F5). */
  overview: () => [...acqKeys.all, "overview"] as const,
  stalledGrabs: () => [...acqKeys.all, "stalled-grabs"] as const,
  toHandle: () => [...acqKeys.all, "to-handle"] as const,

  /** Journeys query key: ``['acquisition', 'journeys']`` (F1). */
  journeys: () => [...acqKeys.all, "journeys"] as const,
};

// ---------------------------------------------------------------------------
// Read endpoints
// ---------------------------------------------------------------------------

/**
 * Fetch followed series list.
 *
 * Sends ``GET /api/acquisition/followed`` with optional ``active`` filter.
 * Read-only — no ``X-Requested-With`` header.
 *
 * Args:
 *   params: Optional filter (``active``: ``"active"``, ``"all"``, or
 *       ``"inactive"``).
 *
 * Returns:
 *   A {@link FollowedResponse} with ``items`` array.
 */
export function getFollowed(
  params: FollowedParams = {},
): Promise<FollowedResponse> {
  return apiFetch("/api/acquisition/followed", {
    method: "get",
    params: { query: params },
  });
}

/**
 * Fetch paginated wanted items.
 *
 * Sends ``GET /api/acquisition/wanted`` with optional status filter and
 * pagination.  Read-only — no ``X-Requested-With`` header.
 *
 * Args:
 *   params: Optional filter (``status``, ``page``, ``page_size``).
 *
 * Returns:
 *   A {@link WantedResponse} with ``items``, ``total``, ``page``, and
 *   ``page_size``.
 */
export function getWanted(params: WantedParams = {}): Promise<WantedResponse> {
  return apiFetch("/api/acquisition/wanted", {
    method: "get",
    params: { query: params },
  });
}

/**
 * Fetch seed obligations.
 *
 * Sends ``GET /api/acquisition/obligations`` with optional ``status`` filter.
 * Read-only — no ``X-Requested-With`` header.
 *
 * Args:
 *   params: Optional filter (``status``: ``"all"``, ``"pending"``,
 *       ``"breached"``, or ``"satisfied"``).
 *
 * Returns:
 *   An {@link ObligationsResponse} with ``items`` array.
 */
export function getObligations(
  params: ObligationsParams = {},
): Promise<ObligationsResponse> {
  return apiFetch("/api/acquisition/obligations", {
    method: "get",
    params: { query: params },
  });
}

/**
 * Fetch acquisition status (watcher state + recent runs).
 *
 * Sends ``GET /api/acquisition/status``.  Read-only — no ``X-Requested-With``
 * header.
 *
 * Returns:
 *   An {@link AcquisitionStatusResponse} with ``watcher_enabled``,
 *   ``last_successful_run_at``, and ``recent_runs``.
 */
export function getAcquisitionStatus(): Promise<AcquisitionStatusResponse> {
  return apiFetch("/api/acquisition/status", { method: "get" });
}

/**
 * Fetch the live progress of every grabbed torrent (A4).
 *
 * Sends ``GET /api/acquisition/downloads``.  Read-only — no ``X-Requested-With``
 * header.  Fail-soft server-side: a torrent-client outage yields
 * ``client_available=false`` rather than an error.
 *
 * Returns:
 *   An {@link AcquisitionDownloadsResponse} with ``downloads`` +
 *   ``client_available``.
 */
export function getDownloads(): Promise<AcquisitionDownloadsResponse> {
  return apiFetch("/api/acquisition/downloads", { method: "get" });
}

/** Query params for GET /api/acquisition/lookup */
export type MediaLookupParams = QueryParamsOf<
  paths["/api/acquisition/lookup"]["get"]
>;

/** One resolved media, as a search result. */
export type MediaLookupResult = SuccessBody<
  paths["/api/acquisition/lookup"]["get"]["responses"]
>;

/**
 * Resolve ONE media by provider id.
 *
 * The add-by-ID path: it RESOLVES, it does not follow. The operator sees the
 * real title and poster, then decides.
 *
 * Args:
 *   params: provider, provider_id, kind.
 *
 * Returns:
 *   The resolved result.
 */
export function lookupMedia(
  params: MediaLookupParams,
): Promise<MediaLookupResult> {
  return apiFetch("/api/acquisition/lookup", {
    method: "get",
    params: { query: params },
  });
}

/**
 * Search live providers for media to follow (add-by-search, OBJ3).
 *
 * Sends ``GET /api/acquisition/search`` with a title ``q`` and optional
 * ``kind``.  Read-only — no ``X-Requested-With`` header.
 *
 * Args:
 *   params: ``q`` (title to search) + optional ``kind`` (``"movie"``/``"tv"``).
 *
 * Returns:
 *   A {@link MediaSearchResponse} with scored ``results``.
 */
export function searchMedia(
  params: MediaSearchParams,
): Promise<MediaSearchResponse> {
  return apiFetch("/api/acquisition/search", {
    method: "get",
    params: { query: params },
  });
}

// ---------------------------------------------------------------------------
// Mutating endpoints
// ---------------------------------------------------------------------------

/**
 * Follow (or reactivate) a series.
 *
 * Sends ``POST /api/acquisition/followed`` with the ``X-Requested-With``
 * header.  At least one provider ID is required.
 *
 * Args:
 *   body: The {@link CreateFollowRequest} with at least one of ``tvdb_id``,
 *       ``tmdb_id``, or ``imdb_id``, and optional ``title``.
 *
 * Returns:
 *   The created or reactivated {@link FollowedSeriesItem}.
 *
 * Raises:
 *   ApiError: 409 if the series is already actively followed.
 */
export function createFollow(
  body: CreateFollowRequest,
): Promise<FollowedSeriesItem> {
  return apiFetch("/api/acquisition/followed", {
    method: "post",
    body,
    headers: XRW_HEADERS,
  });
}

/**
 * Update a followed series (active flag / cadence).
 *
 * Sends ``PATCH /api/acquisition/followed/{followed_id}`` with the
 * ``X-Requested-With`` header.  Every field is optional — only the provided
 * fields are updated.
 *
 * Args:
 *   id: Rowid of the ``followed_series`` row.
 *   body: The {@link UpdateFollowRequest} with optional ``active`` and
 *       ``cadence`` fields.
 *
 * Returns:
 *   The updated {@link FollowedSeriesItem}.
 *
 * Raises:
 *   ApiError: 404 if the followed_id does not exist.
 */
export function updateFollow(
  id: number,
  body: UpdateFollowRequest,
): Promise<FollowedSeriesItem> {
  return apiFetch("/api/acquisition/followed/{followed_id}", {
    method: "patch",
    body,
    headers: XRW_HEADERS,
    params: { path: { followed_id: id } },
  });
}

/** The provider an add-by-id follow targets. */
export type FollowProvider = "tvdb" | "tmdb" | "imdb";

/** An IMDb id is ``tt`` followed by digits (e.g. ``tt0137523``). */
const IMDB_ID_RE = /^tt\d+$/;

/**
 * Build the follow body for an add-by-id submit, or ``null`` when the id is
 * invalid for the provider (TVDB/TMDB → plain positive digits, IMDB →
 * ``tt\d+``).
 *
 * The plain-digits requirement is checked BEFORE ``Number()`` because the
 * latter coerces ``"1e3"`` → 1000 and ``"0x10"`` → 16, both of which are
 * safe integers — but the operator typing ``"1e3"`` into the by-ID field
 * means the string ``"1e3"``, not the integer 1000, and following that as
 * tvdb_id 1000 would fetch wrong artwork and wrong metadata on a real
 * library.
 *
 * The form is series-only (``kind: 'show'``) — a TVDB id is a series id, and a
 * film is followed from the search cards which carry ``kind: 'movie'``. The
 * server resolves TVDB from a TMDB/IMDB series so detection works.
 */
export function buildIdFollowBody(
  provider: FollowProvider,
  rawId: string,
): CreateFollowRequest | null {
  const value = rawId.trim();
  if (!value) return null;
  if (provider === "imdb") {
    return IMDB_ID_RE.test(value)
      ? { imdb_id: value, kind: "show", replace_owned: false }
      : null;
  }
  // Reject any non-IMDB value that is not plain digits — Number() alone
  // cannot carry this: it coerces "1e3" → 1000 and "0x10" → 16, both of
  // which pass Number.isSafeInteger.  The operator typing "1e3" into the
  // by-ID field means the string 1e3, not the integer 1000.
  if (!/^\d+$/.test(value)) return null;
  const numeric = Number(value);
  // Number.isSafeInteger, not isInteger: a 17-digit-or-longer id still passes
  // isInteger but has already lost precision (JSON would emit 1e+23 for a
  // 23-digit string) — a precision-mangled id must refuse here, never silently
  // follow a wrong id.
  if (!Number.isSafeInteger(numeric) || numeric <= 0) return null;
  return provider === "tvdb"
    ? { tvdb_id: numeric, kind: "show", replace_owned: false }
    : { tmdb_id: numeric, kind: "show", replace_owned: false };
}

/** Response type for POST /api/acquisition/followed/{id}/search (OBJ3). */
export type GrabTriggerResponse = SuccessBody<
  paths["/api/acquisition/followed/{followed_id}/search"]["post"]["responses"]
>;

/**
 * Launch the FULL search chain for one followed series (« Rechercher »).
 *
 * Sends ``POST /api/acquisition/followed/{followed_id}/search`` with the
 * ``X-Requested-With`` header. Server-side this now spawns the ``prime`` runner
 * — detect → search → grab — because a bare grab only claims items already
 * marked takeable and would do nothing at all on a follow that is waiting or
 * unverified. Returns ``202`` with the launched ``run_uid``.
 *
 * Args:
 *   id: Rowid of the ``followed_series`` row.
 *
 * Returns:
 *   The {@link GrabTriggerResponse} with the launched ``run_uid``.
 *
 * Raises:
 *   ApiError: 404 (unknown series) / 409 (a search for this series is already
 *     running — the only permitted refusal).
 */
export function triggerFollowedSearch(
  id: number,
): Promise<GrabTriggerResponse> {
  return apiFetch("/api/acquisition/followed/{followed_id}/search", {
    method: "post",
    headers: XRW_HEADERS,
    params: { path: { followed_id: id } },
  });
}

/**
 * Claim NOW what is already takeable for one follow (« Récupérer maintenant »).
 *
 * Sends ``POST /api/acquisition/followed/{followed_id}/grab`` with the
 * ``X-Requested-With`` header. The counterpart of
 * {@link triggerFollowedSearch}: no catalog poll, no tracker search — it grabs
 * what the last search already marked available, which is exactly what an
 * « À récupérer » item needs. Returns ``202`` with the launched ``run_uid``.
 *
 * Args:
 *   id: Rowid of the ``followed_series`` row.
 *
 * Returns:
 *   The {@link GrabTriggerResponse} with the launched ``run_uid``.
 *
 * Raises:
 *   ApiError: 404 (unknown series) / 409 (a grab for this series is already
 *     running — the only permitted refusal).
 */
export function triggerFollowedGrab(id: number): Promise<GrabTriggerResponse> {
  return apiFetch("/api/acquisition/followed/{followed_id}/grab", {
    method: "post",
    headers: XRW_HEADERS,
    params: { path: { followed_id: id } },
  });
}

/** Response type for POST /api/acquisition/follows/{id}/seasons/{season}/grab (R4).
 *
 * The endpoint returns ``201``, not ``200``, so ``SuccessBody`` does not match —
 * the type is extracted directly from the generated schema.
 */
export type SeasonGrabResponse = components["schemas"]["SeasonGrabResponse"];

/**
 * Manually enqueue a season wanted for a followed series (R4).
 *
 * Sends ``POST /api/acquisition/follows/{id}/seasons/{season}/grab`` with the
 * ``X-Requested-With`` header. Idempotent: returns the existing season row if
 * one already exists.
 *
 * Args:
 *   followedId: Rowid of the ``followed_series`` row.
 *   season: Season number (1-based).
 *
 * Returns:
 *   The {@link SeasonGrabResponse} with the season wanted id and absorbed count.
 *
 * Raises:
 *   ApiError: 404 (unknown series) / 400 (season < 1, or follow is not a show).
 */
export function grabSeason(
  followedId: number,
  season: number,
): Promise<SeasonGrabResponse> {
  return apiFetch(
    "/api/acquisition/follows/{followed_id}/seasons/{season}/grab",
    {
      method: "post",
      headers: XRW_HEADERS,
      params: { path: { followed_id: followedId, season } },
    },
  );
}

/**
 * Launch the aired-episode / film discovery NOW (§5 manual watcher trigger).
 *
 * Sends ``POST /api/acquisition/detect``; returns ``202`` with the run_uid the
 * caller tracks to its numeric result (never a blind success toast).
 *
 * Returns:
 *   The launched run's identifier.
 *
 * Raises:
 *   ApiError: 409 when a detect run is already in flight.
 */
export function triggerDetect(): Promise<GrabTriggerResponse> {
  return apiFetch("/api/acquisition/detect", {
    method: "post",
    headers: XRW_HEADERS,
  });
}

/**
 * Fetch the §5 completeness matrix for one followed series.
 *
 * Sends ``GET /api/acquisition/followed/{followed_id}/completeness`` — the aired
 * catalog read through the five states (in_library / to_grab /
 * acquiring / pending / unverified), per season and per episode.
 *
 * Args:
 *   id: Rowid of the ``followed_series`` row.
 *
 * Returns:
 *   The {@link CompletenessResponse}.
 */
export function getCompleteness(id: number): Promise<CompletenessResponse> {
  return apiFetch("/api/acquisition/followed/{followed_id}/completeness", {
    method: "get",
    params: { path: { followed_id: id } },
  });
}

/**
 * Soft-unfollow a series (sets active=False).
 *
 * Sends ``DELETE /api/acquisition/followed/{followed_id}`` with the
 * ``X-Requested-With`` header.  Returns 204 No Content on success.
 *
 * Args:
 *   id: Rowid of the ``followed_series`` row.
 *
 * Raises:
 *   ApiError: 404 if the followed_id does not exist.
 */
export function deleteFollow(id: number): Promise<void> {
  return apiFetch("/api/acquisition/followed/{followed_id}", {
    method: "delete",
    headers: XRW_HEADERS,
    params: { path: { followed_id: id } },
  });
}

// ---------------------------------------------------------------------------
// Ranking editor (#18) — live preview of the acquisition ranking
// ---------------------------------------------------------------------------

/** The full ranking configuration (criteria + bonuses + min_seeders). */
export type RankingConfig = components["schemas"]["RankingConfig"];

/** One ranking criterion (field + weight + values|thresholds). */
export type RankingCriterion = components["schemas"]["RankingCriterion"];

/** A size-or-count threshold with a score value ({@link ThresholdEntry}). */
export type ThresholdEntry = components["schemas"]["ThresholdEntry"];

/** Response for ``POST /api/acquisition/ranking/preview``. */
export type RankingPreviewResponse = SuccessBody<
  paths["/api/acquisition/ranking/preview"]["post"]["responses"]
>;

/** One scored sample release in the preview. */
export type RankingPreviewRelease = RankingPreviewResponse["ranked"][number];

/**
 * Score the representative sample set under a candidate ranking (live preview).
 *
 * Sends ``POST /api/acquisition/ranking/preview`` — pure/read-only, so it needs
 * no cache invalidation and is safe to call on every debounced edit.
 *
 * Args:
 *   body: The candidate ranking configuration to score with.
 *
 * Returns:
 *   A {@link RankingPreviewResponse} with the scored, sorted samples.
 */
export function previewRanking(
  body: RankingConfig,
): Promise<RankingPreviewResponse> {
  return apiFetch("/api/acquisition/ranking/preview", {
    method: "post",
    body,
    headers: XRW_HEADERS,
  });
}

// ---------------------------------------------------------------------------
// Provenance F1 — the « Parcours » journey view
// ---------------------------------------------------------------------------

/** Response for ``GET /api/acquisition/journeys``. */
export type JourneysResponse = SuccessBody<
  paths["/api/acquisition/journeys"]["get"]["responses"]
>;

/** One acquisition's pipeline journey. */
export type JourneyItem = JourneysResponse["journeys"][number];

/**
 * List each acquisition's pipeline journey (grabbed → ingested → scraped →
 * dispatched) from the provenance registry: ``GET /api/acquisition/journeys``.
 * Read-only, header-free.
 */
export function getJourneys(): Promise<JourneysResponse> {
  return apiFetch("/api/acquisition/journeys", { method: "get" });
}

/** The « état de la machine » rollup (F5): ``GET /api/acquisition/overview``. */
export type OverviewResponse = SuccessBody<
  paths["/api/acquisition/overview"]["get"]["responses"]
>;

/**
 * Fetch the unified machine-state overview (acquisitions + décisions + en-attente).
 * Read-only, header-free.
 */
export function getOverview(): Promise<OverviewResponse> {
  return apiFetch("/api/acquisition/overview", { method: "get" });
}

/** Les acquisitions parquées à « récupéré » : ``GET /api/acquisition/stalled-grabs``. */
export type StalledGrabsResponse = SuccessBody<
  paths["/api/acquisition/stalled-grabs"]["get"]["responses"]
>;

/** One parked acquisition, with the reason it is flagged. */
export type StalledGrabItem = StalledGrabsResponse["items"][number];

/**
 * Fetch the acquisitions parked at « récupéré » that never reached the library.
 * The detail behind the overview alert (§8 — a count must lead to its items).
 */
export function getStalledGrabs(): Promise<StalledGrabsResponse> {
  return apiFetch("/api/acquisition/stalled-grabs", { method: "get" });
}

// ---------------------------------------------------------------------------
// « À traiter » — blocked media carried by one of our acquisitions (§14.3)
// ---------------------------------------------------------------------------

/** One blocked media whose acquisition is ours (spec §3.1). */
export type ToHandleItem = SuccessBody<
  paths["/api/acquisition/to-handle"]["get"]["responses"]
>["items"][number];

/** Response for ``GET /api/acquisition/to-handle``. */
export type ToHandleResponse = SuccessBody<
  paths["/api/acquisition/to-handle"]["get"]["responses"]
>;

/** Fetch the « À traiter » rollup. Read-only, header-free. */
export function getToHandle(): Promise<ToHandleResponse> {
  return apiFetch("/api/acquisition/to-handle", { method: "get" });
}

/** Response of a spine-driven per-item action (rescrape / requeue) — the launched run. */
export type JourneyActionResponse = SuccessBody<
  paths["/api/acquisition/journeys/{info_hash}/rescrape"]["post"]["responses"]
>;

/**
 * Re-scrape one tracked staging item (F4): ``POST /journeys/{info_hash}/rescrape``.
 * Mutating — carries the ``X-Requested-With`` header. 202 with the launched run_uid.
 */
export function rescrapeJourney(
  infoHash: string,
): Promise<JourneyActionResponse> {
  return apiFetch("/api/acquisition/journeys/{info_hash}/rescrape", {
    method: "post",
    params: { path: { info_hash: infoHash } },
    headers: XRW_HEADERS,
  });
}

/**
 * Requeue one item's wanted row (F4): ``POST /journeys/{info_hash}/requeue``.
 * Mutating — carries the ``X-Requested-With`` header. 202 with the launched run_uid.
 */
export function requeueJourney(
  infoHash: string,
): Promise<JourneyActionResponse> {
  return apiFetch("/api/acquisition/journeys/{info_hash}/requeue", {
    method: "post",
    params: { path: { info_hash: infoHash } },
    headers: XRW_HEADERS,
  });
}
