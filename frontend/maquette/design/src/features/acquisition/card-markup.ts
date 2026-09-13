// A medium's card on the acquisition surfaces — « En cours », « Suivis »,
// « Découvrir » and the add screen — composed from the card's markup spelling.
//
// ONE CARD, ONE BEHAVIOUR (R41–R46). The poster opens the media sheet; the body
// opens the panel. A title no sheet stands behind wears a FOLDER instead, which
// addresses the folder's own panel and nothing else, and the card says it is not
// a medium.
//
// NO HANDLER IS ATTACHED HERE. The document-level delegation answers
// `data-mediasheet`, `data-panel` and `data-act` on the button tapped, which is
// why every attribute below is one the delegation reads.
import i18next from "i18next";
import { initials } from "../../lib/titles";
import { cardMarkup } from "../../ui/card-markup";
import type { StripState } from "../../ui/card";
import { escapeMarkup } from "../../ui/markup";
import { posterArtworkMarkup } from "../../ui/poster";
import { posterFallback } from "../../ui/variants";
import { posterArtwork } from "../../lib/engine-drawing";
import { richTextMarkup } from "./rich-text";

/** A medium as an acquisition list holds one, in the engine's field names. */
export type MediumCard = {
  t: string;
  k?: string;
  s?: string;
  r?: unknown;
  f?: string;
  chip?: [string, string] | null;
  note?: number | string;
  caption?: string;
  fresh?: boolean;
  strip?: (number | string)[];
  noposter?: boolean;
  overview?: string;
  panel?: string;
  poster?: string | null;
  /** The provider identifiers — null for a title no sheet stands behind. */
  ids?: Record<string, number | string> | null;
};

/** The foot a section offers for its own action. */
export type MediumCardFoot = { label: string; act?: string; solid?: boolean };

/**
 * Where the journey stands at one stage, from the value the strip carries.
 *
 * @param value `1` for a stage passed, `"now"`, `"blocked"`, anything else for one not reached.
 * @returns The step's state.
 */
function stageState(value: number | string): StripState {
  if (value === 1) return "done";
  if (value === "now") return "now";
  if (value === "blocked") return "blocked";
  return "pending";
}

/**
 * One medium's card.
 *
 * TWO DIFFERENT ABSENCES, never merged: `noposter` says there is no artwork, a
 * missing identity says there is no medium — a list item carries provider ids
 * exactly when a sheet stands behind its title. A card with no artwork still has a
 * sheet, and still leads to it.
 *
 * @param medium The medium, as the list holds it.
 * @param foot The section's action, if it offers one.
 * @returns The card's markup.
 */
export function mediumCardMarkup(medium: MediumCard, foot?: MediumCardFoot): string {
  const reference = window.__referentiel;
  const title = medium.t;
  const hasSheet = medium.ids != null;
  // french-ok: a panel ADDRESS and the non-medium marker, contract values the delegation and R46 read
  const folderAddress = `dossier:${title}`;
  const artworkMarkup = medium.noposter
    ? `<span class="${posterFallback()}" data-part="card/poster-fallback"><b>${escapeMarkup(initials(title))}</b></span>`
    : posterArtworkMarkup(posterArtwork(reference.icons, medium.poster, title, medium.k));
  const stages = i18next.t("surfaces.card.stages", { returnObjects: true }) as string[];
  return cardMarkup({
    title,
    // french-ok: the non-medium marker R46 reads, a contract value
    attributes: hasSheet ? {} : { "data-nonmedia": "dossier" },
    side: hasSheet
      ? {
          poster: artworkMarkup,
          attributes: { "aria-label": i18next.t("surfaces.card.sheetOf", { title }), "data-mediasheet": title },
        }
      : {
          folderIcon: reference.icons.folder,
          folderLabel: i18next.t("surfaces.card.folder"),
          attributes: {
            "aria-label": i18next.t("surfaces.card.folderActions", { title }),
            "data-panel": medium.panel || folderAddress,
          },
        },
    body: { "data-panel": medium.panel || (hasSheet ? `media:${title}` : folderAddress) },
    subtitle: medium.s,
    reason: medium.r ? richTextMarkup(medium.r) : undefined,
    overview: medium.overview,
    fraction: medium.f,
    chip: medium.chip ? { tone: medium.chip[0], label: medium.chip[1] } : null,
    rating: medium.note != null ? String(medium.note) : undefined,
    caption: medium.caption,
    fresh: medium.fresh ? i18next.t("surfaces.card.freshTag") : undefined,
    strip: medium.strip?.map((value, index) => ({ state: stageState(value), label: stages[index] })),
    foot: foot ? { label: foot.label, solid: foot.solid, attributes: { "data-act": foot.act ?? "" } } : undefined,
  });
}
