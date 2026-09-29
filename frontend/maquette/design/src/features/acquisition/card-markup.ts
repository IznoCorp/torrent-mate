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
import { originRow, footRow } from "./variants";
import { currentRung } from "../../lib/current-rung";


/** One rung of a card's ladder, as the card reads it. */
type Rung = {
  rung: string;
  state: StripState;
  reason?: string;
  when?: string;
  /** For a ratio deferral, the tracker it is under, and that tracker's own threshold. */
  tracker?: string | null;
  minimumRatio?: number | null;
};
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
  /** Put in the staging area by hand: nobody asked, and its subtitle says so. */
  droppedByHand?: boolean;
  /** The medium's ladder — the same list its journey sheet reads. */
  ladder?: Rung[];
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
  skipped: "neutral",
  pending: "neutral",
};

// The reason a rung waits for the operator's answer rather than for his hand.
const TO_CONFIRM = "confirmation";
// The engine's token for a ratio deferral, and where its path lands: the
// Trackers page, its « Trackers » tab, the tracker named after the separator.
const RATIO_DEFERRAL = "ratio_below_threshold";
const TRACKERS_PAGE = "trackers";
const TRACKERS_TAB = "trackers";
const DIAL_SEPARATOR = ":";

/**
 * A date, as a sentence says it: the day and the month.
 *
 * @param date The date, `YYYY-MM-DD`.
 * @returns The day in the interface's language, or the date as given when it is not one.
 */
function dayOf(date: string): string {
  const parsed = new Date(date);
  if (Number.isNaN(parsed.getTime())) return date;
  // In UTC, the zone a bare date is read in, so the day never slips by one.
  return new Intl.DateTimeFormat(i18next.language, { day: "numeric", month: "long", timeZone: "UTC" }).format(parsed);
}

/**
 * Where a card stands on its ladder: the strip's cells, unlabelled, and the
 * current rung named in words after its figure, on the line where it has the
 * full width (§12).
 *
 * A RUNG WAITING ON HIS ANSWER is not drawn done: its word says it waits for
 * him, in the waiting tone.
 *
 * @param ladder The medium's rungs.
 * @returns The strip, the figure and the current rung's chip.
 */
/**
 * The tracker a ratio deferral is under, when the rung the card stands on is one.
 *
 * @param ladder The medium's rungs.
 * @returns The tracker's name, or undefined for any other rung.
 */
function ratioDeferralTracker(ladder: Rung[]): string | undefined {
  const rung = ladder[currentRung(ladder)];
  return rung.reason === RATIO_DEFERRAL && rung.tracker ? rung.tracker : undefined;
}

function ladderMarkup(ladder: Rung[]) {
  const current = currentRung(ladder);
  const strip: StripCell[] = ladder.map((rung) => ({ state: rung.state }));
  const reason = ladder[current].reason;
  const setAside = ladder[current].state === "aside";
  const name = i18next.t(`surfaces.ladder.rungs.${ladder[current].rung}`);
  return {
    strip,
    // WHO SET IT ASIDE, AND WHEN, composed from the date the rung carries —
    // never a constant (§13). It outranks the row's own reason: the folder is
    // waiting for him now, not for the step that stopped it.
    setAside: setAside ? i18next.t("surfaces.ladder.setAside", { day: dayOf(ladder[current].when ?? "") }) : undefined,
    // THE REASON THE LADDER KNOWS, said in words, for a card whose row carries none
    // — a ratio deferral naming its tracker and THAT tracker's own threshold.
    reason: reason === undefined ? undefined : i18next.t(`surfaces.ladder.reasons.${reason}`, {
      tracker: ladder[current].tracker ?? "",
      minimum: new Intl.NumberFormat(i18next.language).format(ladder[current].minimumRatio ?? 0),
    }),
    fraction: i18next.t("surfaces.ladder.figure", { position: current + 1, count: ladder.length }),
    chip: {
      tone: reason === TO_CONFIRM ? RUNG_TONE.waiting : RUNG_TONE[ladder[current].state],
      label: reason === TO_CONFIRM ? i18next.t("surfaces.ladder.toConfirm", { rung: name }) : name,
    },
  };
}

/**
 * The line saying where an acquisition came from — ONE composition, read by its
 * card and by its panel, which carries it whole where the card truncates it.
 *
 * FROM THE ANSWER: its requester's name and where the asking happened. An
 * acquisition whose origin is not known says so, never nothing; a folder
 * dropped by hand asked nobody, and its subtitle already says it was.
 *
 * @param medium The card's row.
 * @returns The line, or undefined where the card draws none.
 */
export function originLine(medium: Pick<MediumCard, "requester" | "ladder" | "droppedByHand">): string | undefined {
  if (medium.requester)
    return i18next.t(`surfaces.card.requester.${medium.requester.via}`, { name: medium.requester.name });
  return medium.ladder && !medium.droppedByHand ? i18next.t("surfaces.card.requester.unknown") : undefined;
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
  // A RATIO DEFERRAL IS A PATH to the tracker it is under: « Voir le tracker »
  // lands on the Trackers tab, that tracker's entry open. An ADDRESS the page
  // reads through its own landing door — never an import of that page's feature.
  const deferredOn = medium.ladder ? ratioDeferralTracker(medium.ladder) : undefined;
  const footOptions = [...(foot === undefined ? [] : Array.isArray(foot) ? foot : [foot]), ...(deferredOn === undefined ? [] : [{
    label: i18next.t("screens.acquisition.ratioReasonTracker"),
    attributes: { "data-go": TRACKERS_PAGE, "data-dial": `${TRACKERS_TAB}${DIAL_SEPARATOR}${deferredOn}` },
  }])];
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
      : onLadder?.setAside
      ? escapeMarkup(onLadder.setAside)
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
    requester: originLine(medium),
    strip: onLadder ? onLadder.strip : medium.strip?.map((value, index) => ({ state: stageState(value), label: stages[index] })),
    foot: footOptions.length === 0
      ? undefined
      : footOptions.map((one: MediumCardFoot) => ({ label: one.label, solid: one.solid, attributes: one.attributes ?? {} })),
     footRow: footRow(),
     originRow: originRow(),
  });
}
