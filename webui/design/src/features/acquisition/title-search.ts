// The name search of every Acquisition list — one rule, so the three tabs
// cannot disagree on what « contains » means.

/**
 * Whether a title holds the search typed in the filter zone, case and accents
 * ignored. An empty search keeps everything.
 *
 * @param title The title looked at.
 * @param search What was typed, untrimmed.
 * @returns True when the title is kept.
 */
export function titleMatches(title: string, search: string): boolean {
  const plain = (text: string) => text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLocaleLowerCase();
  const term = plain(search.trim());
  return term === "" || plain(title).includes(term);
}
