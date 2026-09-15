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
import { heldIdentity, providerAddress } from "../../lib/held-identity";
import { membershipQuery } from "../../lib/membership";
import { sharedQueryClient } from "../../lib/query-client";
import { panel } from "../../lib/shell-doors";
import { seasonsQuery } from "../../lib/season-rows";
import { store } from "../../lib/store-access";
import { registerProducer, type PanelCache, type PanelDescriptor } from "../../ui/panel/contract";
import { followFacts, type Follow } from "./follow-facts";
import { primaryAction, secondaryActions } from "./follow-actions";
import { followsQuery, incompleteShowsQuery } from "./queries";
import { STATUS_TONE, followStatusLabel } from "./follow-vocabulary";

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
    const pending = shownNow ? pendingSeasons(title) : null;
    if (pending !== null && sharedQueryClient !== undefined) {
      void sharedQueryClient.prefetchQuery(pending);
      return;
    }
    cancel();
    if (cancelWaiting === cancel) cancelWaiting = null;
    if (shownNow) panel?.redraw();
  });
  cancelWaiting = cancel;
}

/**
 * The seasons read of a medium, when its identity is known and the read is out.
 *
 * Args:
 *     title: The medium.
 *
 * Returns:
 *     The query to ask for, or null when nothing is out.
 */
function pendingSeasons(title: string) {
  if (sharedQueryClient === undefined) return null;
  const followed = sharedQueryClient.getQueryData<Follow[]>(followsQuery.queryKey) ?? [];
  const ids = followed.find((one) => one.title === title)?.ids ?? heldIdentity(title)?.ids;
  const address = providerAddress(ids);
  if (address === null) return null;
  const query = seasonsQuery(address.provider, address.id);
  return sharedQueryClient.getQueryData(query.queryKey) === undefined ? query : null;
}

/**
 * Asks for a medium's seasons, and redraws the panel about it when they land.
 *
 * THE IDENTITY IS KNOWN ONLY ONCE THE FOLLOWS HAVE LANDED, so the seasons read
 * cannot be one of the kind's declared needs: it is asked here, the moment the
 * producer knows the address, and the panel is put back in place when it
 * answers — the same redraw an identity's arrival uses, onto the entry already
 * standing.
 *
 * Args:
 *     title: The medium.
 */
function askForSeasons(title: string): void {
  const query = pendingSeasons(title);
  if (query === null || sharedQueryClient === undefined) return;
  void sharedQueryClient.prefetchQuery(query);
  redrawOnIdentityArrival(title);
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
  else if (facts.seasonsPending) askForSeasons(title);
  const translate = i18next.t.bind(i18next);
  const { follow, isFilm, seasons, fraction } = facts;
  const kind = translate(isFilm ? "panels.follow.film" : "panels.follow.series");
  return {
    address: "follow:" + title,
    title: follow.title,
    poster: { t: follow.title, k: follow.kind, source: follow.poster ?? heldIdentity(title)?.poster },
    meta:
      `${follow.year ? String(follow.year) + " · " : ""}${kind}` +
      `${fraction ? " · " + fraction + translate("panels.follow.episodesSuffix") : ""}`,
    puce: [STATUS_TONE[follow.status as string], followStatusLabel(follow)],
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
  // AND WHAT THE LIBRARY HOLDS OF THIS VERY TITLE: the membership read is
  // exact and per subject, so the kind's needs are a function of it — which
  // takes the follow panel out of the boot's prefill by construction, and its
  // first open about any title goes down the deferred path.
  needs: (subject) => [followsQuery, incompleteShowsQuery, membershipQuery(subject)],
});
