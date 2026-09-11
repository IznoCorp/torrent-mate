// « Récupérer cette saison » — the verb a season with a hole owes (B-301).
//
// THE SEASON MATRIX SHOWED THE HOLE AND OFFERED NOTHING. It draws « Saison 3 ·
// 6/7 · 1 manquant » and there was no way to ask for the missing episode.
// DOIT-3 is « agir là où l'on observe »; this is where one observes it.
//
// IT LIVES IN `features/media/` BECAUSE THAT IS WHERE THE PANEL IS DRAWN, and
// invariant 7 is absolute: the media feature may not import
// `features/acquisition/`. What it does instead is call the OPERATION — a
// mutation on the contract is not a feature import. `features/media/queries.ts`
// is this feature's own door to the layer, and this is its mutating half.
//
// A FILE OF ITS OWN beside the block it serves, never a growth of
// `panel-seasons.tsx`: a verb is behaviour, the block is drawing, and invariant
// 6 asks for the cut before the ceiling rather than after it.
import type { QueryClient } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";
import { markSeasonQueued } from "./queued-seasons";
import i18next from "i18next";
import { HELD, send } from "../../lib/query-client";

/** What the operation answers, as the contract declares it. */
type SeasonGrab = {
  season: number;
  absorbedCount: number;
  queued: boolean;
  runUid: string | null;
  newlyFollowed: boolean;
};

/**
 * Asks for one season of one follow.
 *
 * WHAT IT SAYS DEPENDS ON WHAT CAME BACK, and that is DOIT-4 rather than a
 * nicety. An ask that arrives while the pipeline is working is QUEUED — the
 * interface says « En file — pipeline en cours » and never « occupé », and it
 * never shows the 409 the backend answers for that case (NE-DOIT-PAS-3, §20).
 * An ask that starts now says so. **A toast is written from the ANSWER, never
 * before it**: a sentence composed optimistically is a sentence that can be
 * right about nothing, which is NE-DOIT-PAS-1 and the defect `data-take` wore
 * for a whole wave.
 *
 * OFFLINE IS NOT A FAILURE. `send` answers `HELD` when the mutation is queued
 * for a network that is not there; saying « asked for » then would be a lie and
 * saying « failed » would be a worse one, so the interface says it is held.
 *
 * Args:
 *     title: The follow, as this interface knows it — by TITLE. The backend
 *         wants a rowid; that is a demand on the register (§ 2b), not something
 *         to invent here.
 *     season: The season number, 1-based.
 *
 * Returns:
 *     Whether the ask is WAITING on the pipeline rather than under way. The
 *     caller records it so the season can go on saying so after the message
 *     has gone (DOIT-4's visible half): a sentence shown for four seconds
 *     tells the operator who was looking, and nobody else.
 */
/**
 * Asks for a season and settles every surface that shows it.
 *
 * WHY IT EXISTS RATHER THAN LIVING IN A HANDLER. Two surfaces draw the same
 * season with the same hole — the follow panel and the media sheet's own list —
 * and the queued mark was deliberately put on BOTH. An action drawn on one of
 * them with its behaviour written inline is an action the other cannot offer
 * without copying four steps, and a copied sequence is one that stops agreeing
 * the first time either end moves.
 *
 * THE FOUR STEPS ARE ONE UNIT: ask, remember the wait so the season goes on
 * saying so after the message has gone, re-read the follows the ask moved, and
 * put the open panel back from what came. The last one is the whole of it —
 * without it the surface the operator pressed is the only one that does not
 * know, which is where he was looking.
 *
 * Args:
 *     client: The cache both surfaces read.
 *     title: The followed medium.
 *     season: The season number, 1-based.
 */
export async function askForSeason(
  client: QueryClient,
  title: string,
  season: number,
): Promise<void> {
  const waiting = await grabSeason(title, season);
  if (waiting) markSeasonQueued(client, title, season);
  await client.refetchQueries({ queryKey: ["/api/acquisition/followed"] });
  window.__panel?.redraw();
}

/* THE ASKS IN FLIGHT, keyed `title|season`. Module state and not a React ref:
   the same season is reachable from two surfaces, and a guard held by one
   component would not see a press on the other. */
const inFlight = new Set<string>();

/* AND WHAT IS IN FLIGHT IS DRAWN. The guard below answers a second press with
   silence, and the operator saw a button that had taken nothing: with the answer
   held back 2.5 s the pressed act read no state at all, the same text at full
   opacity, while three more presses did nothing visible. So the asks in flight
   are published, and both surfaces draw their act as TAKEN while its ask is out.

   A SNAPSHOT REPLACED ON EVERY CHANGE, never the live set: the subscription
   compares what it is handed, so a set mutated in place would report no change
   and a fresh copy on every read would report one on every render. */
let flightSnapshot: ReadonlySet<string> = new Set();
const flightListeners = new Set<() => void>();

function announceFlight(): void {
  flightSnapshot = new Set(inFlight);
  for (const listener of flightListeners) listener();
}

/**
 * The season asks in flight, keyed `title|season`, for a surface drawing acts.
 *
 * Not the store, for `app/message-presence.ts`'s measured reason: a store write
 * re-renders every page, and a node replaced between a press and its click
 * loses the click (B-247).
 *
 * Returns:
 *     The asks under way right now.
 */
export function useAskedInFlight(): ReadonlySet<string> {
  return useSyncExternalStore(
    (onChange) => {
      flightListeners.add(onChange);
      return () => flightListeners.delete(onChange);
    },
    () => flightSnapshot,
  );
}

export async function grabSeason(title: string, season: number): Promise<boolean> {
  const say = (key: string, values?: Record<string, unknown>) =>
    i18next.t(`verbs.media.${key}`, values ?? {});
  // ONE ASK AT A TIME PER SEASON. Two presses with no settle between them sent
  // two identical requests and produced ONE message, because the second answer
  // replaced the first — so the interface asked twice and said so once. A
  // second press while the first is in flight is not a second intention: it is
  // the same one, made again because nothing had visibly happened yet. It is
  // answered with silence rather than a refusal, because a refusal would say
  // « occupé » to a legitimate act, which is the clause NE-DOIT-PAS-3 refuses.
  //
  // KEYED BY TITLE AND SEASON, never by title alone: asking for season 2 while
  // season 3 is in flight is a different ask and must land.
  const asked = `${title}|${season}`;
  if (inFlight.has(asked)) return false;
  inFlight.add(asked);
  announceFlight();
  try {
    const answered = await send<SeasonGrab>(
      "POST",
      `/api/acquisition/follows/${encodeURIComponent(title)}/seasons/${season}/grab`,
    );
    if (answered === HELD) {
      window.__toast?.show({ message: say("seasonHeld", { season }) });
      return false;
    }
    const grab = answered as SeasonGrab | undefined;
    // THE SENTENCE IS CHOSEN, NOT PLURALISED WITH A PARENTHESIS. « 1
    // épisode(s) » makes the reader do the grammar, and this file's own
    // neighbour — the deck's « 1 suggestion de plus » beside « N suggestions de
    // plus » — already writes each number's sentence out. Three and not two,
    // because a season nothing is known about absorbs NOTHING and « 0 épisodes
    // à récupérer » is both wrong in French, where zero takes the singular, and
    // a worse thing to read than saying so.
    //
    // AND A FOLLOW BEGUN BY THE ASK IS A SECOND FACT, so it has sentences of its
    // own: the same four, each with the follow said in it, chosen by the
    // answer's `newlyFollowed`. Never a clause appended to one of the others,
    // and never a key assembled from two halves: every key is written out, so
    // a reader searching for one finds the line that chooses it.
    const count = grab?.absorbedCount ?? 0;
    const newly = grab?.newlyFollowed === true;
    const messageKey = grab?.queued
      ? newly ? "seasonQueuedNewlyFollowed" : "seasonQueued"
      : count === 0
        ? newly ? "seasonAskedNoneNewlyFollowed" : "seasonAskedNone"
        : count === 1
          ? newly ? "seasonAskedOneNewlyFollowed" : "seasonAskedOne"
          : newly ? "seasonAskedNewlyFollowed" : "seasonAsked";
    window.__toast?.show({
      message: say(messageKey, { season, count }),
    });
    return grab?.queued === true;
  } catch {
    // THE REFUSAL IS SAID, and it is said as a refusal. Swallowing it would
    // leave the operator looking at a season that never moved with no reason
    // given — the silent failure this interface's own constitution refuses.
    window.__toast?.show({ message: say("seasonRefused", { season }) });
    return false;
  } finally {
    // IN A `finally`, so a refused ask can be made again. Released on the
    // throwing path as much as on the answering one: a guard that survived a
    // failure would make the second press — the one that follows a refusal and
    // is the operator's whole recourse — do nothing, for ever.
    inFlight.delete(asked);
    announceFlight();
  }
}
