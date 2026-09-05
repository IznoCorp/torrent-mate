// The FOLLOW SHEET — the panel a long press on any medium raises.
//
// It is the largest of the ten producers and the one that names the most: a
// medium's state, its seasons, its place in the queue, and everything one may
// do about it. It lives with Acquisitions because that is what makes it change.
//
// CUT IN THREE, ON SUBJECTS: `follow-facts.ts` answers what is TRUE about the
// medium, `follow-actions.ts` what one may DO about it, and this file assembles
// the descriptor. A single module would have been over the 400-line ceiling
// this lot exists to respect, and the cut is taken on a subject rather than on
// a line count — the answer this repository has now taken three times.
//
// THE SEASONS BLOCK IS ALREADY REACT and needs nothing:
// `features/media/panel-seasons.tsx` registers `"saisons"`. What this producer
// does is BUILD the descriptor that names it. The name crosses through
// `ui/panel/contract`'s open union, which is not a feature import — invariant 7
// holds.
import i18next from "i18next";
import { registerProducer, type PanelCache, type PanelDescriptor } from "../../ui/panel/contract";
import { followFacts } from "./follow-facts";
import { primaryAction, secondaryActions } from "./follow-actions";
import { followsQuery } from "./queries";

/**
 * Builds a medium's follow panel.
 *
 * Args:
 *     title: The medium.
 *     cache: What the query cache holds.
 *
 * Returns:
 *     The descriptor, or null while the follows have not landed.
 */
function followPanel(title: string, cache: PanelCache): PanelDescriptor | null {
  const facts = followFacts(title, cache);
  if (facts === null) return null;
  const translate = i18next.t.bind(i18next);
  const { follow, isFilm, seasons, fraction } = facts;
  const reference = window.__referentiel;
  const kind = translate(isFilm ? "panels.follow.film" : "panels.follow.series");
  return {
    address: "follow:" + title,
    title: follow.t,
    poster: { t: follow.t, k: follow.k },
    meta:
      `${follow.y ? String(follow.y) + " · " : ""}${kind}` +
      `${fraction ? " · " + fraction + translate("panels.follow.episodesSuffix") : ""}`,
    puce: [reference.ST_TONE[follow.st as string], reference.stLabel(follow)],
    blocs: [
      { type: "actions", actions: [primaryAction(facts)] },
      seasons.length
        ? { type: "saisons", isFollowed: follow, seasons }
        : {
            type: "note",
            text: translate(isFilm
              ? "panels.follow.noEpisodeCatalogue"
              : "panels.follow.noSeasonData"),
          },
      { type: "actions", secondary: true, actions: secondaryActions(facts) },
      isFilm
        ? { type: "note", text: translate("panels.follow.filmLeavesNote") }
        : null,
    ],
  };
}

registerProducer("follow", {
  produce: followPanel,
  needs: [followsQuery],
});
