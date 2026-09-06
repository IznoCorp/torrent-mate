// The tunnel's own verbs — « Remettre en file » and « Re-scraper » (B-302).
//
// §20: a blocked tunnel « reprend là où il s'est arrêté, par l'opérateur ». The
// journey sheet IS the tunnel as the operator sees it, and until this file it
// offered one action — « Voir la fiche » — while both operations went uncalled.
//
// A FILE OF ITS OWN beside the producer, never a growth of `panel-journey.ts`:
// a verb is behaviour and a producer is a function from the cache to a
// descriptor. What the producer gains is two entries in its `actions` block.
//
// ⚠ « RE-SCRAPER » IS NOT THE MEDIA SHEET'S METADATA RE-SCRAPE. The resources
// carry « Re-scraper les métadonnées » already, and that is another subject: it
// asks the providers again about a WORK. This one re-runs the tunnel's own
// scrape for one tracked staging item, which is why its sentence names the
// passage and not the metadata.
import i18next from "i18next";
import type { QueryClient } from "@tanstack/react-query";
import { HELD, send } from "../../lib/query-client";
import { registerVerb } from "../../lib/verbs";

/** What both journey operations answer, as the contract declares it. */
type JourneyAnswer = {
  queued: boolean;
  runUid: string | null;
};

/** Which sentence a verb says, keyed by what it is. */
type Verb = "requeue" | "rescrape";

/**
 * Asks the backend to resume one tunnel, one way or the other.
 *
 * WHAT IT SAYS COMES FROM WHAT CAME BACK. An ask that arrives while the machine
 * is working is QUEUED — « en file — pipeline en cours », DOIT-4's own words —
 * and never « occupé »; the backend answers 409 for that case and
 * NE-DOIT-PAS-3 forbids the interface showing it, which is why the contract
 * declares a queued 202 and the difference is a demand rather than a shape to
 * reconcile.
 *
 * THE STAGES ARE RE-READ AFTERWARDS, because that is where the operator sees
 * the tunnel resume: the producer takes its stages from the query cache, so an
 * answer nobody invalidates leaves the sheet showing the passage that was
 * blocked. §20's « reprend là où il s'est arrêté » is a thing one WATCHES, not
 * a thing one is told.
 *
 * Args:
 *     verb: Which of the two was asked for.
 *     subject: The journey, as this interface knows it — by the medium's TITLE.
 *         The backend wants an info hash; that is a demand on the register, not
 *         something to invent here.
 */
async function resumeJourney(
  client: QueryClient,
  verb: Verb,
  subject: string,
): Promise<void> {
  const say = (key: string) => i18next.t(`verbs.journey.${key}`);
  const address =
    `/api/acquisition/journeys/${encodeURIComponent(subject)}/` +
    (verb === "requeue" ? "requeue" : "rescrape");
  try {
    const answered = await send<JourneyAnswer>("POST", address);
    if (answered === HELD) {
      window.__toast?.show({ message: say(verb + "Held") });
      return;
    }
    const outcome = answered as JourneyAnswer | undefined;
    window.__toast?.show({
      message: outcome?.queued ? say(verb + "Queued") : say(verb + "Asked"),
    });
    // THE SHEET IS RE-READ, so the stages the operator is looking at move —
    // and it is a REFETCH rather than an invalidation, which is not a
    // preference. A panel producer is a function from the cache to a
    // descriptor, not a component: NOTHING SUBSCRIBES to this key while the
    // panel is open. `invalidateQueries` refetches what is being observed and
    // merely marks the rest stale, so the cache kept the stages the operator
    // was already looking at and the sheet never moved. Measured: the rule read
    // the same five stages before and after a call that had demonstrably
    // happened.
    await client.refetchQueries({
      queryKey: ["/api/acquisition/journeys", subject],
    });
  } catch {
    // SAID AS A REFUSAL. Swallowing it would leave the operator watching a
    // tunnel that never resumed, with no reason given.
    window.__toast?.show({ message: say(verb + "Refused") });
  }
}

/**
 * Declares the two verbs to the tap registry.
 *
 * THE CLIENT IS HANDED IN, exactly as `installFollowActions` takes it: these
 * verbs are called from a tap and not from a component, so there is no hook to
 * read it from, and a module-level singleton would be a second way to reach the
 * cache in an application that already has one.
 *
 * @param client The cache the surfaces read.
 */
export function installJourneyVerbs(client: QueryClient): void {
  registerVerb("journey-requeue", (subject) => {
    void resumeJourney(client, "requeue", subject);
  });
  registerVerb("journey-rescrape", (subject) => {
    void resumeJourney(client, "rescrape", subject);
  });
}
