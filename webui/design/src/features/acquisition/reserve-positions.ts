// What is spent and the order the pile was arranged in are held as POSITIONS into the reserve.
//
// A RESERVE THAT GROWS KEEPS THEM; ONE THAT IS READ AGAIN DOES NOT. A re-read of the deck — a
// series followed, a write the outbox replayed — answers it without what the account rejected or
// follows, and every card after one that left moves up. The positions held are carried onto the
// cards they named, told by their ids, before anything draws them.
import { hashKey, type QueryClient } from "@tanstack/react-query";
import type { Schemas } from "../../lib/contract-schemas";
import { store } from "../../lib/store-access";

/**
 * Whether a reserve moved under the positions held, rather than only growing at its end.
 *
 * @param before The ids the positions were written against.
 * @param after The ids of the reserve now.
 * @returns True when a position no longer names the card it named.
 */
export function isReplaced(before: readonly string[], after: readonly string[]): boolean {
  return before.some((id, position) => after[position] !== id);
}

/**
 * Carries positions from one reserve onto the next, card by card.
 *
 * A card that left is forgotten; one that arrived takes its place at the end of the order.
 *
 * @param before The ids the positions were written against.
 * @param after The ids of the reserve now.
 * @param gone The spent positions.
 * @param order The order of the pile, or null when none is held.
 * @returns Both, in the new reserve's positions.
 */
export function remapPositions(
  before: readonly string[],
  after: readonly string[],
  gone: ReadonlySet<number>,
  order: readonly number[] | null,
): { gone: Set<number>; order: number[] | null } {
  const at = new Map(after.map((id, position) => [id, position]));
  const moved = (positions: Iterable<number>) => [...positions].flatMap((position) => {
    const to = at.get(before[position]);
    return to === undefined ? [] : [to];
  });
  const kept = order === null ? null : moved(order);
  return {
    gone: new Set(moved(gone)),
    order: kept === null ? null : [...kept, ...after.map((_, position) => position).filter((one) => !kept.includes(one))],
  };
}

// What redraws the feed once the positions are carried: filled by the module that draws it.
let redraw: () => void = () => {};

/**
 * Says what draws the feed again after the reserve moved.
 *
 * @param draw The drawing.
 */
export function onReserveReplaced(draw: () => void): void {
  redraw = draw;
}

/**
 * Follows the reserve in the cache, and carries the positions held each time it is replaced.
 *
 * A listener of the cache is called in the write's own task, so nothing draws in between.
 *
 * @param client The cache the reserve lives in.
 * @param key The reserve's query key.
 */
export function followReserve(client: QueryClient, key: readonly unknown[]): void {
  const reserveHash = hashKey(key);
  let held: string[] = [];
  client.getQueryCache().subscribe((event) => {
    if (event.query.queryHash !== reserveHash) return;
    // A CACHE EMPTIED STARTS AGAIN: what is read next answers to no position held before.
    if (event.type === "removed") held = [];
    if (event.type !== "updated") return;
    const page = event.query.state.data as Schemas["SuggestionPage"] | undefined;
    if (page === undefined) return;
    const before = held;
    held = page.suggestions.map((one) => one.id);
    if (!isReplaced(before, held)) return;
    const state = store.read().state;
    const gone = state.sugGone as Set<number>;
    const moved = remapPositions(before, held, gone, (state.sugOrder as number[] | null | undefined) ?? null);
    // THE SET IS MUTATED IN PLACE, as every other writer of it does, and the write bumps the store.
    gone.clear();
    for (const position of moved.gone) gone.add(position);
    store.write({ sugOrder: moved.order });
    redraw();
  });
}
