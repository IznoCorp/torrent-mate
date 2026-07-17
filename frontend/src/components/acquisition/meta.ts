/**
 * Acquisition panel metadata — shared mappings and pure helpers.
 *
 * Extracted from the former monolithic `AcquisitionPage.tsx` (C12) so the page
 * shell, the four panels, and their tests can each import only what they need.
 * Everything here is framework-agnostic (no JSX, no hooks) — status→tone/label
 * maps, cadence-temperature tokens, event-invalidation sets and the small
 * epoch/format helpers.
 */

import { type ObligationItem } from "@/api/acquisition";

/** Tab ids for the four panels. */
export type TabId = "followed" | "file" | "obligations" | "watcher";

/**
 * Scheduler `name` of the automatic followed-search (grab) cron job (C15).
 *
 * The followed-search cadence caption is built from this scheduler's live
 * ``schedule`` string — never hardcoded — and omitted when the job is absent.
 */
export const GRAB_JOB_NAME = "personalscraper-grab";

/** Event types the page listens for (DESIGN §Live invalidation). */
export const ACQ_EVENT_TYPES = new Set([
  "SeriesFollowed",
  "SeriesUnfollowed",
  "WantedEnqueued",
  "WantedAbandoned",
  "GrabSucceeded",
  "GrabFailed",
  "SeedObligationRecorded",
  "SeedObligationBreached",
  "SeedObligationSatisfied",
  "RatioMeasured",
  "WatcherRunTriggered",
]);

/** Events that invalidate the entire acquisition namespace. */
export const FULL_INVALIDATE_EVENTS = new Set([
  "SeriesFollowed",
  "SeriesUnfollowed",
]);

/** Events that invalidate the wanted + followed queries. */
export const WANTED_INVALIDATE_EVENTS = new Set([
  "WantedEnqueued",
  "WantedAbandoned",
  "GrabSucceeded",
  "GrabFailed",
]);

/** Events that invalidate the obligations queries. */
export const OBLIGATION_INVALIDATE_EVENTS = new Set([
  "SeedObligationRecorded",
  "SeedObligationBreached",
  "SeedObligationSatisfied",
  "RatioMeasured",
]);

/** Tabs displayed in the page header. */
export const TABS: readonly { id: TabId; label: string }[] = [
  { id: "followed", label: "Suivis" },
  { id: "file", label: "File d'acquisition" },
  { id: "obligations", label: "Obligations" },
  { id: "watcher", label: "Watcher" },
];

/** Allowed status filter values for the wanted queue (includes "all"). */
export type WantedFilter =
  | "all"
  | "pending"
  | "searching"
  | "grabbed"
  | "done"
  | "abandoned";

/** Allowed status filter values for obligations (includes "all"). */
export type ObligationFilter = "all" | "pending" | "breached" | "satisfied";

/** Wanted status filter options. */
export const WANTED_STATUS_OPTIONS = [
  { value: "all", label: "Tous" },
  { value: "pending", label: "En attente" },
  { value: "searching", label: "En recherche" },
  { value: "grabbed", label: "Récupéré" },
  { value: "done", label: "Terminé" },
  { value: "abandoned", label: "Abandonné" },
];

/** Obligation status filter options. */
export const OBLIGATION_STATUS_OPTIONS = [
  { value: "all", label: "Toutes" },
  { value: "pending", label: "En cours" },
  { value: "breached", label: "Non respectée" },
  { value: "satisfied", label: "Respectée" },
];

/** Status → badge tone mapping. */
export const STATUS_TONE: Record<
  string,
  "success" | "danger" | "warning" | "info" | "neutral"
> = {
  active: "success",
  inactive: "neutral",
  pending: "warning",
  searching: "info",
  grabbed: "info",
  done: "success",
  abandoned: "danger",
  satisfied: "success",
  breached: "danger",
  completed: "success",
  failed: "danger",
  killed: "warning",
};

/** Status → French label mapping. */
export const STATUS_LABEL: Record<string, string> = {
  active: "Actif",
  inactive: "Inactif",
  pending: "En attente",
  searching: "En recherche",
  grabbed: "Récupéré",
  done: "Terminé",
  abandoned: "Abandonné",
  satisfied: "Respectée",
  breached: "Non respectée",
  completed: "Succès",
  failed: "Échec",
  killed: "Arrêté",
};

/** Cadence temperature token colour (DS `--temp-*`), by tier. */
export const TEMP_COLOR: Record<string, string> = {
  hot: "var(--temp-hot)",
  warm: "var(--temp-warm)",
  cold: "var(--temp-cold)",
  cutoff: "var(--temp-cutoff)",
};

/** French label for a cadence temperature tier. */
export const TIER_LABEL: Record<string, string> = {
  hot: "recherche fréquente",
  warm: "recherche régulière",
  cold: "recherche espacée",
  cutoff: "abandonnée",
};

/**
 * Followed-series lifecycle status → badge tone (C14).
 *
 * Mirrors the backend-derived ``FollowedSeriesItem.status`` so the UI paints
 * without re-deriving business state in JSX.
 */
export const FOLLOW_STATUS_TONE: Record<
  string,
  "success" | "warning" | "neutral" | "info"
> = {
  disabled: "neutral",
  pending: "warning",
  acquiring: "info",
  incomplete: "warning",
  up_to_date: "success",
};

/** Followed-series lifecycle status → French badge label (C14 / §5). */
export const FOLLOW_STATUS_LABEL: Record<string, string> = {
  disabled: "Désactivé",
  pending: "En attente",
  acquiring: "En cours d'acquisition",
  incomplete: "Épisodes manquants",
  up_to_date: "À jour",
};

/**
 * Film-specific overrides for the two status labels that read as series-only
 * (D2-B). A film has no episodes, so « Épisodes manquants » / « À jour » are
 * wrong on a movie card — the status itself is now ownership-driven (real disk
 * presence), so a film reads « Acquis » once in the library and « Manquant »
 * when absent with nothing in flight. Presentational only; tones are shared.
 */
export const FOLLOW_STATUS_LABEL_MOVIE: Record<string, string> = {
  incomplete: "Manquant",
  up_to_date: "Acquis",
};

/** Followed kind → French badge label (§5 film vs série). */
export const FOLLOW_KIND_LABEL: Record<string, string> = {
  movie: "Film",
  show: "Série",
};

/** Run outcome → badge tone (acquisition recent runs). */
export const RUN_OUTCOME_TONE: Record<
  string,
  "success" | "danger" | "warning" | "neutral"
> = {
  success: "success",
  error: "danger",
  killed: "warning",
};

/** Run outcome → French label (acquisition recent runs). */
export const RUN_OUTCOME_LABEL: Record<string, string> = {
  success: "Succès",
  error: "Erreur",
  killed: "Interrompu",
};

/** French labels for the §5 numeric-result keys persisted by the CLIs. */
export const RUN_RESULT_LABEL: Record<string, string> = {
  detected: "détecté(s)",
  enqueued: "mis en file",
  skipped_owned: "déjà en médiathèque",
  skipped_dup: "doublon(s)",
  grabbed: "récupéré(s)",
  retried: "à retenter",
  abandoned: "abandonné(s)",
  skipped: "ignoré(s)",
  // Pipeline-run fallback summary (derived from per-step native counts).
  processed: "traité(s)",
  errors: "erreur(s)",
  // Reconcile counters (detect runs) — surfaced raw in prod on 2026-07-15.
  closed_owned: "clôturé(s) (en médiathèque)",
  resurrected: "réouvert(s)",
  requeued_missing: "remis en recherche",
};

/** French labels for the watcher deferral reasons (transient ingest skips). */
export const DEFERRED_REASON_LABEL: Record<string, string> = {
  ratio_below_threshold: "ratio de partage insuffisant",
  content_missing: "contenu source introuvable",
  insufficient_space: "espace disque insuffisant",
};

/**
 * Render a run's §5 numeric result as a short French sentence.
 *
 * Args:
 *   result: The counts mapping from the run row, or null/undefined.
 *
 * Returns:
 *   E.g. "3 détecté(s), 2 mis en file" — or "rien de nouveau" when every
 *   count is zero, or "" when no result was recorded.
 */
export function formatRunResult(
  result: Record<string, number> | null | undefined,
): string {
  if (!result) return "";
  const parts = Object.entries(result)
    .filter(([, v]) => v > 0)
    .map(([k, v]) => `${String(v)} ${RUN_RESULT_LABEL[k] ?? k}`);
  return parts.length > 0 ? parts.join(", ") : "rien de nouveau";
}

/** Per-episode §5 state → chip tone (completeness matrix). */
export const EPISODE_STATE_TONE: Record<
  string,
  "success" | "warning" | "info" | "neutral"
> = {
  en_mediatheque: "success",
  en_file: "warning",
  en_cours: "info",
  manquant: "neutral",
};

/** Per-episode §5 state → French label (completeness matrix). */
export const EPISODE_STATE_LABEL: Record<string, string> = {
  en_mediatheque: "En médiathèque",
  en_file: "En file",
  en_cours: "En cours",
  manquant: "Manquant",
};

/** Live download state → Badge tone (A4). */
export const DOWNLOAD_STATE_TONE: Record<
  string,
  "success" | "warning" | "info" | "neutral" | "danger"
> = {
  downloading: "info",
  stalled: "warning",
  seeding: "success",
  paused: "neutral",
  queued: "neutral",
  in_client: "neutral",
  missing: "danger",
  errored: "danger",
};

/** Live download state → French label (A4). */
export const DOWNLOAD_STATE_LABEL: Record<string, string> = {
  downloading: "Téléchargement",
  stalled: "En attente de sources",
  seeding: "Terminé (partage)",
  paused: "En pause",
  queued: "En file",
  in_client: "Dans le client",
  missing: "Introuvable",
  errored: "En erreur",
};

/** Format a Unix-epoch float as a relative-time string in French. */
export function relativeTime(epoch: number | null | undefined): string {
  if (epoch == null) return "—";
  const diff = Date.now() - epoch * 1000;
  if (diff < 60_000) return "à l'instant";
  const mins = Math.floor(diff / 60_000);
  if (mins < 60) return `il y a ${String(mins)} min`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `il y a ${String(hours)} h`;
  const days = Math.floor(hours / 24);
  return `il y a ${String(days)} j`;
}

/** Format a Unix-epoch float as a human-readable datetime in French. */
export function formatDatetime(epoch: number | null | undefined): string {
  if (epoch == null) return "—";
  const d = new Date(epoch * 1000);
  return d.toLocaleString("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Derive the obligation status from timestamps.
 *
 * The backend does not expose a ``status`` field on ObligationItem — the
 * status is implicit in the ``satisfied_at`` / ``breached_at`` columns.
 */
export function obligationStatus(
  item: ObligationItem,
): "satisfied" | "breached" | "pending" {
  if (item.satisfied_at != null) return "satisfied";
  if (item.breached_at != null) return "breached";
  return "pending";
}

/** Extract ``interval_minutes`` from a cadence JSON blob, returning a safe default. */
export function cadenceInterval(
  cadence: Record<string, unknown> | null | undefined,
): number {
  if (cadence == null) return 0;
  const v = cadence.interval_minutes;
  return typeof v === "number" ? v : 0;
}

/** Relative human label until an epoch-seconds instant ("imminente" when due). */
export function untilLabel(epochSec: number, nowMs: number): string {
  const deltaMs = epochSec * 1000 - nowMs;
  if (deltaMs <= 60_000) return "imminente";
  const mins = Math.round(deltaMs / 60_000);
  if (mins < 60) return `dans ~${String(mins)} min`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `dans ~${String(hours)} h`;
  return `dans ~${String(Math.round(hours / 24))} j`;
}

/** Truncate a long string for table display, appending "…" when cut. */
export function truncate(s: string, max: number): string {
  if (s.length <= max) return s;
  return `${s.slice(0, max)}…`;
}
