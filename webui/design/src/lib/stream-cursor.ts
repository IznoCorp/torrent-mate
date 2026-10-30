// The order of the event stream, written once.
//
// TWO READERS, ONE ARITHMETIC. The relay compares cursors to refuse one that
// moves backwards; the fake transport compares them to replay from an exclusive
// lower bound. They were separate implementations of the same three lines, which
// is how two ends of one contract drift — and this one has a trap that only has
// to be got wrong once.
//
// COMPARED AS TWO NUMBERS, NEVER AS STRINGS. A Redis stream id is
// `<milliseconds>-<sequence>`, and `"10-0" < "9-0"` is true in a string
// comparison and false in the stream's own order. A lexical compare replays the
// whole log again from the tenth event onward, or lets a cursor walk backwards
// — neither of which announces itself.
//
// IT LIVES IN `lib/` because the fake may import the application's shape and
// never the reverse: a product module importing `mocks/` would ship the mock.

/**
 * Says whether one cursor comes after another in the stream's own order.
 *
 * @param candidate The cursor to judge.
 * @param reached The cursor already reached.
 * @returns True when the candidate is strictly later. A cursor that cannot be
 *   read as two numbers is never later — a malformed id must not be able to
 *   drag the position anywhere.
 */
export function isNewerCursor(candidate: string, reached: string): boolean {
  const [candidateTime, candidateSequence] = candidate.split("-").map(Number);
  const [reachedTime, reachedSequence] = reached.split("-").map(Number);
  if (!Number.isFinite(candidateTime) || !Number.isFinite(reachedTime)) return false;
  if (!Number.isFinite(candidateSequence) || !Number.isFinite(reachedSequence)) return false;
  return candidateTime !== reachedTime
    ? candidateTime > reachedTime
    : candidateSequence > reachedSequence;
}
