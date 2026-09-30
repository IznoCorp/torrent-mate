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

/**
 * Builds one journey's descriptor.
 *
 * Args:
 *     title: The medium the journey followed.
 *     cache: What the query cache holds.
 *
 * Returns:
 *     The descriptor, or null while the stages have not landed.
 */
function journeyPanel(title: string, cache: PanelCache): PanelDescriptor | null {
  const stages = cache.held<Stage[]>(journeyQuery(title).queryKey);
  if (stages === undefined) return null;
  const translate = i18next.t.bind(i18next);
  return {
    address: "journey:" + title,
    title,
    meta: [translate("panels.journey.metaBefore"), { m: RELEASE }],
    blocs: [
      {
        type: "faits",
        // THE LADDER WHOLE: its eight rungs, and under « rangé » the three
        // pipeline steps it merges, from the same answer the card reads.
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
        // OWN TUNNEL (§ 17): the tunnel's verbs are offered on an acquisition
        // the account asked for, or to one that pilots every acquisition.
        actions: offeredActs<Action | null>([
          // THE TUNNEL'S OWN VERBS (B-302, §20: it « reprend là où il s'est
          // arrêté, par l'opérateur »). Their `data-*` names are answered by
          // `lib/verbs`: a verb that never existed in the engine had no branch
          // to move there.
          {
            text: translate("panels.journey.requeue"),
            icone: icons.refresh,
            ton: "primary",
            target: { "journey-requeue": title },
          },
          {
            text: translate("panels.journey.rescrape"),
            icone: icons.search,
            target: { "journey-rescrape": title },
          },
          {
            text: translate("panels.journey.seeSheet"),
            icone: icons.eye,
            target: { mediasheet: title },
          },
          // « RÉAFFECTER… », to whoever holds the right (round 8 Q13 = A).
          heldRights().holds("acquisition.reassign") ? reassignAction("card", title) : null,
        ], heldAcquisition(title), heldRights()),
      },
    ],
  };
}

registerProducer("journey", {
  produce: journeyPanel,
  needs: (subject) => [journeyQuery(subject), accountQuery],
});
