// A medium's card in the library — the list mode of the listing and of
// « Incomplets » — composed from the card's markup spelling.
//
// ONE CARD, ONE BEHAVIOUR (R41–R46): the poster opens the media sheet, the body
// opens the panel, and a title no sheet stands behind wears a folder instead.
// No handler is attached here; the document-level delegation reads the
// attributes.
import { icons } from "../../lib/shell-doors";
import i18next from "i18next";
import { posterArtwork } from "../../lib/engine-drawing";
import { cardMarkup } from "../../ui/card-markup";
import { posterArtworkMarkup } from "../../ui/poster";

/** A medium as a library list holds one, in the engine's field names. */
export type LibraryCard = {
  title: string;
  secondaryLine?: string;
  overview?: string | null;
  f?: string;
  chip?: { tone: string; text: string } | null;
  poster?: string | null;
  /** The provider identifiers — null for a title no sheet stands behind. */
  ids?: Record<string, number | string> | null;
};

/**
 * One medium's card.
 *
 * @param medium The medium, as the list holds it.
 * @returns The card's markup.
 */
export function libraryCardMarkup(medium: LibraryCard): string {
  const title = medium.title;
  const hasSheet = medium.ids != null;
  // french-ok: a panel ADDRESS and the non-medium marker, contract values the delegation and R46 read
  const folderAddress = `dossier:${title}`;
  return cardMarkup({
    title,
    // french-ok: the non-medium marker R46 reads, a contract value
    attributes: hasSheet ? {} : { "data-nonmedia": "dossier" },
    side: hasSheet
      ? {
          poster: posterArtworkMarkup(posterArtwork(icons, medium.poster, title)),
          attributes: { "aria-label": i18next.t("surfaces.card.sheetOf", { title }), "data-mediasheet": title },
        }
      : {
          folderIcon: icons.folder,
          folderLabel: i18next.t("surfaces.card.folder"),
          attributes: { "aria-label": i18next.t("surfaces.card.folderActions", { title }), "data-panel": folderAddress },
        },
    body: { "data-panel": hasSheet ? `media:${title}` : folderAddress },
    subtitle: medium.secondaryLine,
    overview: medium.overview ?? undefined,
    fraction: medium.f,
    chip: medium.chip ? { tone: medium.chip.tone, label: medium.chip.text } : null,
  });
}
