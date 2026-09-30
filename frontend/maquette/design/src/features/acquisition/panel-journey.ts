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
import { icons } from "../../lib/shell-doors";
import i18next from "i18next";
import { registerProducer, type Action, type PanelCache, type PanelDescriptor, type PanelNeed } from "../../ui/panel/contract";
import { read } from "../../lib/query-client";
import { acquisitionKey, tabHolding } from "../../lib/arrival-slots";
import { queueKey, type AcquisitionQueue } from "../../lib/queue";
import { store } from "../../lib/store-access";
import type { Schemas } from "../../lib/contract-schemas";


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

/**
 * One rung as a line of the sheet — or, for a step of « rangé », a line under it.
 *
 * @param stage The rung or the step.
 * @param name Its name, as the line spells it.
 * @returns The line.
 */
function stageLine(stage: Stage, name: string) {
  return {
    c: name,
    v: stage.when || NO_TIME,
    pip: STAGE_PIP[stage.state] ?? "neutral",
    terne: stage.state === "pending" || stage.state === "skipped",
  };
}

// THE RELEASE THE JOURNEY IS ABOUT, and it is a fixture rather than an answer:
// the contract's `readJourney` returns the STAGES and nothing else, so there is
// nowhere to read it from. Recorded as a demand on the backend (D7) rather than
// dressed up — a journey names the release it followed, and the interface
// requires it.
const RELEASE = "Furious.S01E01.MULTi.1080p.WEB-DL";

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
  // COVERED BY A WHOLE SEASON'S RECOVERY (Q6): the pointer, FOLLOWED (§ 13) —
  // the tab holding the season's card now, that card named — or, once the
  // season has left both tabs, where it went and the sheet.
  const pointer: { note: string; action: Action } | null = cover === undefined ? null : tab !== undefined
    ? {
        note: translate("panels.journey.absorbedBy", { season }),
        action: {
          text: translate("panels.journey.seeSeasonCard"), icone: icons.eye, ton: "primary" as const,
          target: { go: "acq", dial: `${tab}${DIAL_SEPARATOR}${cover}` },
        },
      }
    : {
        note: translate("panels.journey.absorbedEnded", { season }),
        action: { text: translate("panels.journey.seeSheet"), icone: icons.eye, ton: "primary" as const,
          target: { mediasheet: title } },
      };
  return {
    address: "journey:" + subject,
    title: itemOf(subject) === "" ? title : `${title} · ${itemOf(subject)}`,
    meta: [translate("panels.journey.metaBefore"), { m: RELEASE }],
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
          ...(stage.steps ?? []).map((step) => stageLine(step, translate("surfaces.ladder.step", {
            name: translate(`surfaces.ladder.steps.${step.rung}`),
          }))),
        ]),
      },
      { type: "note", text: translate("panels.journey.provenanceNote") },
      {
        type: "actions",
        actions: pointer !== null
          // A COVERED EPISODE IS NOT RELAUNCHED ALONE (17:36: « aucun
          // téléchargement … en parallèle »): its journey offers the pointer.
          ? [pointer.action, ...(tab === undefined ? [] : [{
              text: translate("panels.journey.seeSheet"), icone: icons.eye, target: { mediasheet: title },
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
          // to move there.
          {
            text: translate("panels.journey.requeue"),
            icone: icons.refresh,
            ton: "primary",
            target: { "journey-requeue": subject },
          },
          {
            text: translate("panels.journey.rescrape"),
            icone: icons.search,
            target: { "journey-rescrape": subject },
          },
          {
            text: translate("panels.journey.seeSheet"),
            icone: icons.eye,
            target: { mediasheet: title },
          },
        ],
      },
    ],
  };
}

registerProducer("journey", {
  produce: journeyPanel,
  // THE QUEUE FIRST: it lays the acquisition's ladder where its card stands,
  // and the stages are then read off that one ladder.
  needs: (subject) => [queueQuery(), journeyQuery(subject)],
});
