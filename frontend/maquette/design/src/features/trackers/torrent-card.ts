// A torrent's card: one entry of the download client, drawn as a media card.
//
// THE MEDIA CARD'S OWN ANATOMY AND TAPS (§ 12, one card, one behaviour): the
// poster opens the medium's sheet, the body opens the torrent's bottom panel,
// and an entry no medium is linked to wears the folder, which opens the panel
// too. The name is said WHOLE on the first line — a release name has no space to
// break at, and half of one is a riddle — so the medium's title is left to the
// poster, which carries it.
//
// WHAT THE ENTRY SAYS OF ITS TRANSFER is one of three states (the operator's Q1):
// its volumes by default, a bar and the download rate while it downloads, the
// upload rate alone while it sends. A figure the client does not give is said
// unknown, never drawn as zero.
import i18next from "i18next";
import { icons } from "../../lib/shell-doors";
import { posterArtwork } from "../../lib/engine-drawing";
import { cardMarkup, type CardMark } from "../../ui/card-markup";
import { posterArtworkMarkup } from "../../ui/poster";
import { swipeRowMarkup } from "../../ui/rows";
import { escapeMarkup } from "../../ui/markup";
import { svgIcon } from "../../lib/markup-text";
import type { LegendEntry } from "../../ui/legend";
import { swipeAction, type ChipTone, type LegendTone } from "../../ui/variants";
import { dayOf, rateOf, sizeOf, written } from "./format";
import type { Download, Obligation } from "./queries";
import { isSearchable } from "./cross-seed-state";

/** The tone each of the client's states wears — the legend reads the same map. */
export const STATE_TONE: Readonly<Record<Download["state"], ChipTone>> = {
  downloading: "info",
  seeding: "success",
  stalled: "warning",
  errored: "danger",
  missing: "danger",
  paused: "neutral",
  queued: "neutral",
  in_client: "neutral",
};

/** The tone of the origin dot: the original grab, or a cross-seed of the same files. */
export const ORIGIN_TONE = { origin: "info", cross: "waiting" } as const;

/** One colour code a card draws: a chip or a dot, its tone, and what it means. */
export type Code = { kind: "chip" | "dot"; tone: LegendTone; word: string };

/** A mark, and — when its label carries a date — the word its legend entry says. */
type MarkWithWord = CardMark & { word?: string };

/** What an entry's transfer says: which of the three states, and its words. */
export type Transfer = { mode: "downloading" | "uploading" | "volumes"; text: string };

/**
 * The obligation one entry owes on its own tracker.
 *
 * @param entry The download client's entry.
 * @param obligations Every obligation.
 * @returns The obligation, or undefined when the entry owes none.
 */
export function owedBy(entry: Download, obligations: Obligation[]): Obligation | undefined {
  return obligations.find(
    (obligation) => obligation.infoHash === entry.infoHash && obligation.sourceTracker === entry.tracker,
  );
}

/**
 * The season and the episode an entry carries.
 *
 * @param entry The download client's entry.
 * @returns The episode's code, or an empty string for a movie.
 */
export function episodeCode(entry: Download): string {
  const twoDigits = (value: number) => String(value).padStart(2, "0");
  if (entry.season === null) return "";
  return entry.episode === null ? `S${twoDigits(entry.season)}` : `S${twoDigits(entry.season)}E${twoDigits(entry.episode)}`;
}

/**
 * What an entry's transfer says.
 *
 * @param entry The download client's entry.
 * @returns While it downloads, its download rate; while it sends, its upload
 *     rate; otherwise what it received and sent — each unknown said so.
 */
export function transferOf(entry: Download): Transfer {
  const say = (key: string, values: Record<string, string> = {}) => i18next.t(`screens.torrents.${key}`, values);
  if (entry.state === "downloading") {
    return {
      mode: "downloading",
      text: entry.downloadRate === null ? say("rateUnknown") : say("downloadRate", { rate: rateOf(entry.downloadRate) }),
    };
  }
  // SENDING IS A RATE ABOVE ZERO: a seed nobody asks for is at rest.
  if (entry.uploadRate !== null && entry.uploadRate > 0) {
    return { mode: "uploading", text: say("uploadRate", { rate: rateOf(entry.uploadRate) }) };
  }
  if (entry.downloadedBytes === null || entry.uploadedBytes === null) {
    return { mode: "volumes", text: say("volumesUnknown") };
  }
  return {
    mode: "volumes",
    text: say("volumes", { downloaded: sizeOf(entry.downloadedBytes), uploaded: sizeOf(entry.uploadedBytes) }),
  };
}

/**
 * The entry's popularity: the sources the swarm counts, or « unknown » — never 0,
 * which says a dead swarm.
 *
 * @param entry The download client's entry.
 * @returns The popularity in words.
 */
export function sourcesOf(entry: Download): string {
  return entry.swarmSeeds === null
    ? i18next.t("screens.torrents.sourcesUnknown")
    : i18next.t("screens.torrents.sources", { count: entry.swarmSeeds });
}

/**
 * The day the client added the entry, or « unknown ».
 *
 * @param entry The download client's entry.
 * @returns The date in words.
 */
export function addedOf(entry: Download): string {
  return entry.addedAt === null
    ? i18next.t("screens.torrents.addedUnknown")
    : i18next.t("screens.torrents.added", { date: dayOf(entry.addedAt) });
}

/**
 * The panel address of one entry: its hash and the tracker it runs on.
 *
 * @param entry The download client's entry.
 * @returns The address the body and the folder open.
 */
export function torrentPanelAddress(entry: Download): string {
  return `torrent:${entry.infoHash}:${entry.tracker}`;
}

/**
 * The marks an entry wears: its origin, its tracker, its obligation, its deadline.
 *
 * @param entry The download client's entry.
 * @param obligation The obligation it owes, when it owes one.
 * @param breached Whether the page's alert reads its obligation broken.
 * @returns The marks, in the order they are read.
 */
function marksOf(entry: Download, obligation: Obligation | undefined, breached: boolean): MarkWithWord[] {
  const say = (key: string, values: Record<string, string> = {}) => i18next.t(`screens.torrents.${key}`, values);
  // RUNNING: nothing has closed it — neither met, nor broken, nor released.
  const running = obligation !== undefined
    && obligation.satisfiedAt === null && obligation.breachedAt === null && obligation.releasedAt === null;
  // MET AND STILL SEEDING: the entry kept going past its own requirement.
  const done = obligation !== undefined && obligation.satisfiedAt !== null && obligation.releasedAt === null;
  const origin = entry.origin ? "origin" : "cross";
  const marks: MarkWithWord[] = [
    {
      label: say(entry.origin ? "origin" : "crossSeed"),
      dot: ORIGIN_TONE[origin],
      attributes: { "data-part": "torrents/origin", "data-origin": origin },
    },
    { label: entry.tracker, attributes: { "data-part": "torrents/tracker" } },
  ];
  if (running) {
    marks.push({ label: say("obligationOpen"), tone: "info", attributes: { "data-part": "torrents/obligation-open" } });
  }
  // AN OBLIGATION A CROSS-SEED CREATED says whose copy it is (§ 19 point 2) — one that
  // is not reads as it did, no mark and no empty slot.
  if (obligation?.crossSeedOf) {
    marks.push({
      label: say("crossSeedOf", { title: obligation.crossSeedOf.title }),
      attributes: { "data-part": "torrents/obligation-origin", "data-origin-entry": obligation.crossSeedOf.infoHash },
    });
  }
  // AN ORIGIN SAYS WHERE IT CROSS-SEEDS, as the server counts its pairs; its panel says each one.
  if (entry.crossSeed !== null && entry.crossSeed.pairs.length > 0) {
    const active = entry.crossSeed.pairs.filter((pair) => pair.state === "active").length;
    marks.push({
      label: active === 0 ? say("crossSeedNone") : i18next.t("screens.torrents.crossSeedActive", { count: active }),
      attributes: { "data-part": "torrents/cross-seed-summary", "data-active": String(active) },
    });
  }
  // BROKEN, THE TORRENT STILL HERE: the alert's own reading, never recomputed on
  // the card — « en infraction », never « rompue », which names the torrent gone.
  if (breached) {
    marks.push({
      label: say("obligationBreached", { date: obligation?.breachedAt ? dayOf(obligation.breachedAt) : "" }),
      word: say("legendBreached"),
      tone: "danger",
      attributes: { "data-part": "torrents/obligation-breached" },
    });
  }
  if (done) {
    marks.push({ label: say("obligationDone"), tone: "success", attributes: { "data-part": "torrents/obligation-done" } });
  }
  marks.push({
    label: entry.deadline === null ? say("noDeadline") : say("deadline", { date: dayOf(entry.deadline) }),
    attributes: { "data-part": "torrents/deadline" },
  });
  return marks;
}

/**
 * The colour codes one entry's card draws — the card and the legend read this
 * one derivation, so a colour drawn without its legend entry cannot happen.
 *
 * @param entry The download client's entry.
 * @param obligation The obligation it owes, when it owes one.
 * @param breached Whether the page's alert reads its obligation broken.
 * @returns The codes, the state's chip first.
 */
export function codesOf(entry: Download, obligation: Obligation | undefined, breached: boolean): Code[] {
  const state: Code = {
    kind: "chip", tone: STATE_TONE[entry.state], word: i18next.t(`screens.torrents.states.${entry.state}`),
  };
  return [state, ...marksOf(entry, obligation, breached).flatMap((mark): Code[] =>
    mark.dot !== undefined ? [{ kind: "dot", tone: mark.dot as LegendTone, word: mark.word ?? mark.label }]
      : mark.tone !== undefined ? [{ kind: "chip", tone: mark.tone as LegendTone, word: mark.word ?? mark.label }]
        : [])];
}

/**
 * A legend's entries for the codes a list draws: one per TONE, in the order
 * first drawn, saying every meaning that colour carries there — a dot and a chip
 * of one colour are one swatch, never two a reader must tell apart.
 *
 * @param codes Every code the list draws.
 * @returns The entries.
 */
export function legendOf(codes: readonly Code[]): LegendEntry[] {
  const entries = new Map<string, { tone: LegendTone; words: string[] }>();
  for (const code of codes) {
    const key = code.tone;
    const entry = entries.get(key) ?? { tone: code.tone, words: [] };
    if (!entry.words.includes(code.word)) entry.words.push(code.word);
    entries.set(key, entry);
  }
  return [...entries].map(([key, entry]) => ({ key, tone: entry.tone, label: entry.words.join(" · ") }));
}

/**
 * One entry's card, in its swipe row, in the row that names the entry.
 *
 * TRAVEL LEFT UNCOVERS « Retirer », and its tap is the panel's own removal: it
 * opens the confirmation, never removes by itself. TRAVEL RIGHT uncovers
 * « Chercher », a cross-seed search, on an origin with a pair to search.
 *
 * @param entry The download client's entry.
 * @param obligation The obligation it owes, when it owes one.
 * @param breached Whether the page's alert reads its obligation broken.
 * @returns The item's markup.
 */
export function torrentItemMarkup(entry: Download, obligation: Obligation | undefined, breached: boolean): string {
  const say = (key: string, values: Record<string, string> = {}) => i18next.t(`screens.torrents.${key}`, values);
  const panelAddress = torrentPanelAddress(entry);
  const transfer = transferOf(entry);
  const linked = entry.ids !== null;
  const card = cardMarkup({
    title: entry.name,
    // french-ok: the non-medium marker the card contract reads, a contract value
    attributes: linked ? {} : { "data-nonmedia": "dossier" },
    side: linked
      ? {
          poster: posterArtworkMarkup(posterArtwork(icons, entry.poster, entry.title, entry.kind)),
          attributes: { "aria-label": i18next.t("surfaces.card.sheetOf", { title: entry.title }), "data-mediasheet": entry.title },
        }
      : {
          folderIcon: icons.folder,
          folderLabel: i18next.t("surfaces.card.folder"),
          attributes: { "aria-label": i18next.t("surfaces.card.folderActions", { title: entry.name }), "data-panel": panelAddress },
        },
    body: { "data-panel": panelAddress },
    chip: { tone: STATE_TONE[entry.state], label: say(`states.${entry.state}`) },
    details: [
      { label: sizeOf(entry.sizeBytes), attributes: { "data-part": "torrents/size" } },
      {
        label: i18next.t("screens.trackers.ratio", { ratio: written(entry.ratio, 2) }),
        attributes: { "data-part": "torrents/ratio" },
      },
    ],
    progress: transfer.mode === "downloading"
      ? { value: entry.progress, label: say("progress", { percent: written(entry.progress * 100, 0) }) }
      : undefined,
    notes: [
      // WHY THE CLIENT REFUSES IT, in the client's own words, before anything else.
      ...(entry.errorReason === null ? [] : [{ label: entry.errorReason, attributes: { "data-part": "torrents/error" } }]),
      { label: transfer.text, attributes: { "data-part": "torrents/transfer", "data-transfer": transfer.mode } },
      { label: sourcesOf(entry), attributes: { "data-part": "torrents/sources" } },
      { label: addedOf(entry), attributes: { "data-part": "torrents/added" } },
    ],
    marks: marksOf(entry, obligation, breached),
  });
  const remove = `<button class="${swipeAction({ tone: "remove" })}" data-part="swipe/action" data-action="remove" data-swipeact="remove" data-torrent-remove="${escapeMarkup(`${entry.infoHash}:${entry.tracker}`)}">${svgIcon(icons.trash)}${escapeMarkup(say("swipeRemove"))}</button>`;
  // THE LEFT DRAWER IS THE ROW'S ONE « FOR » ACTION (L16-bis § 1.6): a cross-seed
  // search on an origin, over every pair the engine would act on — drawn only
  // when there is one; nothing is drawn that does nothing.
  const searchable = entry.crossSeed !== null
    && entry.crossSeed.pairs.some((pair) => isSearchable(pair, entry.crossSeed?.titleExcluded ?? false));
  const search = searchable
    ? `<button class="${swipeAction({ tone: "resume" })}" data-part="swipe/action" data-action="cross-seed-search" data-swipeact="cross-seed-search" data-cross-seed-search-all="${escapeMarkup(entry.infoHash)}">${svgIcon(icons.search)}${escapeMarkup(say("swipeSearch"))}</button>`
    : undefined;
  return `<div data-part="torrents/row" data-entry="${escapeMarkup(entry.infoHash)}" data-tracker="${escapeMarkup(entry.tracker)}">${swipeRowMarkup(card, remove, search)}</div>`;
}
