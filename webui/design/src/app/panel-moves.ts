// WHETHER A PANEL ASKED FOR A BEAT AGO MAY STILL OPEN.
//
// A producer reads the query cache, and when what it needs has not landed the
// panel host asks for it and opens the panel when the answer comes
// (`producePanel`'s deferred open). The answer can come after the interface has
// moved on: a card tapped, then the bar, and the card's panel rose over the page
// landed on, a beat later, with its entry pushed over the landing (R513, found
// while diagnosing B-675).
//
// So every ask is numbered, and every move of the interface counts: a newer ask,
// a close of the sheet (every landing verb closes it, and so do Retour and the
// scrim), and a change of page. A deferred open whose number is no longer the
// last one opens nothing — what the reader asked for is no longer what is shown.
//
// A NAMED STATE IS BUILT, NOT WALKED: the harness builds it by closing layers
// and writing pages around the panels it produces, and none of that is the
// reader moving. Only a newer ask counts while it runs (`walk.naming`). It is
// not `walk.driven`, which Retour raises around the page it gives back — and
// Retour is a move.
import type { Store } from "./store";
import { walk } from "./page-switch";

let moves = 0;

/** Counts a move of the interface — a close of the sheet, a change of page. */
export function interfaceMoved(): void {
  if (!walk.naming) moves += 1;
}

/**
 * Numbers a panel being asked for, which supersedes any ask still waiting.
 *
 * @returns The ask's number, for `stillAsked` once its answer lands.
 */
export function askPanel(): number {
  moves += 1;
  return moves;
}

/**
 * Whether nothing has moved since the ask.
 *
 * @param asked The number `askPanel` gave the ask.
 * @returns True when the deferred open may still open.
 */
export function stillAsked(asked: number): boolean {
  return asked === moves;
}

/**
 * Counts every change of page as a move.
 *
 * Read off the store rather than off each landing verb: the bar, the menus, the
 * account sheet, Retour and the boot all write the page, and a verb added later
 * would be a verb this list forgot.
 *
 * @param store The single owner of the mutable state.
 */
export function watchLandings(store: Store): void {
  let page = store.read().state.page;
  store.store.subscribe(() => {
    const now = store.read().state.page;
    if (now === page) return;
    page = now;
    interfaceMoved();
  });
}
