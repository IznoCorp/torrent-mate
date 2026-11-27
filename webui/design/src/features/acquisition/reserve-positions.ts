// What is spent and the order the pile was arranged in are held as POSITIONS into the reserve.
//
// A RESERVE THAT GROWS KEEPS THEM; ONE THAT IS READ AGAIN DOES NOT. A re-read of the deck — a
// series followed, a write the outbox replayed — answers it without what the account rejected or
// follows, and every card after one that left moves up. The positions held are carried onto the
// cards they named, told by their ids, before anything draws them. A page read after the cache let
// the reserve go is read again like any other.
//
// THE POSITIONS ARE ONE ACCOUNT'S: what it rejected or passed hides nothing from the next one
// signing in on this device (O-9 A).
import { hashKey, type QueryClient } from "@tanstack/react-query";
import { accountQuery, type Account } from "../../lib/account";
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

// The ids the positions held are written against. THEY OUTLIVE THE QUERY: the cache lets an
// unobserved reserve go, and the page read after it is carried by id like any other.
let held: string[] = [];

/** Forgets the ids the positions were written against: for a driven state, which drops them all. */
export function forgetHeldReserve(): void {
  held = [];
}

/** The spent positions: a Set MUTATED IN PLACE, as every writer of it does; a write bumps the store. */
const spentPositions = () => store.read().state.sugGone as Set<number>;

/** Drops what is spent and the order of the pile, and draws the whole reserve again. */
function forgetPositions(): void {
  spentPositions().clear();
  store.write({ sugOrder: null });
  redraw();
}

/**
 * Carries the positions held onto a reserve just read, and draws it, if it moved under them.
 *
 * @param page What the reserve's query holds now.
 */
function carryOnto(page: Schemas["SuggestionPage"]): void {
  const before = held;
  held = page.suggestions.map((one) => one.id);
  if (!isReplaced(before, held)) return;
  const gone = spentPositions();
  const order = (store.read().state.sugOrder as number[] | null | undefined) ?? null;
  const moved = remapPositions(before, held, gone, order);
  gone.clear();
  for (const position of moved.gone) gone.add(position);
  store.write({ sugOrder: moved.order });
  redraw();
}

/**
 * Follows the reserve and the account in the cache: the positions held are carried onto each page
 * the reserve is read as, and dropped when another account is signed in.
 *
 * A listener of the cache is called in the write's own task, so nothing draws in between.
 *
 * @param client The cache the reserve and the account live in.
 * @param key The reserve's query key.
 */
export function followReserve(client: QueryClient, key: readonly unknown[]): void {
  const reserveHash = hashKey(key);
  const accountHash = hashKey(accountQuery.queryKey);
  // WHO THE POSITIONS ARE OF, past a sign-out: the same account signing back in keeps them.
  let signedIn: string | undefined;
  forgetHeldReserve();
  client.getQueryCache().subscribe((event) => {
    if (event.type !== "updated") return;
    const { queryHash, state } = event.query;
    if (state.data === undefined) return;
    if (queryHash === reserveHash) return carryOnto(state.data as Schemas["SuggestionPage"]);
    if (queryHash !== accountHash) return;
    const { id } = state.data as Account;
    const another = signedIn !== undefined && signedIn !== id;
    signedIn = id;
    if (another) forgetPositions();
  });
}
