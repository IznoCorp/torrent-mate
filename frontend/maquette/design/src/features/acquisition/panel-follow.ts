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
// a line count — the answer this repository has now taken three times, and
// the one `scripts/frontend_size_ledger.py` states as its own reason for
// being a file of its own.
//
// THE SEASONS BLOCK IS ALREADY REACT and needs nothing:
// `features/media/panel-seasons.tsx` registers `"saisons"`. What this producer
// does is BUILD the descriptor that names it. The name crosses through
// `ui/panel/contract`'s open union, which is not a feature import — invariant 7
// holds.
import i18next from "i18next";
import { heldIdentity } from "../../lib/held-identity";
import { sharedQueryClient } from "../../lib/query-client";
import { panel } from "../../lib/shell-doors";
import { store } from "../../lib/store-access";
import { registerProducer, type PanelCache, type PanelDescriptor } from "../../ui/panel/contract";
import { followFacts } from "./follow-facts";
import { primaryAction, secondaryActions } from "./follow-actions";
import { followsQuery, incompleteShowsQuery } from "./queries";

/* The one wait for an identity in progress, stopped by the next one. */
let cancelWaiting: (() => void) | null = null;

/**
 * Puts the follow panel back once a read carrying the medium's identity lands.
 *
 * A PRODUCER READS THE CACHE ONCE, and whether a medium has a sheet is read
 * from its identity — which, for a medium nobody follows, only a LIST read
 * carries. Opened cold (a typed address, a reload), the panel is produced the
 * moment the follows land, and the list holding the medium can land after
 * that: without this, « Voir la fiche » stays missing until the panel is
 * reopened, although the cache holds everything it needs a beat later.
 *
 * THE ROW IS REFRESHED IN PLACE through the panel's own redraw, which runs the
 * producer onto the entry already standing — no history entry is added. It
 * redraws only while the panel on screen is still this one, and it stops
 * waiting as soon as it is not: a panel about another subject owns its own
 * wait, and a closed panel has nothing to put back.
 *
 * Args:
 *     title: The medium the panel is about.
 */
function redrawOnIdentityArrival(title: string): void {
  cancelWaiting?.();
  cancelWaiting = null;
  if (sharedQueryClient === undefined) return;
  const address = "follow:" + title;
  const cancel = sharedQueryClient.getQueryCache().subscribe((event) => {
    if (event.type !== "updated" || event.query.state.data === undefined) return;
    const shown = store.read().state.panelDescriptor as PanelDescriptor | undefined;
    const shownNow = panel?.isOpen() === true && shown?.address === address;
    if (shownNow && heldIdentity(title) === null) return;
    cancel();
    if (cancelWaiting === cancel) cancelWaiting = null;
    if (shownNow) panel?.redraw();
  });
  cancelWaiting = cancel;
}

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
  if (!facts.hasSheet) redrawOnIdentityArrival(title);
  const translate = i18next.t.bind(i18next);
  const { follow, isFilm, seasons, fraction } = facts;
  const reference = window.__referentiel;
  const kind = translate(isFilm ? "panels.follow.film" : "panels.follow.series");
  return {
    address: "follow:" + title,
    title: follow.t,
    poster: { t: follow.t, k: follow.k, source: follow.poster ?? heldIdentity(title)?.poster },
    meta:
      `${follow.y ? String(follow.y) + " · " : ""}${kind}` +
      `${fraction ? " · " + fraction + translate("panels.follow.episodesSuffix") : ""}`,
    puce: [reference.ST_TONE[follow.st as string], reference.stLabel(follow)],
    blocs: [
      { type: "actions", actions: [primaryAction(facts)] },
      seasons.length
        ? { type: "saisons", follow, seasons }
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
  // THE FOLLOWS, AND THE READ THAT CARRIES THE IDENTITY OF A MEDIUM NOBODY
  // FOLLOWS. Without the second, a panel typed onto any page but the
  // Médiathèque waits for an identity nobody asks for: no « Voir la fiche »,
  // owned cells from a threshold, initials for a poster (R176).
  needs: [followsQuery, incompleteShowsQuery],
});
