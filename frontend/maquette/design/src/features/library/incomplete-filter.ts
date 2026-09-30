// Which of « Incomplets »' rows a category pill keeps.
import type { IncompleteShow, LibraryCategory } from "./types";

/**
 * The incomplete shows a category holds: every one for « Tout », which is the
 * whole library and no filter on it; the ones stored under an engine category
 * the pill stands for otherwise.
 *
 * @param rows The incomplete shows, as the lens reads them.
 * @param category The category pill, or undefined when none is known.
 * @returns The rows the pill keeps.
 */
export function incompleteIn(rows: readonly IncompleteShow[], category: LibraryCategory | undefined): IncompleteShow[] {
  const engineCategories = category?.includes;
  return engineCategories ? rows.filter((show) => engineCategories.includes(show.category)) : [...rows];
}
