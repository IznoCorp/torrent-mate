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
import { acquisitionKey } from "../../lib/arrival-slots";
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
import { sizeOf } from "../trackers/format";
import type { Right, Rights } from "../../lib/rights";
import { CLOSED_TONE, closureMarkup } from "./closure-markup";


/** One rung of a card's ladder, as the card reads it. */
type Rung = {
  rung: string;
  state: StripState;
  reason?: string;
  when?: string;
  /** For a ratio deferral, the tracker it is under, and that tracker's own threshold. */
  tracker?: string | null;
  minimumRatio?: number | null;
  /** For an unreachable provider, its name; for a full library, the bytes needed. */
  provider?: string | null;
  size?: number | null;
  /** Who lifts a stopped rung: the engine (`auto`) or his hand — the engine's word (BK1). */
  resumes?: "auto" | "hand" | null;
};
/** A medium as an acquisition list holds one, in the engine's field names. */
// The contract's token for an acquisition the engine launched on its own.
const AUTOMATIC = "automatic";

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
  /** EVERY account that asked for it (round 9 Q16) — the line names them all. */
  requesters?: { id: string; name: string }[];
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
  /** The season and the episode the acquisition is of, as the engine serves them. */
  season?: number | null;
  episode?: number | null;
  /** Who launched it: a person's ask, or the engine's own rule — null when not known. */
  trigger?: "manual" | "automatic" | null;
  /** The pipeline step a tunnel error stopped on. */
  failedStep?: string;
  /** The tunnel's closure, until the account has seen it (Q8, Q9). */
  closure?: { reason: string; at: number; winner: string | null } | null;
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
// The engine's token for a ratio deferral.
const RATIO_DEFERRAL = "ratio_below_threshold";
// Where a door lands: the Trackers page, its « Trackers » tab, the tracker named
// after the separator; Système, the section named by the dial.
const TRACKERS_PAGE = "trackers";
const TRACKERS_TAB = "trackers";
const DIAL_SEPARATOR = ":";
const SYSTEM_PAGE = "sys";

/** A door: its words, the right that opens the page it lands on, where it lands. */
type Door = { label: string; right: Right; attributes: (rung: Rung) => Record<string, string> | undefined };

// To the tracker the block names, its panel up — none where the rung names none.
const TRACKER_DOOR: Door = {
  label: "screens.acquisition.ratioReasonTracker",
  right: "trackers.view",
  attributes: (rung) => rung.tracker
    ? { "data-go": TRACKERS_PAGE, "data-dial": `${TRACKERS_TAB}${DIAL_SEPARATOR}${rung.tracker}` }
    : undefined,
};
// To Système, one of its sections in view.
const systemDoor = (label: string, section: string): Door => ({
  label,
  right: "system.view",
  attributes: () => ({ "data-go": SYSTEM_PAGE, "data-dial": section }),
});
const DISKS_DOOR = systemDoor("screens.acquisition.blockDisks", "disks");
const DEPENDENCIES_DOOR = systemDoor("screens.acquisition.blockDependencies", "dependencies");

/**
 * WHERE EACH EXTERNAL CAUSE IS SETTLED (Q7, « où elle se règle »;
 * maquette-blocked § 1.3): one table, cause token → door. The ratio's door,
 * generalised to every cause the engine lifts on its own.
 */
const DOORS: Readonly<Record<string, Door>> = {
  ratio_below_threshold: TRACKER_DOOR,
  tracker_unreachable: TRACKER_DOOR,
  insufficient_space: DISKS_DOOR,
  content_missing: DISKS_DOOR,
  library_full: DISKS_DOOR,
  provider_unreachable: DEPENDENCIES_DOOR,
  plex_unreachable: DEPENDENCIES_DOOR,
  client_unreachable: DEPENDENCIES_DOOR,
};

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
 * The door of a card stopped by an external cause: the card's foot ALONE
 * (DECIDED 6), a link to where the cause is settled. A link, not an act: it is
 * drawn when the account may open the page it lands on, and only then (§ 17) —
 * the cause and the lift are drawn either way.
 *
 * @param medium The card's row.
 * @param rights What the account may do.
 * @returns The door, or undefined for a card no external cause stops.
 */
export function blockDoor(medium: Pick<MediumCard, "ladder">, rights: Rights): MediumCardFoot | undefined {
  if (!medium.ladder || medium.ladder.length === 0) return undefined;
  const rung = medium.ladder[currentRung(medium.ladder)];
  const door = rung.resumes === "auto" ? DOORS[rung.reason ?? ""] : undefined;
  const attributes = door?.attributes(rung);
  if (door === undefined || attributes === undefined || !rights.holds(door.right)) return undefined;
  return { label: i18next.t(door.label), attributes };
}

/**
 * What a stopped rung says (Q7, « chaque carte dit sa cause, ce qui la lève »):
 * its cause, then — for a block the ENGINE lifts on its own — what lifts it.
 *
 * @param rung The rung the card stands on, its reason set.
 * @returns The sentence, or the two.
 */
function causeSentence(rung: Rung): string {
  const reason = rung.reason ?? "";
  const unset = reason === RATIO_DEFERRAL && rung.minimumRatio == null;
  const values = {
    tracker: rung.tracker ?? "",
    provider: rung.provider ?? "",
    size: rung.size == null ? "" : sizeOf(rung.size),
    minimum: new Intl.NumberFormat(i18next.language).format(rung.minimumRatio ?? 0),
  };
  // A TRACKER WITH NO THRESHOLD OF ITS OWN is said to have none — never an
  // invented « 0 ».
  const cause = unset
    ? i18next.t("surfaces.ladder.ratioWithoutThreshold", values)
    : i18next.t(`surfaces.ladder.reasons.${reason}`, values);
  if (rung.resumes !== "auto") return cause;
  const resume = unset ? "surfaces.ladder.liftWithoutThreshold" : `surfaces.ladder.lifts.${reason}`;
  return i18next.exists(resume) ? `${cause} ${i18next.t(resume, values)}` : cause;
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
    // A TRACKER WITH NO THRESHOLD OF ITS OWN is said to have none — never an
    // invented « 0 ».
    reason: reason === undefined ? undefined : causeSentence(ladder[current]),
    fraction: i18next.t("surfaces.ladder.figure", { position: current + 1, count: ladder.length }),
    chip: {
      tone: reason === TO_CONFIRM ? RUNG_TONE.waiting : RUNG_TONE[ladder[current].state],
      label: reason === TO_CONFIRM ? i18next.t("surfaces.ladder.toConfirm", { rung: name }) : name,
    },
  };
}

// How a card several accounts asked for says it — the follow's own words.
const ASKED = "follow";

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
export function originLine(
  medium: Pick<MediumCard, "requester" | "requesters" | "ladder" | "droppedByHand">,
): string | undefined {
  // PLURAL WHERE SEVERAL ASKED (round 9 Q16): « demandé par izno et Léa ». The
  // names are joined by the language's own list, never by a typed conjunction.
  // THE REQUESTERS ARE WHO ASKED, whenever the answer carries them: a card
  // reassigned to one other account names that account, never the name the
  // row's origin was first recorded under (the reader's L18 round).
  const names = medium.requesters && medium.requesters.length > 0
    ? new Intl.ListFormat(i18next.language, { type: "conjunction" }).format(medium.requesters.map((one) => one.name))
    : medium.requester?.name;
  // A CARD SEVERAL ACCOUNTS ASKED FOR says so even where the answer names no
  // single asking: they asked for it, and « demandé par » is what they did.
  const via = medium.requester?.via ?? (medium.requesters && medium.requesters.length > 1 ? ASKED : undefined);
  if (via)
    return i18next.t(`surfaces.card.requester.${via}`, { name: names });
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
  const footOptions = foot === undefined ? [] : Array.isArray(foot) ? foot : [foot];
  return cardMarkup({
    title,
    // french-ok: the non-medium marker R46 reads, a contract value
    // THE ACQUISITION IT STANDS FOR, the key a landing names it by (DESIGN
    // maquette-season-recovery § 1.4: « Voir la carte de la saison »).
    attributes: { "data-acquisition": acquisitionKey(medium), ...(hasSheet ? {} : { "data-nonmedia": "dossier" }) },
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
    // AN AUTOMATIC RECOVERY SAYS SO in its subtitle, « S03 · auto » (Q19,
    // DECIDED 8 = A): a word, never a second chip beside the rung's. A manual
    // one reads nothing more; an unknown trigger draws nothing, never a guess.
    subtitle: medium.trigger === AUTOMATIC
      ? i18next.t("surfaces.card.automatic", { line: medium.secondaryLine })
      : medium.secondaryLine,
    // A CLOSED TUNNEL SAYS WHY, once (Q8, Q9): it outranks what its ladder
    // said when it was still running.
    reason: medium.closure
      ? closureMarkup(medium.closure)
      : medium.plexMatch
      ? escapeMarkup(i18next.t("surfaces.card.plexMatch", { title: medium.plexMatch.title }))
      : onLadder?.setAside
      ? escapeMarkup(onLadder.setAside)
      : medium.reason
      ? richTextMarkup(medium.reason)
      : onLadder?.reason ? escapeMarkup(onLadder.reason)
      // A STEP THAT FAILED WITH NO SENTENCE says which step (B-671): a card of
      // « À traiter » always says its cause, never nothing.
      : medium.failedStep ? escapeMarkup(i18next.t("surfaces.card.failedStep", {
        step: i18next.t(`screens.run.step.${medium.failedStep}`) }))
      : undefined,
    overview: medium.overview,
    fraction: onLadder ? onLadder.fraction : medium.f,
    // « CLOS », in the neutral tone: nothing runs, nothing waits on him.
    chip: medium.closure ? { tone: CLOSED_TONE, label: i18next.t("surfaces.ladder.closed") }
      : onLadder ? onLadder.chip : medium.chip ? { tone: medium.chip.tone, label: medium.chip.text } : null,
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
