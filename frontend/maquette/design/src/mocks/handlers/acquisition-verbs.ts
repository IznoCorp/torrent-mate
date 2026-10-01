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
import INCOMPLETE_SHOWS from "../seeds/incomplete-shows.json";
import { POST, route } from "./shared";
import { ladderOf } from "./ladder";
import { mockState } from "../state";
import { accountName } from "../account";
import type { MockRoute } from "../router";
import type { components } from "../../contract/types";
import { seasonsAnswer } from "./media";
import { recoverSeason } from "./season-recovery";

type Schemas = components["schemas"];

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
const UPCOMING = "pending";

// What a follow being acquired reads as — the contract's own `Follow.status`
// token, carried like every other token in this layer.
const BEING_ACQUIRED = "acquiring";

// Who asked for a one-off season: the account, once, in the application — the
// contract's own `Requester.via` token.
const ASKED_ONCE = "request";
// Who launched a season asked for on a sheet: a person — the contract's own
// `QueueCard.trigger` token.
const ASKED_BY_HAND = "manual";
// A one-off card's line names its season the way an episode line does: « S03 ».
const SEASON_MARK = "S";
const SEASON_DIGITS = 2;
const DIGITS_FILL = "0";

// The seeds this module derives from, named at their shapes. A handler holds no
// data literal: what it answers traces to one of these or to the request.
const SEASON_COUNT = SEASONS as Record<
  string,
  { season: number; aired: number; owned: number }[]
>;

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
 * One medium's ladder — laid and held by `./ladder`, which the queue's cards
 * read too.
 *
 * @param subject The medium the journey followed.
 * @returns Its stages — the same array on every call, so a verb that moves them
 *   moves what the next read answers.
 */
export function stagesOf(subject: string) {
  return ladderOf(subject);
}

/**
 * Puts a journey back into the queue, or back onto the scrape.
 *
 * THE TWO ARE NOT THE SAME MOVE, and the difference is what makes either one
 * visible. §20's « reprend là où il s'est arrêté » is a thing the operator
 * WATCHES on the strip, so a verb whose effect the strip cannot show has not
 * been proved by anything:
 *
 * - **Requeued**, the item is WAITING again. Every stage from the first
 *   unfinished one becomes still-to-come: nothing is running, it sits in the
 *   queue. That is also what DOIT-4 draws when the machine is busy.
 * - **Re-scraped**, the passage is running again FROM that stage: the first
 *   unfinished stage becomes the one running and everything after it is still
 *   to come.
 *
 * A FIRST VERSION MOVED NOTHING AT ALL and the rule caught it. It set the first
 * unfinished stage to `now` — which it already was, for the only journey the
 * fixture holds — and copied that stage's own words onto itself. « Restarted »
 * and « still running » looked identical, so a build that called the operation
 * and one that ignored it read the same.
 *
 * Args:
 *     subject: The medium the journey followed.
 *     running: Whether the passage runs again now, or waits in the queue.
 */
function restart(subject: string, running: boolean): void {
  const stages = stagesOf(subject);
  const resumeAt = stages.findIndex((stage) => stage.state !== DONE);
  const from = resumeAt === -1 ? 0 : resumeAt;
  stages.forEach((stage, index) => {
    if (index < from) return;
    stage.state = running && index === from ? RUNNING_NOW : UPCOMING;
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
  // A SEASON THAT TABLE DOES NOT CARRY is counted the way the season surfaces
  // draw it — aired by the scenario's date, less what is held — so the answer
  // never says « aucun épisode » beside a card reading « 0/23 ».
  const drawn = seasonsAnswer([title]);
  const aired = counted?.aired ?? drawn.aired[String(season)] ?? 0;
  const missing = aired - (counted?.owned ?? (drawn.owned[String(season)] ?? []).length);
  return missing > 0 ? missing : 0;
}

/**
 * A whole season's acquisition, as the queue holds it — followed or not, ONE
 * card of the same shape (« uniformiser les comportements »).
 *
 * @param title The show.
 * @param season The season asked for, 1-based.
 * @param follow The follow that asks for it, or undefined for a series nobody
 *     follows — a one-off, asked by the account, once, in the application.
 * @returns Its card: the show's identity and poster, the season on its line and
 *     in its fields, and a person's ask as its trigger.
 */
function seasonCard(
  title: string, season: number, follow: { ids?: unknown; poster?: string | null } | undefined,
): Schemas["QueueCard"] {
  const show = follow ?? (INCOMPLETE_SHOWS as {
    title: string; ids: Record<string, string | number> | null; poster: string | null;
  }[]).find((one) => one.title === title);
  return {
    title,
    secondaryLine: SEASON_MARK + String(season).padStart(SEASON_DIGITS, DIGITS_FILL),
    season,
    episode: null,
    trigger: ASKED_BY_HAND,
    ids: (show?.ids ?? null) as Schemas["QueueCard"]["ids"],
    poster: show?.poster ?? null,
    strip: [0, 0, 0, 0, 0],
    // A FOLLOW'S CARD NAMES THE FOLLOW as its requester, read where every card's
    // is; a one-off names the account's ask.
    ...(follow === undefined ? { requester: { name: accountName(), via: ASKED_ONCE } } : {}),
  };
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
        const missing = episodesMissingFromSeason(title, season);
        // ONLY WHEN THE SEASON HAD SOMETHING TO GET. An answer of zero moved an
        // up-to-date follow to being acquired: « 5/5 · En cours d'acquisition »
        // on the follow's row and panel, beside the sentence « aucun épisode à
        // récupérer » just said. Nothing is acquired, so nothing moves.
        if (found !== undefined && !queued() && missing > 0) found.status = BEING_ACQUIRED;
        // THE SEASON'S RECOVERY IS ONE CARD, followed or not (Q5): a series
        // nobody follows begins no follow (round 10 Q2) and its card is a
        // one-off; a followed series' card is the follow's. The ask moves the
        // world — never a success over an unchanged one (B-378) — and the
        // episodes of that season it covers leave « En cours » (Q6). ONE ITEM,
        // ONE CARD: a second ask queues nothing more, and says so.
        const recovery = found !== undefined && missing === 0
          ? { reused: false }
          : recoverSeason(seasonCard(title, season, found));
        return {
          season,
          absorbedCount: missing,
          queued: queued(),
          reused: recovery.reused,
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
        // QUEUED, so nothing runs: every unfinished stage is waiting.
        restart(request.parameters.infoHash, false);
        return { queued: queued(), runUid: null };
      },
    ),
    route(
      "rescrapeJourney",
      POST,
      "/api/acquisition/journeys/{infoHash}/rescrape",
      (request) => {
        // RUNNING AGAIN, from the stage the passage stopped at.
        restart(request.parameters.infoHash, true);
        return { queued: queued(), runUid: null };
      },
    ),
  ];
}
