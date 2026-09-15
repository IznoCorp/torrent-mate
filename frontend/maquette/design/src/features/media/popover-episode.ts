// WHAT THE EPISODE POPOVER SAYS — the sentence, and only the sentence.
//
// THE FRAME PLACES, THE FEATURE SAYS (`frame-model.md` Part 12). The layer, its
// anchoring against the phone frame, its dismissal and its stacking are
// `app/popover-host.ts`'s and are NOT touched here: they went with the frame,
// behind `{ anchor, content }`. What was left in the engine is the five
// lines that turn an episode into three facts, and a producer moves to its
// feature.
//
// IT LIVES WITH MEDIA because what an episode IS — its number, its title, when
// it aired and whether it is held — is the media domain's, and it is the
// feature that draws the cell the reader tapped
// (`features/media/panel-seasons.tsx`).
import i18next from "i18next";
import { heldIdentity, providerAddress } from "../../lib/held-identity";
import { sharedQueryClient } from "../../lib/query-client";
import { dateLabel, episodeStateLabel } from "./format";

/** One episode of a season's catalogue, as the served sheet answers it. */
type Episode = { n: number; t?: string; air?: string | null };

/**
 * The episode catalogue of the medium drawn under one title, from the cache.
 *
 * THE CELL WAS DRAWN FROM A SHEET THAT LANDED — the screen's, or the panel's —
 * so the cache holds it: the title gives the medium's identity, and the identity
 * finds the sheet whichever provider its address was read under.
 *
 * @param title The title the cell was drawn under.
 * @returns The catalogue, season by season, or undefined.
 */
function catalogueOf(title: string): Record<string, Episode[]> | undefined {
  const wanted = providerAddress(heldIdentity(title)?.ids);
  if (wanted === null || sharedQueryClient === undefined) return undefined;
  for (const query of sharedQueryClient.getQueryCache().getAll()) {
    const [address, , , part] = query.queryKey as unknown[];
    if (address !== "/api/media" || part !== undefined) continue;
    const sheet = query.state.data as { ids?: Record<string, number | string>; eps?: Record<string, Episode[]> } | null | undefined;
    const held = providerAddress(sheet?.ids);
    if (sheet?.eps && held?.provider === wanted.provider && held.id === wanted.id) return sheet.eps;
  }
  return undefined;
}

/**
 * Builds what the popover says about one episode.
 *
 * THE SUBJECT IS THE CELL'S OWN `data-ep`, split as the markup writes it:
 * `title|season|episode|state`. Reading it here rather than being handed four
 * arguments keeps ONE spelling of that contract — the cell writes it, this
 * reads it, and a rule taps the cell.
 *
 * Args:
 *     cell: The episode button the reader tapped.
 *
 * Returns:
 *     The popover's content, or null when the cell carries no episode.
 */
export function episodeSaying(
  cell: HTMLElement,
): { title: string; text: string; note: string } | null {
  const written = cell.dataset.ep;
  if (written === undefined) return null;
  const [title, season, number, state] = written.split("|");
  const reference = window.__referentiel;
  const episode =
    catalogueOf(title)?.[season]?.find((one) => String(one.n) === number) ?? null;
  const airDate = episode?.air ? dateLabel(episode.air) : null;
  // ANNOUNCED IS EITHER OF TWO THINGS, and both are read: a date still ahead of
  // today, or a state the catalogue already calls announced. A rule that read
  // only the first would go green the day the fixture's dates fell behind.
  const ahead = Boolean(episode?.air && episode.air > reference.TODAY);
  const translate = i18next.t.bind(i18next);
  return {
    title:
      "S" + String(season).padStart(2, "0") +
      "E" + String(number).padStart(2, "0") +
      (episode?.t ? " · " + episode.t : ""),
    text:
      airDate == null
        ? translate("popover.airDateUnknown")
        : ahead || state === "announced"
          ? translate("popover.airsOn", { date: airDate })
          : translate("popover.airedOn", { date: airDate }),
    note: episodeStateLabel(state),
  };
}
