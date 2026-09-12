// The medium's own verb — « Re-scraper les métadonnées » (B-383).
//
// IT SAID A SENTENCE AND SENT NOTHING. Two surfaces offer it — the follow
// panel's action list (`follow-actions.ts`) and the media sheet's own action
// row (`media-details.tsx`) — and both answered a canned sentence over an
// unchanged world: the panel's through the dying engine's `data-rescrape`
// branch, the sheet's through a `data-toast` attribute. « Said, not done » is
// NE-DOIT-PAS-1, a sentence that can be right about nothing.
//
// THE OPERATION IS NEW, and D7 is why it may be. The contract declares what the
// interface REQUIRES; the verb exists on a validated surface, so the interface
// requires an operation for it, and `POST /api/media/{provider}/{providerId}/rescrape`
// is that declaration. It is a demand on the backend, recorded as every other
// divergence is.
//
// THE SUBJECT IS ADDRESSED BY IDENTITY, never by title. A sheet is reachable at
// `/media/:provider/:id` (DOIT-11) and twenty identities in this fixture are
// carried by two title keys at once, so an operation keyed by title would ask
// about whichever key happened to be matched first (B-088). The callers hold a
// TITLE, so the crossing happens here, through the same reader
// `history-bridge.ts` already crosses with.
//
// THE ENGINE LOSES A BRANCH BY IT (D5). `legacy.js`'s `data-rescrape` branch is
// deleted, not duplicated: a verb still living there moves onto `lib/verbs.ts`
// the day it gains a behaviour, and the size ledger is re-recorded downward.
import i18next from "i18next";
import type { QueryClient } from "@tanstack/react-query";
import { HELD, send } from "../../lib/query-client";
import { registerVerb } from "../../lib/verbs";

/** What the operation answers, as the contract declares it. */
type MediaRescrape = {
  provider: string;
  providerId: string;
  queued: boolean;
  runUid: string | null;
};

/* THE ASKS IN FLIGHT, by address. Module state and not a React ref, for
   `season-grab.ts`'s measured reason: the same medium is reachable from two
   surfaces, and a guard held by one component would not see a press on the
   other. A second press while the first is out is the same intention made
   again, and it is answered with silence rather than with a refusal. */
const inFlight = new Set<string>();

/**
 * Asks the providers for one medium's metadata again.
 *
 * WHAT IT SAYS COMES FROM WHAT CAME BACK, never from what was hoped for. An ask
 * that arrives while the machine is working is QUEUED — DOIT-4's own words, « en
 * file — pipeline en cours », never « occupé » — and an ask that starts now says
 * so. Offline is neither: `send` answers `HELD` when the mutation waits for a
 * network that is not there, and the interface says it is held.
 *
 * THE SHEET IS RE-READ AFTERWARDS, because that is where the effect is visible:
 * `metadataRefreshedAt` is what the medium's own « Métadonnées rafraîchies » row
 * draws, and an answer nobody invalidates leaves that row saying what it said
 * before the act.
 *
 * Args:
 *     client: The cache both surfaces read.
 *     title: The medium, as the surfaces know it — by title.
 */
async function rescrapeMedia(client: QueryClient, title: string): Promise<void> {
  const say = (key: string, values?: Record<string, unknown>) =>
    i18next.t(`verbs.media.${key}`, values ?? {});
  // §11's explicit case, honoured rather than worked around: a medium with no
  // provider identity has no sheet and no address, so there is nothing to ask
  // about. It is SAID — a verb that answered silence would be the defect this
  // file exists to end, wearing a different cause.
  const identity = window.__referentiel.addressIdsFor(title.normalize("NFC"));
  if (identity === null) {
    window.__toast?.show({ message: say("rescrapeUnidentified", { title }) });
    return;
  }
  const address =
    `/api/media/${encodeURIComponent(identity.provider)}/` +
    `${encodeURIComponent(identity.id)}/rescrape`;
  if (inFlight.has(address)) return;
  inFlight.add(address);
  try {
    const answered = await send<MediaRescrape>("POST", address);
    if (answered === HELD) {
      window.__toast?.show({ message: say("rescrapeHeld", { title }) });
      return;
    }
    const outcome = answered as MediaRescrape | undefined;
    window.__toast?.show({
      message: say(outcome?.queued ? "rescrapeQueued" : "rescrapeAsked", { title }),
    });
    // THE SHEET, AND THE SHEET ALONE. The seasons read at the same address is a
    // different key and the act moves nothing in it; refetching it would be a
    // second request nobody's surface is waiting for.
    await client.refetchQueries({
      queryKey: ["/api/media", identity.provider, identity.id],
      exact: true,
    });
    // AND THE OPEN PANEL IS PUT BACK FROM WHAT CAME. A panel producer is a
    // function from the cache to a descriptor, not a component: nothing
    // subscribes to this key while the panel is open, so a refetch that moves
    // the cache tells everyone except the person who acted.
    window.__panel?.redraw();
  } catch {
    // SAID AS A REFUSAL. Swallowing it leaves the operator looking at a medium
    // whose metadata never moved, with no reason given (NE-DOIT-PAS-5).
    window.__toast?.show({ message: say("rescrapeRefused", { title }) });
  } finally {
    inFlight.delete(address);
  }
}

/**
 * Declares the medium's verbs to the tap registry.
 *
 * THE CLIENT IS HANDED IN, exactly as `installJourneyVerbs` takes it: these are
 * called from a tap and not from a component, so there is no hook to read the
 * cache from, and a module-level singleton would be a second way to reach a
 * cache the application already has one door to.
 *
 * Args:
 *     client: The cache the surfaces read.
 */
export function installMediaVerbs(client: QueryClient): void {
  registerVerb("rescrape", (title) => {
    void rescrapeMedia(client, title);
  });
}
