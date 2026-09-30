// A torrent's panel — what a tap on a torrent card's body raises.
//
// THE PANEL'S GENERIC BLOCKS ONLY: the entry's facts, then its actions. Every
// fact is said, and said « inconnu » when the client does not give it — a blank
// would read as nothing to say. Its subject is the entry: its hash and the
// tracker it runs on, `<hash>:<tracker>`.
//
// NO ADDRESS: the entry is a row of the client's list, which moves under the
// operator as torrents come and go; Back closes the panel all the same.
import i18next from "i18next";
import { icons } from "../../lib/shell-doors";
import type { Schemas } from "../../lib/contract-schemas";
import { registerProducer, type Action, type FactLine, type PanelCache, type PanelDescriptor } from "../../ui/panel/contract";
import { read } from "../../lib/query-client";
import { dayOf, sizeOf, written } from "./format";
import { downloadsKey, obligationsKey, type Download, type Obligation } from "./queries";
import { addedOf, episodeCode, owedBy, sourcesOf, transferOf } from "./torrent-card";
// The cross-seed block an origin's panel draws, declared to the panel as it evaluates.
import "./panel-cross-seed";

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
function factsOf(entry: Download, obligation: Obligation | undefined): FactLine[] {
  const code = episodeCode(entry);
  const medium = entry.ids === null ? say("unknown") : code === "" ? entry.title : `${entry.title} · ${code}`;
  const lines: FactLine[] = [
    { c: say("name"), v: entry.name },
    { c: say("medium"), v: medium },
    { c: say("tracker"), v: entry.tracker },
    { c: say("origin"), v: i18next.t(entry.origin ? "screens.torrents.origin" : "screens.torrents.crossSeed") },
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
    { c: say("added"), v: addedOf(entry) },
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
 * Builds a torrent's descriptor.
 *
 * @param subject The entry, `<hash>:<tracker>`.
 * @param cache What the query cache holds.
 * @returns The descriptor, or null while the client's list has not landed or
 *     no longer holds the entry.
 */
function torrentPanel(subject: string, cache: PanelCache): PanelDescriptor | null {
  const [infoHash, tracker] = subject.split(":");
  const downloads = cache.held<Schemas["Downloads"]>(downloadsKey)?.downloads;
  const entry = downloads?.find((one) => one.infoHash === infoHash && one.tracker === tracker);
  if (entry === undefined) return null;
  const obligations = cache.held<Schemas["Obligations"]>(obligationsKey)?.items ?? [];
  // A LINKED ENTRY LEADS TO ITS MEDIUM'S SHEET; an unlinked one to its folder's
  // resolution, when the engine holds a folder for it — and says so when not.
  const path: Action | null = entry.ids !== null
    ? { text: say("seeSheet"), icone: icons.eye, target: { mediasheet: entry.title } }
    : entry.folder !== null
      ? { text: say("identify"), icone: icons.play, ton: "primary", target: { resolution: entry.folder } }
      : null;
  const owed = owedBy(entry, obligations);
  // A CROSS-SEED'S OBLIGATION SAYS WHOSE COPY IT IS, and leads to the original's sheet (S4).
  const origin = owed?.crossSeedOf ?? null;
  const toOrigin: Action | null = origin === null || origin.media === null
    ? null
    : { text: say("seeOrigin"), icone: icons.eye, target: { mediasheet: origin.title } };
  return {
    title: entry.title,
    meta: entry.tracker,
    blocs: [
      { type: "faits", lignes: factsOf(entry, owed) },
      path === null ? { type: "note", text: say("noFolder") } : null,
      // AN ORIGIN'S CROSS-SEED, tracker by tracker — never repeated on a cross-seed's own entry.
      entry.crossSeed === null ? null : {
        type: "crossSeed",
        origin: { infoHash: entry.infoHash, name: entry.name, tracker: entry.tracker, progress: entry.progress },
        pairs: entry.crossSeed.pairs,
        titleExcluded: entry.crossSeed.titleExcluded,
      },
      {
        type: "actions",
        actions: [
          path,
          toOrigin,
          {
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
    { queryKey: downloadsKey, queryFn: async () => read<Schemas["Downloads"]>(downloadsKey[0]) },
    { queryKey: obligationsKey, queryFn: async () => read<Schemas["Obligations"]>(obligationsKey[0]) },
  ],
});
