// The tunnel's verbs, as the layer answers them.
//
// A FILE OF ITS OWN, and not a growth of `acquisition.ts`. That module is at
// 233 non-blank lines against a soft warning at 250, and these three
// operations are one subject — what the operator DOES to a tunnel — beside its
// subject, which is what is wanted and what is being fetched. Invariant 6 asks
// for the cut before the ceiling, not after it.
//
// WHAT MAKES THESE THREE DIFFERENT FROM THEIR NEIGHBOURS: they must MOVE
// SOMETHING. A verb is proved by the state it changes, never by the message it
// answers, so a handler here that acknowledged and mutated nothing would let a
// rule pass over a build that called the operation and threw the answer away —
// which is exactly what `data-take` did for a whole wave under a green gate.
// Each one below writes the state the surface reads back.
//
// THE IDENTIFIERS ARE TITLES. The interface knows a follow by its title and a
// journey by the title too; the backend wants a rowid and an info hash. The
// demand register carries that (§ 2b), and no identifier is invented here.
import SEASONS from "../seeds/seasons.json";
import JOURNEY_STAGES from "../seeds/journey-stages.json";
import { POST, route } from "./shared";
import { mockState } from "../state";
import type { MockRoute } from "../router";

// The pipeline is BUSY unless it is idle. DOIT-4 turns on this one word: an ask
// that arrives while the machine is working is queued VISIBLY — « En file —
// pipeline en cours » — and never refused. The backend answers 409 for the same
// case; NE-DOIT-PAS-3 forbids the interface showing it, so the layer answers
// what the interface requires and the difference is a demand.
const IDLE = "idle";

// The stage tokens the journey's pips are drawn from. They are the contract's
// own `JourneyStage.state` values, carried like every other token here — the
// VALUES are the layer's data, the NAMES are code and are English.
const DONE = "done";
const RUNNING_NOW = "now";
const UPCOMING = "todo";

// What a follow being acquired reads as — the contract's own `Follow.status`
// token, carried like every other token in this layer.
const BEING_ACQUIRED = "acquiring";

// The seeds this module derives from, named at their shapes. A handler holds no
// data literal: what it answers traces to one of these or to the request.
const SEASON_COUNT = SEASONS as Record<
  string,
  { season: number; aired: number; owned: number }[]
>;
const SEEDED_STAGES = JOURNEY_STAGES as {
  label: string;
  when: string;
  state: string;
}[];

/**
 * Whether the machine is working, and an ask therefore waits.
 *
 * READ FROM THE LAYER'S OWN PIPELINE STATE, which is what `runPipeline`,
 * `pausePipeline` and `killPipeline` write. It is deliberately NOT the engine's
 * `pipe` field: that lives in the interface's store, and a layer deciding what
 * to answer from a value the interface holds would be answering its own
 * question.
 *
 * @returns True when the ask is queued rather than started now.
 */
function queued(): boolean {
  return mockState().pipelineState !== IDLE;
}

/**
 * The stages of one journey, filled from the seed the first time it is asked
 * for.
 *
 * @param subject The medium the journey followed.
 * @returns Its stages — the same array on every call, so a verb that moves them
 *   moves what the next read answers.
 */
export function stagesOf(subject: string) {
  const state = mockState();
  const held = state.journeyStages[subject];
  if (held !== undefined) return held;
  const fresh = SEEDED_STAGES.map((stage) => ({ ...stage }));
  state.journeyStages[subject] = fresh;
  return fresh;
}

/**
 * Puts a journey back to work, and answers what its stages now say.
 *
 * THE MOVE IS THE POINT. The first stage that has not finished becomes the one
 * RUNNING, and every stage after it is still to come — which is what « reprend
 * là où il s'est arrêté » means read off a strip (§20). A journey already at
 * its first stage moves nothing visible and answers so; a journey whose stages
 * are all done is restarted from the first, because that is what asking again
 * means.
 *
 * @param subject The medium the journey followed.
 */
function restart(subject: string): void {
  const stages = stagesOf(subject);
  const resumeAt = stages.findIndex((stage) => stage.state !== DONE);
  const from = resumeAt === -1 ? 0 : resumeAt;
  // READ BEFORE ANYTHING MOVES. The first version looked for the running stage
  // INSIDE the loop that sets stages running, so after the first iteration it
  // found the stage it had just written and copied that stage's own words onto
  // itself. A reading taken after the mutation it describes is not a reading of
  // what was there.
  const wasRunning = stages.find((stage) => stage.state === RUNNING_NOW);
  stages.forEach((stage, index) => {
    if (index < from) return;
    stage.state = index === from ? RUNNING_NOW : UPCOMING;
    // THE WORDS COME FROM THE STAGES THEMSELVES. A stage put back to work
    // borrows the phrasing the running stage had, because this module may hold
    // no data literal and inventing a sentence here would put interface text in
    // the layer.
    if (index === from && wasRunning !== undefined) stage.when = wasRunning.when;
  });
}

/**
 * How many episode-level asks a season's ask absorbs.
 *
 * DERIVED FROM THE SEED THE INTERFACE ITSELF DRAWS FROM, and that is the whole
 * correction. A first version crossed the sheet's provider CATALOGUE with the
 * owned-episode seed and answered **10** for Silo's season 3 — while the panel
 * beside it printed « 6/7 · 1 manquant ». The catalogue says how many episodes
 * a season will have (ten announced); `seasons.json` says how many have AIRED
 * and how many are held, which is what the matrix is drawn from and what a
 * season grab is actually for. An interface that says « 1 manquant » and then
 * « 10 épisodes à récupérer » contradicts itself in two adjacent sentences.
 *
 * A season nothing is known about absorbs nothing, which is the honest answer
 * rather than a guess.
 *
 * @param title The follow.
 * @param season The season, 1-based.
 * @returns How many episodes the ask covers.
 */
function episodesMissingFromSeason(title: string, season: number): number {
  const counted = (SEASON_COUNT[title] ?? []).find(
    (one) => one.season === season);
  if (counted === undefined) return 0;
  const missing = counted.aired - counted.owned;
  return missing > 0 ? missing : 0;
}

/** Every route the tunnel's verbs answer. */
export function acquisitionVerbRoutes(): MockRoute[] {
  return [
    route(
      "grabSeasonForFollow",
      POST,
      "/api/acquisition/follows/{followedId}/seasons/{season}/grab",
      (request) => {
        const title = request.parameters.followedId;
        const season = Number(request.parameters.season);
        const state = mockState();
        // THE FOLLOW'S STATE MOVES, and that is what the rule reads. A season
        // asked for is a season being acquired; the interface has no per-season
        // status to write — `Follow.status` is the whole follow's — and the
        // register carries that as a demand rather than this file inventing
        // one.
        const found = state.follows.find((follow) => follow.title === title);
        if (found !== undefined && !queued()) found.status = BEING_ACQUIRED;
        return {
          season,
          absorbedCount: episodesMissingFromSeason(title, season),
          queued: queued(),
          // NULL, ALWAYS, and it is not a placeholder. The layer holds no run
          // identifier at all — `runPipeline` answers `uid: null` for the same
          // reason — and the register asks the backend for one.
          runUid: null,
        };
      },
    ),
    route(
      "requeueJourney",
      POST,
      "/api/acquisition/journeys/{infoHash}/requeue",
      (request) => {
        restart(request.parameters.infoHash);
        return { queued: queued(), runUid: null };
      },
    ),
    route(
      "rescrapeJourney",
      POST,
      "/api/acquisition/journeys/{infoHash}/rescrape",
      (request) => {
        restart(request.parameters.infoHash);
        return { queued: queued(), runUid: null };
      },
    ),
  ];
}
