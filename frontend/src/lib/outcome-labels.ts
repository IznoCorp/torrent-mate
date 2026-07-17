/**
 * Shared outcome/state vocabulary for TorrentMate UI.
 *
 * THE SINGLE SOURCE OF TRUTH for mapping backend outcomes and states to French
 * labels and design-system badge tones.  Before this module the codebase carried
 * FIVE divergent local maps — ``success`` → "Réussi" in one place, "Succès" in
 * another; ``killed`` → "Arrêté" vs "Interrompu"; ``error`` → "Erreur" vs "Échec".
 * Every surface that renders a run outcome, acquisition status, or lifecycle
 * state MUST import from here — never define a private map.
 *
 * Rendering rule (H3/E):
 * - ``OUTCOME_TONE`` → Badge tone chip (used for run outcomes).
 * - ``STATE_TONE`` → StatusDot or Badge (used for live states).
 * - ``OUTCOME_LABEL`` / ``STATE_LABEL`` → French text.
 * - Mono (no tone) = machine tokens (e.g. raw enums surfaced in dev-only views).
 *
 * @module outcome-labels
 */

import type { BadgeTone } from "@/components/ui/badge";

// ---------------------------------------------------------------------------
// Outcome maps — run-level terminal/transient states
// ---------------------------------------------------------------------------

/** Backend run outcome → French label. */
export const OUTCOME_LABEL: Record<string, string> = {
  success: "Succès",
  error: "Échec",
  killed: "Interrompu",
  running: "En cours",
  paused: "En pause",
  queued: "En file",
  blocked: "Bloqué",
  pending: "En attente",
  deferred: "Différé",
};

/** Backend run outcome → DS badge tone. */
export const OUTCOME_TONE: Record<string, BadgeTone> = {
  success: "success",
  error: "danger",
  killed: "warning",
  running: "info",
  paused: "info",
  queued: "neutral",
  blocked: "warning",
  pending: "warning",
  deferred: "neutral",
};

// ---------------------------------------------------------------------------
// State maps — live item lifecycle states (not outcomes)
// ---------------------------------------------------------------------------

/** Backend item state → French label. */
export const STATE_LABEL: Record<string, string> = {
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
};

/** Backend item state → DS badge tone. */
export const STATE_TONE: Record<string, BadgeTone> = {
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
};

// ---------------------------------------------------------------------------
// Fallback
// ---------------------------------------------------------------------------

/** Default outcome info for null/unknown outcomes. */
export const DEFAULT_OUTCOME: { readonly tone: BadgeTone; readonly label: string } = {
  tone: "neutral",
  label: "—",
};

// ---------------------------------------------------------------------------
// label helper
// ---------------------------------------------------------------------------

/**
 * Return the French label for a backend outcome string.
 *
 * Args:
 *   outcome: The backend outcome token, or ``null`` / ``undefined``.
 *
 * Returns:
 *   The corresponding French label from {@link OUTCOME_LABEL}, the raw token
 *   itself when the outcome is a non-null unmapped value (honest fallback), or
 *   ``"Jamais exécuté"`` when the outcome is ``null`` or ``undefined``.
 */
export function outcomeLabel(outcome: string | null | undefined): string {
  if (outcome == null) return "Jamais exécuté";
  return OUTCOME_LABEL[outcome] ?? outcome;
}
