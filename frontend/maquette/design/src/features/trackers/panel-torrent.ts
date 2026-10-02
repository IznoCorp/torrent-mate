// A torrent's panel — what a tap on a torrent card's body raises.
//
// THE PANEL'S GENERIC BLOCKS ONLY: the entry's facts, then its actions. Every
// fact is said, and said « inconnu » when the client does not give it — a blank
// would read as nothing to say. Its subject is the entry: its hash and the
// tracker it runs on, `<hash>:<tracker>`.
//
// ADDRESSED, `torrent:<hash>:<tracker>` — the push of an obligation met or
// released lands here (the operator, 2026-10-03). The address names the PAIR,
// never a position in the client's list, so it stays true as torrents come and
// go; and a torrent that has LEFT the client is still a subject while the engine
// holds its obligation: its panel then says it is gone and why, from the
// obligation alone — the message on the torrent, never a second « released » list.
import { accountQuery, heldRights } from "../../lib/account";
import i18next from "i18next";
import { icons } from "../../lib/shell-doors";
import type { Schemas } from "../../lib/contract-schemas";
import { registerProducer, type Action, type FactLine, type PanelCache, type PanelDescriptor } from "../../ui/panel/contract";
import { read } from "../../lib/query-client";
import { sizeOf, written } from "../../lib/byte-size";
import { dayOf } from "./format";
import { downloadsKey, obligationsKey, type Download, type Obligation } from "./queries";
import { ORIGIN_MARK, episodeCode, owedBy, sourcesOf, transferOf } from "./torrent-card";
import { isSeeding } from "./cross-seed-state";
import { messageOf } from "./obligation-outcome";
// The cross-seed block an origin's panel draws, declared to the panel as it evaluates.
import "./panel-cross-seed";
// The obligation's outcome, the message that leads the panel.
import "./panel-obligation-outcome";

/**
 * A sentence of the panel, in the interface's language.
 *
 * @param key The sentence's key under the panel's words.
 * @param values What it names.
 * @returns The sentence.
 */
function say(key: string, values: Record<string, string> = {}): string {
  return i18next.t(`screens.torrents.panel.${key}`, values);
}

/**
 * What an obligation says on the panel: running, met, broken, released, or none.
 *
 * @param obligation The obligation the entry owes, when it owes one.
 * @returns The obligation in words.
 */
function obligationOf(obligation: Obligation | undefined): string {
  if (obligation === undefined) return say("none");
  if (obligation.releasedAt !== null) return say("obligationReleased", { date: dayOf(obligation.releasedAt) });
  if (obligation.breachedAt !== null) return say("obligationBroken", { date: dayOf(obligation.breachedAt) });
  if (obligation.satisfiedAt !== null) return say("obligationMet", { date: dayOf(obligation.satisfiedAt) });
  return say("obligationRunning");
}

/**
 * The entry's facts, in the order the card reads them.
 *
 * @param entry The download client's entry.
 * @param obligation The obligation it owes, when it owes one.
 * @returns The facts, every absence said.
 */
export function factsOf(entry: Download, obligation: Obligation | undefined): FactLine[] {
  const code = episodeCode(entry);
  const medium = entry.ids === null ? say("unknown") : code === "" ? entry.title : `${entry.title} · ${code}`;
  const lines: FactLine[] = [
    { c: say("name"), v: entry.name },
    { c: say("medium"), v: medium },
    { c: say("tracker"), v: entry.tracker },
    { c: say("origin"), v: i18next.t(`screens.torrents.${ORIGIN_MARK[entry.provenance].word}`) },
    {
      c: say("state"),
      v: [i18next.t(`screens.torrents.states.${entry.state}`), entry.errorReason].filter(Boolean).join(" — "),
    },
    { c: say("size"), v: sizeOf(entry.sizeBytes) },
  ];
  if (entry.state === "downloading") {
    lines.push({ c: say("progress"), v: i18next.t("screens.torrents.progress", { percent: written(entry.progress * 100, 0) }) });
  }
  lines.push(
    { c: say("transfer"), v: transferOf(entry).text },
    { c: say("sources"), v: sourcesOf(entry) },
    // THE LABEL SAYS « AJOUTÉ LE », so the value is the day alone (B-614) — the card's sentence is the card's.
    { c: say("added"), v: entry.addedAt === null ? say("unknown") : dayOf(entry.addedAt) },
    { c: say("ratio"), v: written(entry.ratio, 2) },
    { c: say("obligation"), v: obligationOf(obligation) },
    ...(obligation?.crossSeedOf ? [{ c: say("crossSeedOf"), v: obligation.crossSeedOf.title }] : []),
    {
      c: say("deadline"),
      v: entry.deadline === null ? i18next.t("screens.torrents.noDeadline") : dayOf(entry.deadline),
    },
  );
  return lines;
}

/**
 * The panel of a torrent that has left the client: its obligation alone says it.
 *
 * @param obligation The obligation the pair owed.
 * @param subject The pair, `<hash>:<tracker>`.
 * @returns The descriptor: the outcome, the fact that it is gone, the obligation's own facts.
 */
function gonePanel(obligation: Obligation, subject: string): PanelDescriptor {
  const message = messageOf(obligation);
  return {
    address: `torrent:${subject}`,
    title: obligation.title ?? obligation.infoHash,
    meta: obligation.sourceTracker,
    blocs: [
      message === null ? null : { type: "obligationOutcome", message },
      { type: "note", text: say("gone") },
      {
        type: "faits",
        lignes: [
          { c: say("tracker"), v: obligation.sourceTracker },
          { c: say("added"), v: dayOf(obligation.addedAt) },
          { c: say("obligation"), v: obligationOf(obligation) },
        ],
      },
    ],
  };
}

/**
 * The client's entry and the obligation of one pair, as the cache holds them.
 *
 * @param subject The pair, `<hash>:<tracker>`.
 * @param cache What the query cache holds.
 * @returns The entry when the client still holds it, and the obligation the pair owes.
 */
function pairOf(subject: string, cache: PanelCache): { entry: Download | undefined; owed: Obligation | undefined } {
  const [infoHash, tracker] = subject.split(":");
  const downloads = cache.held<Schemas["Downloads"]>(downloadsKey)?.downloads;
  const entry = downloads?.find((one) => one.infoHash === infoHash && one.tracker === tracker);
  const obligations = cache.held<Schemas["Obligations"]>(obligationsKey)?.items ?? [];
  const owed = entry !== undefined
    ? owedBy(entry, obligations)
    : obligations.find((one) => one.infoHash === infoHash && one.sourceTracker === tracker);
  return { entry, owed };
}

/**
 * Builds a torrent's descriptor.
 *
 * @param subject The entry, `<hash>:<tracker>`.
 * @param cache What the query cache holds.
 * @returns The descriptor — the gone torrent's when the client no longer holds
 *     it but its obligation is known — or null while neither has landed.
 */
function torrentPanel(subject: string, cache: PanelCache): PanelDescriptor | null {
  const { entry, owed } = pairOf(subject, cache);
  if (entry === undefined) return owed === undefined ? null : gonePanel(owed, subject);
  // A LINKED ENTRY LEADS TO ITS MEDIUM'S SHEET; an unlinked one to its folder's
  // resolution, when the engine holds a folder for it — and says so when not.
  const path: Action | null = entry.ids !== null
    ? { text: say("seeSheet"), icone: icons.eye, target: { mediasheet: entry.title } }
    : entry.folder !== null
      ? { text: say("identify"), icone: icons.play, ton: "primary", target: { resolution: entry.folder } }
      : null;
  // A CROSS-SEED'S OBLIGATION SAYS WHOSE COPY IT IS, and leads to the original's sheet (S4).
  const origin = owed?.crossSeedOf ?? null;
  const toOrigin: Action | null = origin === null || origin.media === null
    ? null
    : { text: say("seeOrigin"), icone: icons.eye, target: { mediasheet: origin.title } };
  const message = messageOf(owed);
  return {
    address: `torrent:${subject}`,
    title: entry.title,
    meta: entry.tracker,
    blocs: [
      // THE OUTCOME LEADS: it is what the push sent the reader here to read.
      message === null ? null : { type: "obligationOutcome", message },
      { type: "faits", lignes: factsOf(entry, owed) },
      path === null ? { type: "note", text: say("noFolder") } : null,
      // AN ORIGIN'S CROSS-SEED, tracker by tracker — never repeated on a cross-seed's own entry.
      entry.crossSeed === null ? null : {
        type: "crossSeed",
        origin: {
          infoHash: entry.infoHash, name: entry.name, tracker: entry.tracker, progress: entry.progress,
          seeding: isSeeding(entry),
        },
        pairs: entry.crossSeed.pairs,
        titleExcluded: entry.crossSeed.titleExcluded,
      },
      {
        type: "actions",
        actions: [
          path,
          toOrigin,
          // REMOVING IS A WRITE (`trackers.control`), absent without it.
          !heldRights().holds("trackers.control") ? null : {
            text: i18next.t("screens.torrents.remove"),
            icone: icons.trash,
            ton: "danger",
            target: { "torrent-remove": `${entry.infoHash}:${entry.tracker}` },
          },
        ],
      },
    ],
  };
}

registerProducer("torrent", {
  produce: torrentPanel,
  // A FUNCTION, NOT A LIST: resolved when a panel is asked for, never prefilled at
  // boot — a boot-time read would answer before a named state poses its entries.
  needs: () => [
    accountQuery,
    { queryKey: downloadsKey, queryFn: async () => read<Schemas["Downloads"]>(downloadsKey[0]) },
    { queryKey: obligationsKey, queryFn: async () => read<Schemas["Obligations"]>(obligationsKey[0]) },
  ],
  // HELD while the client holds the entry OR the engine holds the pair's obligation.
  holds: (subject, cache) => {
    const { entry, owed } = pairOf(subject, cache);
    return entry !== undefined || owed !== undefined;
  },
});
