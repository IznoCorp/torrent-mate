// WHAT A FOLLOW PANEL OFFERS, and in what order.
//
// Split out of the producer on a SUBJECT: `follow-facts.ts` answers what is
// TRUE about a medium, and this answers what one may DO about it. Every entry
// below is derived from those facts and from nothing else.
//
// NO VERB IS ADDED HERE. « Récupérer cette saison », « Remettre en file » and
// « Re-scraper » from the journey are **L21's**, on this very panel; what this
// file does is offer exactly what the engine's producer offered.
import i18next from "i18next";
import type { Action } from "../../ui/panel/contract";
import type { FollowFacts } from "./follow-facts";

const icons = () => window.__referentiel.icons;
const say = (key: string) => i18next.t(`panels.follow.${key}`);

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
  if (facts.toResolve)
    return {
      text: say("resolve"), icone: icons().play, ton: "primary",
      target: { resolve: follow.t },
    };
  if (facts.toTake)
    return {
      text: say("takeNow"), icone: icons().play, ton: "primary",
      target: { take: follow.t },
    };
  if (facts.incomplete)
    return {
      text: say("complete"), icone: icons().play, ton: "primary",
      target: { complete: follow.t },
    };
  if (facts.isFollowed)
    return {
      text: say(follow.st === "to_grab" ? "takeNow" : "searchNow"),
      icone: icons().play, ton: "primary",
      target: { sheetprim: `${follow.t}|${follow.st}` },
    };
  if (facts.hasSheet)
    return {
      text: say("seeSheet"), icone: icons().eye, ton: "primary",
      target: { mediasheet: follow.t },
    };
  // AN UNIDENTIFIED RELEASE HAS NO SHEET. Offering to open one is the same
  // broken promise as a poster that leads nowhere, so the panel leads to the
  // journey instead — which exists for every acquisition.
  return {
    text: say("seeJourney"), icone: icons().refresh, ton: "primary",
    target: { journey: follow.t },
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
    // « Voir la fiche » is reachable whenever a sheet exists. It is omitted only
    // when it is ALREADY the primary action, which happens for a medium that is
    // owned and whole.
    facts.hasSheet && (facts.toResolve || facts.toTake || facts.incomplete || facts.isFollowed)
      ? { text: say("seeSheet"), icone: icons().eye, target: { mediasheet: follow.t } }
      : null,
    { text: say("seeJourney"), icone: icons().refresh, target: { journey: follow.t } },
    // Chasing a release only means something for a medium still being acquired.
    // Offered on a complete one it is a button that can only disappoint.
    beingAcquired
      ? { text: say("otherRelease"), icone: icons().search, target: { releases: follow.t } }
      : null,
    beingAcquired
      ? { text: say("qualityProfile"), icone: icons().sort, target: { profile: follow.t } }
      : null,
    facts.inLibrary
      ? { text: say("rescrape"), icone: icons().refresh, target: { rescrape: follow.t } }
      : null,
    // Pausing or dropping a follow requires a follow. An incomplete series in
    // the library is not one: nothing is watching it, so there is nothing to
    // stop.
    facts.isFollowed
      ? {
          text: say(isFilm ? "stopSearchingFilm" : "pauseSeries"),
          icone: icons().x, target: { pause: follow.t },
        }
      : null,
    facts.isFollowed
      ? {
          text: say(isFilm ? "removeFilm" : "removeSeries"),
          icone: icons().trash, ton: "danger", target: { remove: follow.t },
        }
      : null,
    facts.inLibrary
      ? {
          text: say("deleteFromLibrary"), icone: icons().trash, ton: "danger",
          target: { del: follow.t },
        }
      : null,
  ];
}
