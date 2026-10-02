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
 * The rows « Incomplets » shows: the category pill's, narrowed by the search.
 *
 * THE FIELD THE PAGE DRAWS ACTS ON EVERY LENS (B-688). The lens drew the search
 * field and never read it, so a title typed there left every incomplete series
 * on screen. It matches the way the listing's read does — the query anywhere in
 * the title, whatever the case — and the pill and its panel count the same rows.
 *
 * @param rows The incomplete series, as the lens reads them.
 * @param category The category pill, or undefined when none is known.
 * @param query What the search field holds.
 * @returns The rows the lens draws.
 */
export function incompleteShown<Row extends { title: string; category: string }>(
  rows: readonly Row[], category: LibraryCategory | undefined, query: string,
): Row[] {
  const wanted = query.toLowerCase();
  return rowsIn(rows, category).filter((row) => row.title.toLowerCase().includes(wanted));
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
 * @param recent « Récents »' rows, as the lens reads them — already searched,
 *     since the listing's read carries the query.
 * @param query What the search field holds, which « Incomplets » applies itself.
 * @returns The count.
 */
export function categoryCount(
  category: LibraryCategory,
  lens: string,
  incomplete: readonly { title: string; category: string }[],
  recent: readonly { category: string }[],
  query: string,
): number {
  if (lens === "inc") return incompleteShown(incomplete, category, query).length;
  if (lens === "rec") return rowsIn(recent, category).length;
  return category.count;
}
