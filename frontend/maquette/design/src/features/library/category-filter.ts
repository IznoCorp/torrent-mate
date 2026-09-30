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
