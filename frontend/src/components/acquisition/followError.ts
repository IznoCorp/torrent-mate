/**
 * Classify a followed-query failure for the ErrorState detail line.
 *
 * The two failure classes must not read as one (panne ≠ absence): a server
 * error carries its status, a device-side failure (network cut, timeout,
 * abort) never reached the server at all and must say so with the browser's
 * own message. No French literal lives here on purpose — ``frontend/src``
 * French is ratcheted and the baseline may never grow.
 */

import { ApiError } from "@/api/client";

/**
 * Produce the human-readable detail for one failed followed-query.
 *
 * Args:
 *   error: The query's error value (react-query passes the thrown object).
 *
 * Returns:
 *   The detail line shown under the « Impossible de charger les suivis »
 *   headline. For an {@link ApiError} it is the server's ``status: detail``;
 *   for anything else it is the browser's own failure message (network,
 *   timeout, abort) — the two classes the operator must be able to tell apart.
 */
export function followLoadErrorDetail(error: unknown): string {
  if (error instanceof ApiError) {
    // The server answered with an error — its message already carries
    // « status : detail », which is the fact the operator needs.
    return error.message;
  }
  if (error instanceof Error) {
    // The request never concluded: the browser's message names the failure
    // ("TypeError: Failed to fetch", "TimeoutError: …"). Raw on purpose —
    // the diagnostic value is the class, not the wording.
    return `${error.name}: ${error.message}`;
  }
  return String(error);
}
