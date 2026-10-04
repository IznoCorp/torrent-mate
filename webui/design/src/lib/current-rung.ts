// Where a ladder stands — ONE derivation, read by the card that draws it and
// by the write that sets a card aside, so the two never name different rungs.

/**
 * The rung a card stands on: the one in motion, waiting or stopped; else the one
 * after the last passed — a rung the row never lived, before it, is not where it
 * stands — or the last when every one is passed.
 *
 * @param ladder The medium's rungs.
 * @returns The current rung's index.
 */
export function currentRung(ladder: readonly { state: string }[]): number {
  // A rung never lived is not where it stands either, like one not reached.
  const active = ladder.findIndex(
    (rung) => rung.state !== "done" && rung.state !== "pending" && rung.state !== "skipped");
  if (active !== -1) return active;
  const done = ladder.map((rung) => rung.state).lastIndexOf("done");
  return Math.min(done + 1, ladder.length - 1);
}
