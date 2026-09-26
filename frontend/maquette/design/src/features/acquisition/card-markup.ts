// A medium's card on the acquisition surfaces — « En cours », « Suivis »,
// « Découvrir » and the add screen — composed from the card's markup spelling.
//
// ONE CARD, ONE BEHAVIOUR (R41–R46). The poster opens the media sheet; the body
// opens the panel. A title no sheet stands behind wears a FOLDER instead, which
// addresses the folder's own panel and nothing else, and the card says it is not
// a medium.
//
// NO HANDLER IS ATTACHED HERE. The document-level delegation answers
// `data-mediasheet` and `data-panel` on the button tapped, which is
// why every attribute below is one the delegation reads.
import { icons } from "../../lib/shell-doors";
import i18next from "i18next";
import { initials } from "../../lib/titles";
import { cardMarkup } from "../../ui/card-markup";
import type { StripCell, StripState } from "../../ui/card";
import { escapeMarkup } from "../../ui/markup";
import { posterArtworkMarkup } from "../../ui/poster";
import { posterFallback } from "../../ui/variants";
import { posterArtwork } from "../../lib/engine-drawing";
import { richTextMarkup } from "./rich-text";

/** A medium as an acquisition list holds one, in the engine's field names. */
export type MediumCard = {
  title: string;
  k?: string;
  secondaryLine?: string;
  reason?: unknown;
  f?: string;
  chip?: { tone: string; text: string } | null;
  note?: number | string;
  caption?: string;
  fresh?: boolean;
  strip?: (number | string)[];
  /** The match Plex made, when it waits for the operator's confirmation. */
  plexMatch?: { title: string };
  /** Who asked for it, and where: a follow of theirs, or a direct add. */
  requester?: { name: string; via: string };
  /** The medium's ladder — the same list its journey sheet reads. */
  ladder?: { rung: string; state: StripState; reason?: string }[];
  withoutPoster?: boolean;
  overview?: string;
  panel?: string;
  poster?: string | null;
  /** The provider identifiers — null for a title no sheet stands behind. */
  ids?: Record<string, number | string> | null;
};

/** The foot a section offers for its own action. */
export type MediumCardFoot = { label: string; solid?: boolean; attributes?: Record<string, string> };

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
 * The tone a rung's name is drawn in, by the rung's state. A rung that WAITS
 * reads neutral: the waiting tone as a chip's words does not hold its contrast
 * on the light theme, and the rung's name says the wait itself.
 */
const RUNG_TONE: Record<StripState, string> = {
  done: "success",
  now: "info",
  waiting: "neutral",
  blocked: "danger",
  aside: "neutral",
  pending: "neutral",
};

/**
 * Where a card stands on its ladder: the strip's cells, unlabelled, and the
 * current rung — the first not passed, or the last when every one is — named in
 * words after its figure, on the line where it has the full width (§12).
 *
 * @param ladder The medium's rungs.
 * @returns The strip, the figure and the current rung's chip.
 */
function ladderMarkup(ladder: { rung: string; state: StripState; reason?: string }[]) {
  const standing = ladder.findIndex((rung) => rung.state !== "done");
  const current = standing === -1 ? ladder.length - 1 : standing;
  const strip: StripCell[] = ladder.map((rung) => ({ state: rung.state }));
  const reason = ladder[current].reason;
  return {
    strip,
    // THE REASON THE LADDER KNOWS, said in words, for a card whose row carries none.
    reason: reason === undefined ? undefined : i18next.t(`surfaces.ladder.reasons.${reason}`),
    fraction: i18next.t("surfaces.ladder.figure", { position: current + 1, count: ladder.length }),
    chip: {
      tone: RUNG_TONE[ladder[current].state],
      label: i18next.t(`surfaces.ladder.rungs.${ladder[current].rung}`),
    },
  };
}

/**
 * One medium's card.
 *
 * TWO DIFFERENT ABSENCES, never merged: `withoutPoster` says there is no artwork, a
 * missing identity says there is no medium — a list item carries provider ids
 * exactly when a sheet stands behind its title. A card with no artwork still has a
 * sheet, and still leads to it.
 *
 * @param medium The medium, as the list holds it.
 * @param foot The section's action, if it offers one.
 * @returns The card's markup.
 */
export function mediumCardMarkup(medium: MediumCard, foot?: MediumCardFoot | MediumCardFoot[]): string {
  const title = medium.title;
  const hasSheet = medium.ids != null;
  // french-ok: a panel ADDRESS and the non-medium marker, contract values the delegation and R46 read
  const folderAddress = `dossier:${title}`;
  const artworkMarkup = medium.withoutPoster
    ? `<span class="${posterFallback()}" data-part="card/poster-fallback"><b>${escapeMarkup(initials(title))}</b></span>`
    : posterArtworkMarkup(posterArtwork(icons, medium.poster, title, medium.k));
  const stages = i18next.t("surfaces.card.stages", { returnObjects: true }) as string[];
  const onLadder = medium.ladder ? ladderMarkup(medium.ladder) : null;
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
          folderIcon: icons.folder,
          folderLabel: i18next.t("surfaces.card.folder"),
          attributes: {
            "aria-label": i18next.t("surfaces.card.folderActions", { title }),
            "data-panel": medium.panel || folderAddress,
          },
        },
    body: { "data-panel": medium.panel || (hasSheet ? `media:${title}` : folderAddress) },
    subtitle: medium.secondaryLine,
    reason: medium.plexMatch
      ? escapeMarkup(i18next.t("surfaces.card.plexMatch", { title: medium.plexMatch.title }))
      : medium.reason
      ? richTextMarkup(medium.reason)
      : onLadder?.reason ? escapeMarkup(onLadder.reason) : undefined,
    overview: medium.overview,
    fraction: onLadder ? onLadder.fraction : medium.f,
    chip: onLadder ? onLadder.chip : medium.chip ? { tone: medium.chip.tone, label: medium.chip.text } : null,
    rating: medium.note != null ? String(medium.note) : undefined,
    caption: medium.caption,
    fresh: medium.fresh ? i18next.t("surfaces.card.freshTag") : undefined,
    // THE LINE IS COMPOSED FROM THE ANSWER — its name and where the asking
    // happened — never from a constant (§13).
    requester: medium.requester
      ? i18next.t(`surfaces.card.requester.${medium.requester.via}`, { name: medium.requester.name })
      : undefined,
    strip: onLadder ? onLadder.strip : medium.strip?.map((value, index) => ({ state: stageState(value), label: stages[index] })),
    foot: foot === undefined
      ? undefined
      : (Array.isArray(foot) ? foot : [foot]).map((one) => ({ label: one.label, solid: one.solid, attributes: one.attributes ?? {} })),
  });
}
