/**
 * Which candidates the score does not separate.
 *
 * The engine returns a score per candidate, and it is often the same for
 * several of them: four of « Lucky »'s five real candidates came back at
 * exactly 1.00. Printing that score on each of them suggests a ranking that
 * does not exist, and invites a trust the ranking cannot honour — the tie is
 * precisely why a human is being asked.
 *
 * Rule R57, `frontend/maquette/harness/decision.py`.
 */

/** The shape both decision surfaces pass in. */
export interface Scored {
  readonly score: number;
}

/**
 * Marks the candidates that share the top score.
 *
 * A lone leader is not tied: its score does separate it, so it keeps it.
 *
 * Args:
 *   candidates: The scored candidates, in the order they are drawn.
 *
 * Returns:
 *   One boolean per candidate, true when its score says nothing about it.
 */
export function tiedLeaders(candidates: readonly Scored[]): boolean[] {
  if (candidates.length === 0) return [];
  const top = Math.max(...candidates.map((c) => c.score));
  const leaders = candidates.filter((c) => c.score === top).length;
  return candidates.map((c) => leaders > 1 && c.score === top);
}

/**
 * The sentence a screen says when its leaders tie, or null when they do not.
 *
 * Args:
 *   candidates: The scored candidates.
 *
 * Returns:
 *   The sentence, or null.
 */
export function tieNotice(candidates: readonly Scored[]): string | null {
  const tied = tiedLeaders(candidates).filter(Boolean).length;
  if (tied < 2) return null;
  const numberWords = ["", "Un", "Deux", "Trois", "Quatre", "Cinq"];
  const howMany = numberWords[tied] ?? String(tied);
  return `${howMany} candidats reviennent au même score. Le ranking ne tranche pas — c'est pour cela que la question vous est posée.`;
}
