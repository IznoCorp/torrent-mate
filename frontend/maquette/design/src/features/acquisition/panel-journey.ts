// The journey sheet — the TUNNEL as the operator sees it (§20).
//
// It lives with Acquisitions because a journey is one acquisition's own
// history: what was taken, when, and where it has got to. §20 says a blocked
// tunnel « reprend là où il s'est arrêté, par l'opérateur », and the two verbs
// that do the resuming are offered here — `features/acquisition/journey-verbs.ts`
// does them. This header used to say they « belong to the lot that wires the
// tunnel's verbs »; that lot is this one and the sentence has stopped being
// true.
//
// ITS STEPS COME FROM THE LAYER, not from a literal inside the function. The
// engine's producer carried the five stages inline; the mock layer already
// answered them at `/api/acquisition/journeys/{infoHash}` and nothing called
// it. That fixture dies here, which is what D5 asks of every producer that
// moves.
//
// A PER-SUBJECT READ, so its need is a FUNCTION of the subject: a journey is
// read per medium and a boot cannot know which one will be asked for.
import { heldAcquisition, offeredActs } from "./act-rights";
import { reassignAction } from "./reassign";
import { accountQuery, heldRights } from "../../lib/account";
import { icons } from "../../lib/shell-doors";
import i18next from "i18next";
import { registerProducer, type Action, type PanelCache, type PanelDescriptor, type PanelNeed } from "../../ui/panel/contract";
import { read } from "../../lib/query-client";
import { acquisitionKey, tabHolding } from "../../lib/arrival-slots";
import { queueKey, type AcquisitionQueue } from "../../lib/queue";
import { store } from "../../lib/store-access";
import type { Schemas } from "../../lib/contract-schemas";
import { DECISIONS_QUERY, type Decisions } from "./decision-queries";
import { settledDecisionOf } from "./decision-block";
import { heldIdentity, providerAddress } from "../../lib/held-identity";


/** One rung of a medium's ladder, as the contract answers it. */
type Stage = Schemas["JourneyStage"];

/** Which pip says a rung's state. The six are the interface's drawing. */
const STAGE_PIP: Record<Stage["state"], string> = {
  done: "success",
  now: "info",
  waiting: "waiting",
  blocked: "danger",
  aside: "neutral",
  skipped: "neutral",
  pending: "neutral",
};

// Between the tab and the acquisition a landing names, in a dial.
const DIAL_SEPARATOR = ":";

// The mark of a time nobody recorded — never a reconstructed one.
const NO_TIME = "—";

// A LINE SAYS ITS STATE IN WORDS when no time was recorded for it: « — » read
// the same for done, running and never reached. Only a rung never lived keeps
// the mark. A done rung still owes its time — the acts that pass one write it —
// and the word stands only where nothing recorded it.
const WITHOUT_TIME: Partial<Record<Stage["state"], string>> = {
  done: "surfaces.ladder.doneUntimed",
  now: "surfaces.ladder.nowUntimed",
};

/**
 * One rung as a line of the sheet — or, for a step of « rangé », a line under it.
 *
 * @param stage The rung or the step.
 * @param name Its name, as the line spells it.
 * @returns The line.
 */
function stageLine(stage: Stage, name: string) {
  const words = WITHOUT_TIME[stage.state];
  return {
    c: name,
    v: stage.when || (words ? i18next.t(words) : NO_TIME),
    pip: STAGE_PIP[stage.state] ?? "neutral",
    terne: stage.state === "pending" || stage.state === "skipped",
  };
}

/**
 * The release a journey followed: the folder of ITS OWN acquisition's decision.
 *
 * A FIXTURE NAMED ONE RELEASE FOR EVERY JOURNEY — President Curtis's journey
 * read « release Furious.S01E01… ». The contract's `readJourney` answers the
 * stages alone (demand D7), so the release is read where the layer does hold
 * it: the decision about this medium, settled or pending, names its folder.
 * None known, none named.
 *
 * @param title The medium.
 * @param decisions The decisions read, both lists.
 * @returns The release's folder, or null.
 */
function releaseOf(title: string, decisions: Decisions | undefined): string | null {
  const pending = decisions?.pending.find((decision) => decision.title === title || decision.folder === title);
  return pending?.folder ?? settledDecisionOf(decisions, { title })?.folder ?? null;
}

/**
 * What « Voir la fiche » carries from a journey: the medium's identity, or nothing.
 *
 * A TITLE IS NOT AN ADDRESS (B-616). The sheet is addressed by provider identity
 * (DOIT-11), and a journey's title is the acquisition's — « The Alabama
 * Solution », which the library holds as « The Alabama Solution dans l'enfer de
 * la prison ». Handed the title alone, the crossing asked the cache, found no
 * read naming it, and opened the resolution of « élément inconnu ». So the act
 * carries the identity the journey knows, as a candidate's poster does
 * (B-578): its card's, else the one its decision chose, else what a held read
 * says of that title. Knowing none — a medium left as it was — the act is not
 * offered: never a button that leads nowhere (DOIT-7).
 *
 * @param title The medium.
 * @param ids Its own card's provider identifiers, when the queue holds it.
 * @param decisions The decisions read, both lists.
 * @returns The act's target, or null when no identity is known.
 */
function sheetTarget(
  title: string,
  ids: Record<string, string | number | null | undefined> | null | undefined,
  decisions: Decisions | undefined,
): Record<string, string> | null {
  const known = (held: typeof ids) => providerAddress(held
    ? Object.fromEntries(Object.entries(held).filter((entry): entry is [string, string | number] =>
      entry[1] !== null && entry[1] !== undefined && entry[1] !== ""))
    : null);
  const choice = settledDecisionOf(decisions, { title })?.choice;
  const address = known(ids)
    ?? (choice ? { provider: choice.provider, id: String(choice.id) } : null)
    ?? known(heldIdentity(title)?.ids);
  return address === null
    ? null
    : { mediasheet: title, provider: address.provider, "provider-id": address.id };
}

/**
 * Whether the medium's identification is behind it: the rung « identifié » done.
 *
 * @param stages The journey's rungs.
 * @returns True once that rung is done.
 */
function identifiedDone(stages: Stage[]): boolean {
  return stages.some((stage) => stage.rung === "identified" && stage.state === "done");
}

/** The stages of one journey, as a query definition. */
function journeyQuery(subject: string): PanelNeed {
  return {
    queryKey: ["/api/acquisition/journeys", subject],
    queryFn: async () =>
      read<Stage[]>(`/api/acquisition/journeys/${encodeURIComponent(subject)}`),
  };
}

/** The world the harness's dial names — the key the queue is cached under carries it. */
function scenario(): string {
  return String(store.read().state.scen) === "loaded" ? "loaded" : "";
}

/** The acquisition queue, as a query definition: a journey reads what covers it there. */
function queueQuery(): PanelNeed {
  const world = scenario();
  return {
    queryKey: queueKey(world),
    queryFn: async () => read<AcquisitionQueue>("/api/acquisition/to-handle",
      new URLSearchParams(world ? { scenario: world } : {})),
  };
}

// Between a title and the season or episode its acquisition is of, in a key.
const KEY_SEPARATOR = "|";

/**
 * The part of an acquisition's key that names its season or episode.
 *
 * @param key The key, « Silo|S03E07 ».
 * @returns « S03E07 », or an empty string for a key naming a title alone.
 */
function itemOf(key: string): string {
  const at = key.indexOf(KEY_SEPARATOR);
  return at === -1 ? "" : key.slice(at + 1);
}

/**
 * What a whole season's recovery says of one acquisition: what covers it, and
 * what it covers — each from the served pointer, never a label (DECIDED 5).
 *
 * @param subject The acquisition's key.
 * @param queue The queue's answer, when held.
 * @returns Its own card, the tab holding its cover now, and the cards it covers.
 */
function coverOf(subject: string, queue: AcquisitionQueue | undefined) {
  const cards = queue ? [...queue.inFlight, ...queue.arrivals, ...queue.blocked, ...queue.takeable] : [];
  const own = cards.find((card) => acquisitionKey(card) === subject);
  const cover = own?.absorbedBy ?? undefined;
  return {
    own,
    cover,
    tab: queue && cover ? tabHolding(queue, cover) : undefined,
    covered: cards.filter((card) => card.absorbedBy === subject),
  };
}

/**
 * Whether a covered episode's own torrent is already on its way — its ladder
 * past « attrapé » (Q16: « téléchargement déjà en cours »).
 *
 * @param card The covered card.
 * @returns True once it was grabbed.
 */
function alreadyRunning(card: { ladder?: Stage[] }): boolean {
  return (card.ladder ?? []).some((rung) => rung.rung === "grabbed" && rung.state === "done");
}

// The rungs before the torrent is in the staging area: while one runs, the
// download is still going and there is nothing to put back in the queue.
const BEFORE_ARRIVAL: readonly Stage["rung"][] = ["requested", "searched", "grabbed", "downloading"];

/**
 * Whether a journey's download is still under way: a rung before « arrivé »
 * running now.
 *
 * @param stages Its rungs.
 * @returns True while it downloads.
 */
function running(stages: Stage[]): boolean {
  return stages.some((stage) => stage.state === "now" && BEFORE_ARRIVAL.includes(stage.rung));
}

/**
 * Builds one journey's descriptor.
 *
 * A JOURNEY PER ACQUISITION (Q14 = A): the subject is the acquisition's key —
 * « Silo|S03 », « Silo|S03E07 » — and a key naming a title alone is the title.
 *
 * Args:
 *     subject: The acquisition the journey followed.
 *     cache: What the query cache holds.
 *
 * Returns:
 *     The descriptor, or null while the stages have not landed.
 */
function journeyPanel(subject: string, cache: PanelCache): PanelDescriptor | null {
  const stages = cache.held<Stage[]>(journeyQuery(subject).queryKey);
  if (stages === undefined) return null;
  const translate = i18next.t.bind(i18next);
  const title = subject.split(KEY_SEPARATOR)[0];
  const { own, cover, tab, covered } = coverOf(subject, cache.held<AcquisitionQueue>(queueQuery().queryKey));
  const season = own?.season ?? null;
  const decisions = cache.held<Decisions>(DECISIONS_QUERY.queryKey);
  const release = own?.release || releaseOf(title, decisions);
  const toSheet = sheetTarget(title, own?.ids, decisions);
  // COVERED BY A WHOLE SEASON'S RECOVERY (Q6): the pointer, FOLLOWED (§ 13) —
  // the tab holding the season's card now, that card named — or, once the
  // season has left both tabs, where it went and the sheet.
  const pointer: { note: string; action: Action | null } | null = cover === undefined ? null : tab !== undefined
    ? {
        note: translate("panels.journey.absorbedBy", { season }),
        action: {
          text: translate("panels.journey.seeSeasonCard"), icone: icons.eye, ton: "primary" as const,
          target: { go: "acq", dial: `${tab}${DIAL_SEPARATOR}${cover}` },
        },
      }
    : {
        note: translate("panels.journey.absorbedEnded", { season }),
        action: toSheet === null ? null : { text: translate("panels.journey.seeSheet"), icone: icons.eye,
          ton: "primary" as const, target: toSheet },
      };
  return {
    address: "journey:" + subject,
    title: itemOf(subject) === "" ? title : `${title} · ${itemOf(subject)}`,
    // THE RELEASE ITS OWN ACQUISITION FOLLOWED: the one its card carries (SR4 —
    // the season's pack for a season, the episode's own for an episode), else
    // the folder of its decision; none named while neither knows, never
    // another journey's.
    meta: release === null ? [translate("panels.journey.metaAlone")]
      : [translate("panels.journey.metaBefore"), { m: release }],
    blocs: [
      ...(pointer === null ? [] : [{ type: "note" as const, text: pointer.note }]),
      {
        type: "faits",
        // THE LADDER WHOLE: its eight rungs, and under « rangé » the three
        // pipeline steps it merges, from the same answer the card reads. A
        // covered episode's stops at the rung it had reached: the season's
        // progress is the season's to say.
        lignes: stages.flatMap((stage) => [
          stageLine(stage, translate(`surfaces.ladder.rungs.${stage.rung}`)),
          ...(stage.steps ?? []).flatMap((step) => [
            stageLine(step, translate("surfaces.ladder.step", {
              name: translate(`surfaces.ladder.steps.${step.rung}`),
            })),
            // « ENRICHI » UNFOLDED (L24 OPEN 5 = B): what the enrichment
            // fetched, each part with its own state — the sheet only; the
            // card keeps its eight rungs.
            ...(step.steps ?? []).map((part) => stageLine(part, translate("surfaces.ladder.subStep", {
              name: translate(`surfaces.ladder.steps.${part.rung}`),
            }))),
          ]),
        ]),
      },
      // THE DECISION THAT IDENTIFIED IT, once « identifié » is passed (L24 S1):
      // the block says itself nothing when the medium has none.
      identifiedDone(stages) ? { type: "decision", subject: title } : null,
      { type: "note", text: translate("panels.journey.provenanceNote") },
      {
        type: "actions",
        // OWN TUNNEL (§ 17): the tunnel's verbs are offered on an acquisition
        // the account asked for, or to one that pilots every acquisition.
        actions: offeredActs<Action | null>(pointer !== null
          // A COVERED EPISODE IS NOT RELAUNCHED ALONE (17:36: « aucun
          // téléchargement … en parallèle »): its journey offers the pointer.
          ? [...(pointer.action === null ? [] : [pointer.action]), ...(tab === undefined || toSheet === null ? [] : [{
              text: translate("panels.journey.seeSheet"), icone: icons.eye, target: toSheet,
            }])]
          : [
          // THE SEASON'S JOURNEY NAMES EACH EPISODE IT COVERS, with its state,
          // each a path to that episode's own journey (Q16 = A).
          ...covered.map((card) => ({
            text: translate(alreadyRunning(card) ? "panels.journey.absorbedRunning" : "panels.journey.absorbedCovered",
              { episode: itemOf(acquisitionKey(card)) }),
            icone: icons.refresh,
            target: { journey: acquisitionKey(card) },
          })),
          // THE TUNNEL'S OWN VERBS (B-302, §20: it « reprend là où il s'est
          // arrêté, par l'opérateur »). Their `data-*` names are answered by
          // `lib/verbs`: a verb that never existed in the engine had no branch
          // to move there. A DOWNLOAD STILL RUNNING has not stopped: nothing is
          // put back in the queue while it goes on.
          ...(running(stages) ? [] : [{
            text: translate("panels.journey.requeue"),
            icone: icons.refresh,
            ton: "primary" as const,
            target: { "journey-requeue": subject },
          }]),
          {
            text: translate("panels.journey.rescrape"),
            icone: icons.search,
            target: { "journey-rescrape": subject },
          },
          ...(toSheet === null ? [] : [{
            text: translate("panels.journey.seeSheet"),
            icone: icons.eye,
            target: toSheet,
          }]),
          // « RÉAFFECTER… », to whoever holds the right (round 8 Q13 = A).
          heldRights().holds("acquisition.reassign") ? reassignAction("card", title) : null,
        ], heldAcquisition(title), heldRights()),
      },
    ],
  };
}

registerProducer("journey", {
  produce: journeyPanel,
  // THE QUEUE FIRST: it lays the acquisition's ladder where its card stands,
  // and the stages are then read off that one ladder; the decisions name the
  // release when the card carries none.
  needs: (subject) => [queueQuery(), journeyQuery(subject), DECISIONS_QUERY, accountQuery],
});
