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
export type TabId = "followed" | "wanted" | "obligations" | "watcher";

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
  { id: "wanted", label: "Recherches" },
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
  "success" | "warning" | "neutral"
> = {
  disabled: "neutral",
  pending: "warning",
  up_to_date: "success",
};

/** Followed-series lifecycle status → French badge label (C14). */
export const FOLLOW_STATUS_LABEL: Record<string, string> = {
  disabled: "Désactivé",
  pending: "En cours",
  up_to_date: "À jour",
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
