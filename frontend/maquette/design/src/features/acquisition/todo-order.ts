// What « À traiter » shows, and in what order — ONE derivation, read by the tab,
// its filter pill's count and the filter panel's counts (§13).
//
// THE LIST IS FLAT (DECIDED 1 of maquette-blocked, the operator's word: « Liste à
// plat avec filtre. »): no section says what unblocks a card; its cause line
// does. The order by default is URGENCY — what needs his judgement, then the
// external blocks the engine lifts on its own, then the closures not yet seen —
// newest first inside each group. The filter keeps one cause; the sort may also
// order every card by its time alone.
import type { QueueCard } from "../../lib/engine-queue";

/** The filter's choices, in the order its panel offers them. */
export const TODO_FILTERS = ["all", "resolve", "plex", "step", "disks", "ratio", "unreachable", "closed"] as const;
export type TodoFilter = (typeof TODO_FILTERS)[number];

/** The sort's choices, in the order its panel offers them. */
export const TODO_SORTS = ["urgency", "newest", "oldest"] as const;
export type TodoSort = (typeof TODO_SORTS)[number];

/** A card's cause, as the filter names it. */
export type TodoCause = Exclude<TodoFilter, "all">;

// Which filter an external cause's token belongs to (maquette-blocked § 1.2).
const EXTERNAL_CAUSE: Record<string, TodoCause> = {
  insufficient_space: "disks",
  library_full: "disks",
  content_missing: "disks",
  ratio_below_threshold: "ratio",
  tracker_unreachable: "unreachable",
  provider_unreachable: "unreachable",
  plex_unreachable: "unreachable",
  client_unreachable: "unreachable",
};

// The urgency groups: his judgement, the engine's own lifts, the closures.
const JUDGEMENT = 0;
const EXTERNAL = 1;
const CLOSED = 2;
const GROUP: Record<TodoCause, number> = {
  resolve: JUDGEMENT, plex: JUDGEMENT, step: JUDGEMENT,
  disks: EXTERNAL, ratio: EXTERNAL, unreachable: EXTERNAL,
  closed: CLOSED,
};

/**
 * The rung a card is stopped on: blocked for his hand, or classified stopped
 * by the engine (`resumes` set).
 *
 * @param card The card.
 * @returns The rung, or undefined.
 */
function stoppedRung(card: QueueCard) {
  return (card.ladder ?? []).find((rung) => rung.state === "blocked" || rung.resumes != null);
}

/**
 * Why a card is in « À traiter », as the filter names it.
 *
 * THE ENGINE CLASSIFIES (BK1): an external block is one whose rung the engine
 * says resumes on its own; its token only says WHICH cause.
 *
 * @param card A card of « À traiter ».
 * @returns Its cause.
 */
export function causeOf(card: QueueCard): TodoCause {
  if (card.closure != null) return "closed";
  if (card.plexMatch !== undefined) return "plex";
  if (card.failedStep !== undefined) return "step";
  const rung = stoppedRung(card);
  if (rung?.resumes === "auto" && rung.reason !== undefined && EXTERNAL_CAUSE[rung.reason] !== undefined)
    return EXTERNAL_CAUSE[rung.reason];
  return "resolve";
}

/**
 * When a card stopped: its closure's time, else its rung's — epoch seconds.
 *
 * @param card The card.
 * @returns The time, or null when the answer carries none.
 */
export function stoppedAt(card: QueueCard): number | null {
  return card.closure?.at ?? stoppedRung(card)?.blockedSince ?? null;
}

/**
 * Newest first; a card with no time last, in the order it came.
 *
 * @param left One card's time.
 * @param right The other's.
 * @returns The comparison.
 */
function newestFirst(left: number | null, right: number | null): number {
  if (left === null || right === null) return (left === null ? 1 : 0) - (right === null ? 1 : 0);
  return right - left;
}

/**
 * The cards « À traiter » draws, filtered and ordered.
 *
 * @param cards Every card of the list (`todoCards`).
 * @param filter The filter in force.
 * @param sort The sort in force.
 * @returns The cards drawn, in their order.
 */
export function orderTodo(cards: QueueCard[], filter: TodoFilter, sort: TodoSort): QueueCard[] {
  const kept = filter === "all" ? [...cards] : cards.filter((card) => causeOf(card) === filter);
  const time = (card: QueueCard) => stoppedAt(card);
  if (sort === "newest") return kept.sort((left, right) => newestFirst(time(left), time(right)));
  if (sort === "oldest") return kept.sort((left, right) => {
    const [one, other] = [time(left), time(right)];
    if (one === null || other === null) return newestFirst(one, other);
    return one - other;
  });
  return kept.sort((left, right) => GROUP[causeOf(left)] - GROUP[causeOf(right)]
    || newestFirst(time(left), time(right)));
}

/**
 * How many cards each filter keeps.
 *
 * @param cards Every card of the list.
 * @returns The count per filter, « all » included.
 */
export function todoCounts(cards: QueueCard[]): Record<TodoFilter, number> {
  const counts = Object.fromEntries(TODO_FILTERS.map((filter) => [filter, 0])) as Record<TodoFilter, number>;
  counts.all = cards.length;
  for (const card of cards) counts[causeOf(card)] += 1;
  return counts;
}
