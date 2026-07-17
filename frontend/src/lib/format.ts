/**
 * Shared French-locale display formatters (ACC-10 — one owner).
 *
 * Every date / size / duration / relative-time helper the UI shows lives here
 * once, plus the pipeline run-outcome → Badge tone+label map. Component-local
 * copies previously drifted (e.g. a typographic vs straight apostrophe in
 * ``à l'instant``); this module is the single source of truth.
 *
 * French-locale unit conventions: ``Go`` (gigaoctet) and ``To`` (téraoctet).
 */

import type { BadgeProps } from "@/components/ui/badge";

// ---------------------------------------------------------------------------
// Sizes
// ---------------------------------------------------------------------------

/**
 * Format a size in gigaoctets adaptively — ``Go`` below 1024, ``To`` above.
 *
 * One decimal maximum, with a trailing ``.0`` stripped so round values render
 * bare (``"12 Go"``, not ``"12.0 Go"``). Large libraries no longer display as
 * ``"20658.0 Go"`` but as ``"20.2 To"`` (U1, operator-reported).
 *
 * Args:
 *   gb: The value in gigaoctets.
 *
 * Returns:
 *   A formatted string like ``"238.5 Go"``, ``"12 Go"``, or ``"20.2 To"``.
 */
export function formatGb(gb: number): string {
  const inTb = gb >= 1024;
  const value = inTb ? gb / 1024 : gb;
  const rendered = value.toFixed(1).replace(/\.0$/, "");
  return `${rendered} ${inTb ? "To" : "Go"}`;
}

/**
 * Format a byte size as a compact human string (e.g. ``1.6 Go``).
 *
 * Args:
 *   bytes: The size in bytes.
 *
 * Returns:
 *   ``"—"`` for non-positive sizes, ``"X.Y Go"`` at or above 1 Go, else
 *   ``"N Mo"`` (never below 1 Mo).
 */
export function formatSize(bytes: number): string {
  if (bytes <= 0) return "—";
  const gb = bytes / 1_000_000_000;
  if (gb >= 1) return `${gb.toFixed(1)} Go`;
  const mb = bytes / 1_000_000;
  return `${String(Math.max(1, Math.round(mb)))} Mo`;
}

// ---------------------------------------------------------------------------
// Dates / durations / relative time
// ---------------------------------------------------------------------------

/**
 * Format an ISO 8601 UTC timestamp into a French-localised date+time string.
 *
 * Args:
 *   iso: The ISO 8601 UTC timestamp.
 *
 * Returns:
 *   A short date+time string formatted for the ``fr`` locale.
 */
export function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("fr", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

/**
 * Format a Unix-epoch float as a human-readable datetime in French.
 *
 * Args:
 *   epoch: Unix-epoch seconds, or ``null`` / ``undefined``.
 *
 * Returns:
 *   A ``fr-FR`` date+time string, or ``"—"`` when the epoch is nullish.
 */
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
 * Format a duration in seconds to a compact ``Xm Ys`` or ``Ys`` string.
 *
 * Args:
 *   seconds: Duration in seconds, or null/undefined.
 *
 * Returns:
 *   A human-readable duration string, or ``"—"`` if null.
 */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return "—";
  const s = Math.round(seconds);
  if (s < 60) return `${String(s)}s`;
  const mins = Math.floor(s / 60);
  const secs = s % 60;
  return `${String(mins)}m ${String(secs).padStart(2, "0")}s`;
}

/**
 * Format a Unix-epoch float as a relative-time string in French.
 *
 * Args:
 *   epoch: Unix-epoch seconds, or ``null`` / ``undefined``.
 *
 * Returns:
 *   A string like ``"il y a 12 min"``, ``"il y a 3 h"``, or ``"—"``.
 */
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

// ---------------------------------------------------------------------------
// Pipeline run outcome → Badge tone + French label
// ---------------------------------------------------------------------------

/** Maps a pipeline run outcome to a DS Badge tone + French label. */
export const RUN_OUTCOME_BADGE: Record<
  string,
  { readonly tone: BadgeProps["tone"]; readonly label: string }
> = {
  success: { tone: "success", label: "Succès" },
  error: { tone: "danger", label: "Erreur" },
  killed: { tone: "warning", label: "Arrêté" },
  running: { tone: "info", label: "En cours" },
  paused: { tone: "info", label: "En pause" },
};

/** Default outcome info for null/unknown outcomes. */
export const DEFAULT_RUN_OUTCOME = {
  tone: "neutral" as BadgeProps["tone"],
  label: "—",
};

/**
 * Look up the tone + label for a given pipeline run outcome string.
 *
 * Args:
 *   outcome: The pipeline outcome, or null.
 *
 * Returns:
 *   A ``{tone, label}`` pair for the Badge.
 */
export function runOutcomeInfo(outcome: string | null | undefined): {
  readonly tone: BadgeProps["tone"];
  readonly label: string;
} {
  if (outcome == null) return DEFAULT_RUN_OUTCOME;
  return RUN_OUTCOME_BADGE[outcome] ?? DEFAULT_RUN_OUTCOME;
}
