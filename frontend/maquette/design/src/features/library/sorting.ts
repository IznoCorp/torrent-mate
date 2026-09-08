// HOW THE MÉDIATHÈQUE MAY BE SORTED — the ways, and what each is called.
//
// The engine carried this as `TRIS`, a table of three keys each with its two
// directions, and the register classes it `interface`: the ORDER is the
// library's own vocabulary and the NAMES are the operator's words. Neither is
// an answer a server sends.
//
// SPLIT ON THE LINE THE LANGUAGE RULE DRAWS, as the maintenance risks were: the
// keys are code — they are what the store holds and what `data-setsort`
// carries — and the six names are interface text, in `fr.json`.
//
// PUBLISHED FOR THE ENGINE AND FOR THE RULE, which is `settings-labels.ts`'s
// arrangement exactly: the feature owns the answer, the fragment reads it
// through `window.__sortWays`, and `harness/library_sort.py` reads the NAMES
// from the prototype rather than restating them — a rule carrying its own copy
// of six labels goes green the day the interface renames one.
import i18next from "i18next";

/**
 * The sort keys, in the order the panel offers them.
 *
 * THE ORDER IS THE DECLARATION'S, and it is drawn: the panel lists recent
 * first, then alphabetical, then by what is missing. A `Object.keys` over the
 * resource bundle would make the drawing depend on how a translator's file
 * happens to be written.
 */
export const SORT_KEYS = ["recent", "az", "manque"] as const;

/** The two directions every sort key offers. */
export const SORT_DIRECTIONS = ["normal", "inverse"] as const;

export type SortWay = { normal: string; inverse: string };

/**
 * What each way of sorting is CALLED, both directions.
 *
 * Returns:
 *     One entry per key, in the declared order.
 */
export function sortWays(): Record<string, SortWay> {
  const named: Record<string, SortWay> = {};
  for (const key of SORT_KEYS) {
    named[key] = {
      normal: i18next.t(`panels.sort.ways.${key}.normal`),
      inverse: i18next.t(`panels.sort.ways.${key}.inverse`),
    };
  }
  return named;
}

declare global {
  interface Window {
    /** What each way of sorting is called — read by the dying engine and by a rule. */
    __sortWays?: () => Record<string, SortWay>;
  }
}

window.__sortWays = sortWays;
