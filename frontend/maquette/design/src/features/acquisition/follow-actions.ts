// WHAT A FOLLOW PANEL OFFERS, and in what order.
//
// Split out of the producer on a SUBJECT: `follow-facts.ts` answers what is
// TRUE about a medium, and this answers what one may DO about it. Every entry
// below is derived from those facts and from nothing else.
//
// NO VERB IS ADDED HERE. « Récupérer cette saison », « Remettre en file » and
// « Re-scraper » from the journey belong to the lot that wires the tunnel's
// verbs; what this file does is offer exactly what the engine's producer did.
import { icons } from "../../lib/shell-doors";
import i18next from "i18next";
import type { Action } from "../../ui/panel/contract";
import type { FollowFacts } from "./follow-facts";

const say = (key: string) => i18next.t(`panels.follow.${key}`);

// The status of a follow whose grab is running.
const BEING_ACQUIRED = "acquiring";

/**
 * The ONE act the panel leads with.
 *
 * IT ANSWERS THE MEDIUM'S STATE, not the screen it was reached from — which is
 * why it is read from the facts and never passed in. Blocked outranks
 * everything: nothing else can happen until it is resolved. Then what can be
 * grabbed, then what is incomplete, then what is merely watched. A medium that
 * is owned and whole has nothing left to chase, so the panel leads to its sheet
 * rather than offering a search that would find nothing.
 *
 * Args:
 *     facts: What is true about the medium.
 *
 * Returns:
 *     The primary action.
 */
export function primaryAction(facts: FollowFacts): Action {
  const { follow } = facts;
  // WHAT « À TRAITER » ASKS OF THIS CARD comes first, and never an identity
  // pick: a match is confirmed, a step that cannot finish is relaunched.
  if (facts.plexMatch)
    return {
      text: say("plexConfirm"), icone: icons.check, ton: "primary",
      target: { "plex-confirm": follow.title },
    };
  // A CLOSED TUNNEL ASKS TO BE READ, once (Q8, Q9): « Marquer comme vu » is the
  // card's own act, in its panel and never as a « × » on it (DECIDED 2).
  if (facts.closure !== null)
    return {
      text: i18next.t("panels.journey.markSeen"), icone: icons.check, ton: "primary",
      target: { "closure-seen": facts.closure },
    };
  if (facts.tunnelError)
    return {
      text: say("requeue"), icone: icons.refresh, ton: "primary",
      target: { "journey-requeue": follow.title },
    };
  if (facts.toResolve)
    return {
      text: say("resolve"), icone: icons.play, ton: "primary",
      target: { resolution: follow.title },
    };
  if (facts.toTake)
    return {
      text: say("takeNow"), icone: icons.play, ton: "primary",
      target: { take: follow.title },
    };
  if (facts.incomplete)
    return {
      text: say("complete"), icone: icons.play, ton: "primary",
      target: { complete: follow.title },
    };
  // A GRAB ALREADY RUNNING IS NOT SEARCHED AGAIN: the follow leads to the
  // journey of what runs — a whole season's recovery first (Q14 = A).
  if (facts.isFollowed && follow.status === BEING_ACQUIRED)
    return {
      text: say("seeJourney"), icone: icons.refresh, ton: "primary",
      target: { journey: facts.journey },
    };
  if (facts.isFollowed)
    return {
      text: say(follow.status === "to_grab" ? "takeNow" : "searchNow"),
      icone: icons.play, ton: "primary",
      target: { sheetprim: `${follow.title}|${follow.status}` },
    };
  if (facts.hasSheet)
    return {
      text: say("seeSheet"), icone: icons.eye, ton: "primary",
      target: { mediasheet: follow.title },
    };
  // AN UNIDENTIFIED RELEASE HAS NO SHEET, and this is the branch it keeps: a
  // FOLLOW without one is refused at its creation now (B-366), but a queued
  // folder nothing has identified yet is drawn through these same facts, and
  // offering it a sheet would be the broken promise B-313 is about. It leads to
  // the journey, which every acquisition has.
  return {
    text: say("seeJourney"), icone: icons.refresh, ton: "primary",
    target: { journey: follow.title },
  };
}

/**
 * Everything else the panel offers, in the order it offers it.
 *
 * Args:
 *     facts: What is true about the medium.
 *
 * Returns:
 *     The secondary actions, absences included as nulls — the panel's own
 *     contract tolerates them in place, which is what lets each line state its
 *     condition beside itself.
 */
export function secondaryActions(facts: FollowFacts): (Action | null)[] {
  const { follow, isFilm } = facts;
  const beingAcquired = facts.isFollowed || facts.incomplete || facts.toTake;
  return [
    // « Suivre », PROPOSED on an arrived series nobody follows (ruling 1).
    facts.followOffer
      ? {
          text: say("offerFollow"), icone: icons.plus, ton: "primary",
          target: { follow: follow.title, "follow-ids": JSON.stringify(facts.followOffer) },
        }
      : null,
    // The second answer « À traiter » offers at the card's foot.
    facts.plexMatch
      ? { text: say("plexCorrect"), icone: icons.search, target: { "plex-correct": follow.title } }
      : null,
    facts.tunnelError
      ? { text: say("abandon"), icone: icons.trash, ton: "danger", target: { "journey-abandon": follow.title } }
      : null,
    // The second foot « Mis de côté » offers.
    facts.setAside
      ? { text: say("deleteStaged"), icone: icons.trash, ton: "danger", target: { "staging-delete": follow.title } }
      : null,
    // « Voir la fiche » is reachable whenever a sheet exists. It is omitted only
    // when it is ALREADY the primary action, which happens for a medium that is
    // owned and whole.
    facts.hasSheet && (facts.closure !== null || facts.plexMatch || facts.tunnelError || facts.toResolve || facts.toTake || facts.incomplete || facts.isFollowed)
      ? { text: say("seeSheet"), icone: icons.eye, target: { mediasheet: follow.title } }
      : null,
    // « Voir le parcours » is guarded exactly as « Voir la fiche » is, and for
    // the same reason: it is omitted only when it is ALREADY the primary
    // action, which happens for a medium with no sheet that nothing is
    // chasing. Without this condition the panel drew the same words twice and
    // gave the reader two buttons he could not tell apart (B-313).
    (facts.hasSheet || facts.toResolve || facts.toTake || facts.incomplete || facts.isFollowed)
      && primaryAction(facts).target?.journey === undefined
      ? { text: say("seeJourney"), icone: icons.refresh, target: { journey: facts.journey } }
      : null,
    // Chasing a release only means something for a medium still being acquired.
    // Offered on a complete one it is a button that can only disappoint.
    beingAcquired
      ? { text: say("otherRelease"), icone: icons.search, target: { releases: follow.title } }
      : null,
    beingAcquired
      ? { text: say("qualityProfile"), icone: icons.sort, target: { profile: follow.title } }
      : null,
    facts.inLibrary
      ? { text: say("rescrape"), icone: icons.refresh, target: { rescrape: follow.title } }
      : null,
    // Pausing or dropping a follow requires a follow. An incomplete series in
    // the library is not one: nothing is watching it, so there is nothing to
    // stop.
    facts.isFollowed
      ? {
          text: say(isFilm ? "stopSearchingFilm" : "pauseSeries"),
          icone: icons.x, target: { pause: follow.title },
        }
      : null,
    facts.isFollowed
      ? {
          text: say(isFilm ? "removeFilm" : "removeSeries"),
          icone: icons.trash, ton: "danger", target: { remove: follow.title },
        }
      : null,
    facts.inLibrary
      ? {
          text: say("deleteFromLibrary"), icone: icons.trash, ton: "danger",
          target: { del: follow.title },
        }
      : null,
  ];
}
