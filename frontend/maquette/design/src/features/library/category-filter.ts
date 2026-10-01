// Which of a lens' rows a category pill keeps — « Incomplets »' and « Récents »'.
import type { LibraryCategory } from "./types";

/**
 * The rows a category holds: every one for « Tout », which is the whole
 * library and no filter on it; the ones stored under an engine category the
 * pill stands for otherwise. One function for the rows a lens draws and the
 * count its pill prints, so the figure is the rows drawn.
 *
 * @param rows The lens' rows, as it reads them.
 * @param category The category pill, or undefined when none is known.
 * @returns The rows the pill keeps.
 */
export function rowsIn<Row extends { category: string }>(rows: readonly Row[], category: LibraryCategory | undefined): Row[] {
  const engineCategories = category?.includes;
  return engineCategories ? rows.filter((row) => engineCategories.includes(row.category)) : [...rows];
}

/**
 * What a category counts on a lens — ONE derivation, read by the filter pill
 * and by its panel (§13). EVERY LENS IS FILTERED BY THE SAME PILL, and the
 * category is the same remembered one: « Médias » prints the library's counts;
 * « Récents » and « Incomplets » count the rows they draw — a « Films » on
 * « Incomplets » reads 0, and the lens says why.
 *
 * @param category The category.
 * @param lens The lens in force: `cat`, `rec` or `inc`.
 * @param incomplete « Incomplets »' rows, as the lens reads them.
 * @param recent « Récents »' rows, as the lens reads them.
 * @returns The count.
 */
export function categoryCount(
  category: LibraryCategory,
  lens: string,
  incomplete: readonly { category: string }[],
  recent: readonly { category: string }[],
): number {
  if (lens === "inc") return rowsIn(incomplete, category).length;
  if (lens === "rec") return rowsIn(recent, category).length;
  return category.count;
}
