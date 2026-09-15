// THE PAGE SWITCH — how a navigation is written into history, and the facts
// about the walk that decide which write it is.
//
// ── BACK FOLLOWS THE PATH WALKED ────────────────────────────────────────────
// Only the LAYERS used to push history, so the back gesture closed a sheet and
// then, with nothing left to close, left the application — losing every page
// the operator had walked through. A tab is a place one navigates to; it
// belongs in the history exactly as a screen does.
//
// Every navigation now pushes where it came FROM, so popping restores it.
// Driving the prototype from the harness does not: `__go` is not a journey, and
// a measurement must not depend on how many states ran before it.
//
// At the bottom of the stack a GUARD entry sits, so a back at the root has
// something to pop and the application is never left by surprise. Popping it
// says so and puts it back; a second back within five seconds does not put it
// back, and lets the stack run out — which is what closes an installed app on
// Android. A page cannot close itself; exhausting its history is the only thing
// it can honestly do.
//
// ── THE ADDRESS CARRIES THE STATE (DOIT-10) ─────────────────────────────────
// « Chaque détail a son URL » is a rule of the constitution: a reload lands
// where one was, and any screen can be sent to anyone. What is decided HERE is
// navigation logic proper — WHEN to record an arrival, what state to carry on
// the entry. What a place is CALLED is `lib/addresses.ts`'s, and only what
// differs from the opening state is written, so the common case has a clean URL.
//
// THE FACTS ARE ONE EXPORTED OBJECT, not private bindings, because three
// readers write them: the writers below, the ladder's handler in `layers.ts`
// when a Back lands, and the boot on arrival. An importer can write a property;
// it can never write a binding.
import { addressSeam } from "../lib/addresses";
import { navigationState } from "../lib/navigation-entry";
import { bridge, fillReplaceAddressDoor } from "../lib/shell-doors";
import { stackedSurfaces } from "../lib/stacked-surface";
import { store } from "../lib/store-access";

/** How long an armed exit waits for the second Back, in milliseconds. */
export const BACK_WINDOW = 5000;

export const walk = {
  /* A named state is DRIVEN, not walked: every writer of history checks this
     and writes nothing while it is raised. */
  driven: false,
  /* WHETHER A HOME PAGE ENTRY LIES AT OR BENEATH THE CURRENT ONE, and it
     FOLLOWS THE WRITES: every verb that lays a home entry down raises it, and a
     write that was refused raises nothing. The page-switch verbs read it:
     stepping BACK onto a floor that was never laid lands on the exit guard
     instead, which arms the exit on an arrival the reader never made as a back
     — and one gesture later the document is gone. Only an address nobody
     serves has no floor; it is kept exactly as typed, so nothing is put under
     it.

     DERIVED FROM THE ARRIVAL it answered for the stack the boot had planned
     rather than the one the document ended up with, and it went stale the
     moment a later gesture laid a floor the boot had not: off an unserved
     address, five tab round trips read a history depth of fourteen and twelve
     Backs before the exit armed, where an ordinary arrival reads four and one.

     It goes back DOWN in one place only — a Back that lands under the floor,
     which no served arrival can reach — and the asymmetry is deliberate: a
     stale true spends the exit guard, a stale false merely writes an entry
     that could have been stepped onto.

     False until a write raises it, which is safe rather than conservative:
     nothing in the interface can switch page before the boot has run. */
  homeFloorExists: false,
  /* WHETHER THE BOOT PUT NOTHING UNDER THE ARRIVAL, which is what an address
     nobody serves is owed: it is kept exactly as typed. In such a session the
     floor is not the boot's — it is wherever a later switch laid one — so it
     can be BACKED OFF, and the flag above has to come down when it is. False in
     every session that arrived at an address the model serves, where the floor
     is the entry directly above the exit guard and nothing reaches beneath it. */
  arrivalWithoutFloor: false,
  /* When the exit guard was popped and armed, or 0. Published for the rules as
     `window.armedExit`: the address alone says nothing about the guard. */
  armedExit: 0,
  /* WHAT RUNS ONCE THE TRAVERSAL HAS LANDED, and there is at most one of it. A
     caller that rewinds to an entry in order to write ON it cannot write in the
     same task: the traversal is asynchronous, so the write would land first and
     the pop would undo it. So the write is left here and the ladder's latch
     fires it — the one moment at which the destination entry is certainly the
     current one.

     Armed AFTER the traversal is issued, never before, so a traversal that
     threw leaves no continuation waiting to fire on somebody else's unwind. */
  afterUnwind: null as null | (() => boolean),
};

/**
 * Runs `run` as a DRIVEN state: no writer of history writes while it runs.
 *
 * The harness calls this verb rather than holding the flag itself.
 *
 * Args:
 *     run: What builds the state.
 */
export function drivenWithoutHistory(run: () => void): void {
  walk.driven = true;
  try {
    run();
  } finally {
    walk.driven = false;
  }
}

const currentState = () => store.read().state;

/* B-026: a navigation write that fails must not fail silently — the URL and the
   interface would then disagree with nothing on record. Every writer here raises
   `__navEchec`; it is cleared only at load, so a measurement that ran before
   leaves no residue. It catches a write that DID fail, never a wrong one. */
window.__navEchec = false;

/**
 * Records where the operator has ARRIVED.
 *
 * The pushed entry carries the state one is now in, so it is the CURRENT entry
 * and popping it lands on the previous arrival. Pushing the state being left
 * instead puts the history one step ahead of the interface, and every back
 * then overshoots by one — measured, and it is the mistake this ordering exists
 * to avoid. A write that fails must not fail silently (B-026): the URL and the
 * interface would then disagree with nothing on record.
 *
 * Returns:
 *     Whether the entry was really written. The floor flag follows the WRITES,
 *     so a caller that lays a home entry down has to be able to tell a write
 *     that went through from one that was refused — a flag raised over an entry
 *     nobody wrote is the stale true that spends the guard. Driving the
 *     interface writes nothing, and answers so.
 */
export function recordPath(): boolean {
  if (walk.driven) return false;
  try {
    bridge.record(navigationState(), addressSeam.compose(currentState()));
    return true;
  } catch (error) {
    // ENGLISH, and not in `fr.json`: a console message is a tool message.
    console.error("recordPath: writing the navigation failed", error);
    window.__navEchec = true;
    return false;
  }
}

/**
 * Records that the surface is being looked at ANOTHER WAY.
 *
 * § 16 rule 1 splits every navigation in two: opening a surface is an arrival
 * and stacks, adjusting one is a setting and replaces the entry it is on. A
 * filter, an inner tab, a sort or a lens recorded as an arrival is what makes
 * Retour undo a sort where the reader meant to leave the screen — the single
 * gesture that tells a web application from a native one. The address is still
 * WRITTEN: a setting belongs in the URL, it simply does not belong in the path
 * one walked.
 *
 * Returns:
 *     Whether the entry was really rewritten, for the same reason `recordPath`
 *     answers: a replace can hand the reader a home entry too, and the floor
 *     flag may only follow a write that happened.
 */
export function replacePath(): boolean {
  if (walk.driven) return false;
  try {
    bridge.replace(navigationState(), addressSeam.compose(currentState()));
    return true;
  } catch (error) {
    console.error("replacePath: writing the navigation failed", error);
    window.__navEchec = true;
    return false;
  }
}

/**
 * Settles history for a top-level page switch the interface has ALREADY applied.
 *
 * § 16 rule 2: the main pages are destinations, not steps of a journey, so
 * visiting them stacks nothing. Under any of them the stack is the entry page
 * plus at most one, which is what makes Retour from anywhere land on the entry
 * page and Retour from the entry page arm the exit guard.
 *
 * Three verbs, and which applies is decided by the page one came FROM:
 * · from the entry page, the destination is PUSHED — the floor has to stay
 *   beneath it, and replacing would send the first Retour into the guard;
 * · to the entry page, the floor is already one entry down, so it is stepped
 *   BACK onto: pushing or replacing would leave two of it, and a Retour that
 *   changes nothing;
 * · between two other pages, the top of the stack is REPLACED.
 * Tapping the page one is already on replaces too — it is not an arrival.
 *
 * A LAYER'S ENTRY ON TOP is a shape this does not settle: `switchPageFromLayer`
 * does, and the two `data-*` sites that can be tapped over a layer route there.
 *
 * Args:
 *     leaving: The page id the interface was on before the caller rendered the
 *         destination — read at the call site because the store already holds
 *         the destination by the time history is settled.
 */
export function switchPage(leaving: string): void {
  if (walk.driven) return;
  const arriving = currentState().page;
  /* A LAYER'S ENTRY ON TOP, reached from a site that does not route to
     `switchPageFromLayer` — which today means the tab bar, and only through
     `node.click()`: hit-tested at the design's own viewport, every layer kind
     covers the centre of every tab button, so no finger arrives here with a
     layer up. The arm stays: it keeps the stack honest for the next surface
     that offers a page switch over a layer. */
  const onLayer = Boolean(history.state && history.state.layer);
  if (arriving === leaving) {
    replacePath();
    return;
  }
  if (leaving === addressSeam.homePage) {
    /* PUSHED FROM HOME, so the entry this one is laid on IS the floor, whatever
       the boot did or did not lay. */
    if (recordPath()) walk.homeFloorExists = true;
    return;
  }
  if (arriving === addressSeam.homePage && !onLayer) {
    /* NO FLOOR, NO STEP BACK. The entry one down is then the exit guard, and
       stepping onto it arms the exit from an arrival nobody made as a back. The
       switch RECORDS instead — the address as typed stays one back away — AND
       THE ENTRY IT WRITES IS A HOME ENTRY, so the next switch away from home
       stacks on a floor. Left false here, every later switch took this branch
       again and the depth grew with every tab tapped. */
    if (!walk.homeFloorExists) {
      if (recordPath()) walk.homeFloorExists = true;
      return;
    }
    try {
      bridge.back();
    } catch (error) {
      console.error("switchPage: stepping back onto the entry page failed", error);
      window.__navEchec = true;
    }
    return;
  }
  /* Arriving home over a LAYER is the one way this last write hands the reader
     a home entry — the layer's own entry takes the destination. Between two
     other pages it swaps one page for another. */
  if (replacePath() && arriving === addressSeam.homePage)
    walk.homeFloorExists = true;
}

/**
 * Settles history for a page switch made FROM A LAYER.
 *
 * The drawer's entries and the account menu's « Profil et préférences » are the
 * page switches a finger can reach while something is open over the page.
 *
 * § 16 RULE 2 IS THE SAME RULE HERE, and it used to be read as « the destination
 * takes the layer's entry ». That leaves the ABANDONED page's entry sandwiched
 * underneath: from the médiathèque, the drawer's Acquisition gave [guard, acq,
 * médiathèque, acq] — two entries for one page, and three backs to leave. The
 * rule allows exactly two shapes: [guard, acq] arriving home, [guard, acq, page]
 * anywhere else.
 *
 * Only a TRAVERSAL can reach them, because no write reaches an entry below the
 * current one. So the walk goes down to the floor and the destination is
 * settled on it — once the pop has landed, because a write issued in this task
 * would be overtaken by the traversal and undone. The interface is already on
 * the destination, and the pop is swallowed by the ladder's latch, so nothing of
 * the floor is ever drawn.
 *
 * Args:
 *     leaving: The page id the interface was on before the caller rendered the
 *         destination.
 */
export function switchPageFromLayer(leaving: string): void {
  if (walk.driven) return;
  const homePage = addressSeam.homePage;
  /* No floor to walk down to: the entry under the layer is an arrival nobody
     serves, and the one below THAT is the exit guard. The layer's entry takes
     the destination — AND THAT WRITE CAN LAY THE FLOOR ITSELF: a switch made
     FROM home leaves a home entry beneath the destination, and a switch
     arriving home puts the reader on one. */
  if (!walk.homeFloorExists) {
    const written = replacePath();
    if (written && (leaving === homePage || currentState().page === homePage))
      walk.homeFloorExists = true;
    return;
  }
  /* WHAT THE LAYER STANDS ON, counted rather than ASSUMED. The layer's own
     entry plus the abandoned page's is what rule 2 leaves, and a surface inside
     a page that pushes its own arrival puts a third entry there (B-398): what
     stacks says so, or this is a guess again. */
  const entries = (leaving === homePage ? 1 : 2) + stackedSurfaces();
  bridge.rewind(entries);
  /* Armed after the traversal is issued: a pop cannot land before this task
     ends, so this is in time, and a rewind that threw arms nothing. Arriving
     home the floor IS the destination, so its address is settled in place;
     anywhere else the destination is an arrival and stacks on the floor. */
  walk.afterUnwind = currentState().page === homePage ? replacePath : recordPath;
}

// THE FEATURES REACH THE REPLACE THROUGH A DOOR, not by importing this module: a
// tab or a lens is a page setting every feature may write, and a module every
// feature imported would be the hub the fan-in arm refuses.
fillReplaceAddressDoor(replacePath);
