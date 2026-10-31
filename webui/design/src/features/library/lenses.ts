// THE MÉDIATHÈQUE'S LENSES — how the interface groups the engine's leaf categories.
//
// The engine knows LEAF categories only (`movies`, `tv_shows_animation`, …) and
// serves each with its count (K2-G5 = A). Which leaves a pill stands for, its
// order and its name are the interface's: the grouping lives here, the names in
// `fr.json` under `screens.library.lenses`. A lens' count is the sum of its
// leaves', so the figure a pill prints is what the engine counted.
import i18next from "i18next";
import type { Schemas } from "../../lib/contract-schemas";

/** One engine leaf category and its count, as served. */
export type LeafCategory = Schemas["LibraryCategory"];

/** A lens: its id, its name, its count, and the leaves it keeps (`null` for « Tout »). */
export type LibraryLens = {
  id: string;
  label: string;
  count: number;
  includes: string[] | null;
};

/** The lenses, in the order the pill offers them; `includes: null` keeps every leaf. */
const LENSES: readonly { id: string; includes: readonly string[] | null }[] = [
  { id: "all", includes: null },
  { id: "movies", includes: ["movies"] },
  { id: "tv", includes: ["tv_shows"] },
  { id: "anim", includes: ["movies_animation", "tv_shows_animation"] },
  { id: "standup", includes: ["standup"] },
  { id: "doc", includes: ["movies_documentary", "tv_shows_documentary"] },
  { id: "anime", includes: ["anime"] },
  { id: "tvprog", includes: ["tv_programs"] },
  { id: "theater", includes: ["theater"] },
];

/**
 * The leaves one lens keeps, read from the table alone — what the listing's
 * `category` parameter carries, known before any count has landed.
 *
 * @param lensId The lens, as the store and the address name it.
 * @returns Its leaves, or null for « Tout » and for a lens the table does not carry.
 */
export function leavesOf(lensId: string): readonly string[] | null {
  return LENSES.find((lens) => lens.id === lensId)?.includes ?? null;
}

/**
 * The lenses, counted from the served leaves and named in the interface's words.
 *
 * @param leaves The engine's leaf categories with their counts.
 * @returns Every lens, its count the sum of its leaves'.
 */
export function lensesOf(leaves: readonly LeafCategory[]): LibraryLens[] {
  const counted = (includes: readonly string[] | null) =>
    leaves
      .filter((leaf) => includes === null || includes.includes(leaf.id))
      .reduce((total, leaf) => total + leaf.count, 0);
  return LENSES.map((lens) => ({
    id: lens.id,
    label: i18next.t(`screens.library.lenses.${lens.id}`),
    count: counted(lens.includes),
    includes: lens.includes === null ? null : [...lens.includes],
  }));
}
