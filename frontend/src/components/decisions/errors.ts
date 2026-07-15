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
 * The two distinct 409 causes a resolve can return.
 *
 * - ``pipeline_lock``: a pipeline run / maintenance holds the GLOBAL
 *   ``pipeline.lock`` (backend detail: ``"Pipeline lock held"``).
 * - ``decision_busy``: THIS decision is already resolving.
 */
export type Conflict409 = "pipeline_lock" | "decision_busy";

/**
 * Classify a 409 ``ApiError.detail`` into its cause.
 *
 * Args:
 *   detail: The raw ``ApiError.detail`` of a 409 response.
 *
 * Returns:
 *   The classified {@link Conflict409} cause.
 */
export function classify409(detail: string): Conflict409 {
  return detail.toLowerCase().includes("pipeline lock")
    ? "pipeline_lock"
    : "decision_busy";
}

/** French message for the pipeline-lock 409 (global run in progress). */
export const MSG_PIPELINE_LOCK =
  "Un pipeline est en cours — la validation repassera dès qu'il se termine (quelques minutes). Réessayez.";

/** French message for the per-decision-busy 409 (this decision only). */
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
      return classify409(error.detail) === "pipeline_lock"
        ? MSG_PIPELINE_LOCK
        : MSG_DECISION_BUSY;
    case 410:
      return "Cette décision a été remplacée par une version plus récente.";
    case 502:
      return "Le fournisseur de métadonnées est indisponible. Réessayez plus tard.";
    default:
      return error.detail;
  }
}
