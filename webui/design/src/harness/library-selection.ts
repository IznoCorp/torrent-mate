// A LIBRARY SELECTION BUILT FROM TITLES, for a named state or a rule.
//
// The selection is keyed by each row's provider identity, because two media may
// share a title. A named state or a rule names the rows it ticks by title, the
// way a reader reads them; each title is taken here to the identity its seeded
// row carries — a listing row, else an incomplete show or a recent arrival. The
// seed's titles a state names are held once, so the first row of a title is that
// title's medium.
import LIBRARY from "../mocks/seeds/library-items.json";
import INCOMPLETE from "../mocks/seeds/incomplete-shows.json";
import RECENT from "../mocks/seeds/recent.json";
import { mediaRefOf, refKey } from "../lib/membership";
import type { Doomed } from "../features/library/delete-dialog";

/**
 * The selection that ticks the seeded rows of some titles.
 *
 * @param titles The titles ticked.
 * @returns The selection, keyed by each medium's identity.
 */
export function librarySelection(titles: string[]): Map<string, Doomed> {
  const seeded: { title: string; kind?: string; ids?: unknown }[] = [...LIBRARY, ...INCOMPLETE, ...RECENT];
  const selection = new Map<string, Doomed>();
  for (const title of titles) {
    const row = seeded.find((one) => one.title === title);
    const ref = mediaRefOf(row?.ids as Record<string, string | number> | undefined, row?.kind);
    if (ref !== null) selection.set(refKey(ref), { title, ref });
  }
  return selection;
}
