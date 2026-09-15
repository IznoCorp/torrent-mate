// ONE VISIT OF THE ADD SCREEN: the mode it was opened in, and the results it has
// already acted on.
//
// NOT THE STORE'S. A copy kept in the store outlived the screen it described:
// « + » reopened with the previous query in the field, the previous strip
// « N médias ajoutés » and the previous checks. The query is the router's; the
// mode is the router's too, mirrored here for the verbs and the panel, which are
// not components and cannot read it; and what was added belongs to the visit
// that added it.
//
// KEYED BY IDENTITY, never by position: a new answer's first row is not the
// previous answer's first row, and a check kept by position lands on a result
// nobody acted on.
import type { SearchResult } from "./types";

type Mode = "follow" | "identify";

let mode: Mode = "follow";
let added = new Set<string>();

/** Starts a visit: nothing is added yet. Called once per opening of the screen. */
export function beginVisit(): void {
  added = new Set();
}

/**
 * Records the mode the screen is showing.
 *
 * Args:
 *     showing: The router's mode for the screen as it is drawn.
 */
export function setVisitMode(showing: Mode): void {
  mode = showing;
}

/** Whether the visit identifies a folder rather than following a medium. */
export function identifying(): boolean {
  return mode === "identify";
}

/**
 * The key a result is remembered by: its kind and its provider identity, or,
 * when no sheet identifies it, what the provider answered about it.
 *
 * THE KIND IS PART OF THE IDENTITY. A provider numbers its films and its series
 * apart, so one number can name a film and a series; and an answer that gives a
 * film its series' identifiers would otherwise mark the film done the moment the
 * series is followed.
 *
 * Args:
 *     result: The search result.
 *
 * Returns:
 *     A key two different results cannot share.
 */
export function resultIdentity(result: SearchResult): string {
  const ids = result.ids;
  if (ids && Object.keys(ids).length > 0) {
    const identifiers = Object.keys(ids)
      .sort()
      .map((provider) => `${provider}:${ids[provider]}`)
      .join("|");
    return `${result.kind}|${identifiers}`;
  }
  return `${result.title}|${result.kind}|${result.year}`;
}

/**
 * Whether this visit has already acted on a result.
 *
 * Args:
 *     result: The search result.
 *
 * Returns:
 *     True once it was added, followed or associated during this visit.
 */
export function isAdded(result: SearchResult): boolean {
  return added.has(resultIdentity(result));
}

/**
 * Records that this visit acted on a result.
 *
 * Args:
 *     result: The search result.
 */
export function markAdded(result: SearchResult): void {
  added.add(resultIdentity(result));
}

/** How many results this visit has acted on. */
export function addedCount(): number {
  return added.size;
}
