/**
 * Shared French error presentation for the decision surfaces (§4.3).
 *
 * Extracted from `DecisionDetail` (revue mobile 2026-07-15): the
 * ResolutionDeck showed the RAW backend detail (« Pipeline lock held ») on a
 * 409, which read as « le scraping manuel est cassé » while a pipeline run
 * simply held the global lock for two minutes. One classifier, both surfaces.
 */

import type { ApiError } from "@/api/client";

/**
 * French message for the per-decision-busy 409 (this decision only).
 *
 * Since the resolve queue (operator directive 2026-07-15) a held
 * ``pipeline.lock`` no longer produces a 409 — the runner waits, visibly.
 * The only remaining resolve 409 is the same-decision idempotence guard.
 */
export const MSG_DECISION_BUSY =
  "Cette décision est déjà en cours de re-scraping. Attendez qu'elle se termine.";

/**
 * Map a known backend error status to a French message.
 *
 * Args:
 *   error: The typed API error.
 *
 * Returns:
 *   A French, actionable message (falls back to the raw detail).
 */
export function frenchErrorDetail(error: ApiError): string {
  switch (error.status) {
    case 409:
      return MSG_DECISION_BUSY;
    case 410:
      return "Cette décision a été remplacée par une version plus récente.";
    case 502:
      return "Le fournisseur de métadonnées est indisponible. Réessayez plus tard.";
    default:
      return error.detail;
  }
}
