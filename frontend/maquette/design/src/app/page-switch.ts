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
import { navigationState, trailOf, TRAIL_KEY, type TrailStop } from "../lib/navigation-entry";
import { bridge, fillRecordAddressDoor, fillReplaceAddressDoor } from "../lib/shell-doors";
import { store } from "../lib/store-access";
import { standingIndex, standingTrail, writeTrail } from "./trail";

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
 * Args:
 *     trail: The trail the entry stands on, when the caller knows it; left
 *         out, the entry inherits the one it is written from.
 *
 * Returns:
 *     Whether the entry was really written. The floor flag follows the WRITES,
 *     so a caller that lays a home entry down has to be able to tell a write
 *     that went through from one that was refused — a flag raised over an entry
 *     nobody wrote is the stale true that spends the guard. Driving the
 *     interface writes nothing, and answers so.
 */
export function recordPath(trail?: TrailStop[]): boolean {
  if (walk.driven) return false;
  try {
    const state = trail ? { ...navigationState(), [TRAIL_KEY]: trail } : navigationState();
    bridge.record(state, addressSeam.compose(currentState()));
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
 * Args:
 *     trail: The trail the entry stands on, when the caller knows it; left
 *         out, the entry keeps its own.
 *
 * Returns:
 *     Whether the entry was really rewritten, for the same reason `recordPath`
 *     answers: a replace can hand the reader a home entry too, and the floor
 *     flag may only follow a write that happened.
 */
export function replacePath(trail?: TrailStop[]): boolean {
  if (walk.driven) return false;
  try {
    const state = trail ? { ...navigationState(), [TRAIL_KEY]: trail } : navigationState();
    bridge.replace(state, addressSeam.compose(currentState()));
    return true;
  } catch (error) {
    console.error("replacePath: writing the navigation failed", error);
    window.__navEchec = true;
    return false;
  }
}

/** How a page switch lands — decided by the verb, which knows where the tap came from. */
export type Landing =
  /* A BAR PAGE (or the entry page) chosen from the bar or the menu: the trail
     is unwound onto the floor, from any depth (§ 16 rule 2, Q11). */
  | "unwind"
  /* A LINK INSIDE A PAGE, a screen or a panel: it stacks on whatever it was
     tapped on (Q12), which is what a Retour then gives back. */
  | "stack"
  /* A MENU PAGE chosen from the menu or the account sheet: it stacks on the
     PAGE left, the layer and any rubric above it given back first (DECIDED 3). */
  | "stackOnPage";

/**
 * Writes the entries of a trail from one history index up (`writeTrail`).
 *
 * Reaching `from` from higher up is a traversal, and a write issued in the same
 * task would be overtaken by it: the writes are then left to the ladder's latch
 * (`walk.afterUnwind`), which fires them once the traversal has landed.
 *
 * Args:
 *     kept: The stops left as they are, floor first.
 *     pages: The pages to write above them, the arriving one last.
 *     from: The history index the first of `pages` is written at.
 */
function layTrail(kept: TrailStop[], pages: string[], from: number): void {
  const write = (): boolean => {
    const written = writeTrail(kept, pages, from);
    if (written) walk.homeFloorExists = true;
    return written;
  };
  const standing = standingIndex();
  if (standing <= from) {
    write();
    return;
  }
  try {
    bridge.rewind(standing - from);
    walk.afterUnwind = write;
  } catch (error) {
    // ENGLISH, and not in `fr.json`: a console message is a tool message.
    console.error("layTrail: stepping back down the trail failed", error);
    window.__navEchec = true;
  }
}

/**
 * Settles history for a top-level page switch the interface has ALREADY applied.
 *
 * § 16 AS AMENDED (#635, #643) and the rulings of 2026-09-29/30. Three facts
 * decide, and the entry's trail says where everything lies:
 * · a bar page (or the entry page) chosen from the bar or the menu UNWINDS the
 *   trail onto the floor — Retour from it lands on the entry page, and the
 *   entry page's own Retour arms the exit guard;
 * · a link inside a page, and a menu page from the menu, STACK — Retour gives
 *   back the page (or the screen, or the panel) it was tapped on;
 * · a page ALREADY on the trail is moved to its top, never stacked twice
 *   (DECIDED 1): Retour walks the path back with each page once, in the order
 *   it was last left, and with nothing left under a page lands on the floor.
 * The page one is already on is not an arrival: the entry is replaced.
 *
 * An arrival with NO FLOOR under it — an address nobody serves — is kept as
 * typed, and the switches made from it lay the floor (`switchWithoutFloor`).
 *
 * Args:
 *     leaving: The page id the interface was on before the caller rendered the
 *         destination — read at the call site because the store already holds
 *         the destination by the time history is settled.
 *     landing: How the tap lands, decided by the verb from where it was made.
 */
export function switchPage(leaving: string, landing: Landing = "stack"): void {
  if (walk.driven) return;
  const arriving = String(currentState().page);
  const homePage = addressSeam.homePage;
  if (arriving === leaving) {
    replacePath();
    return;
  }
  if (!walk.homeFloorExists) {
    switchWithoutFloor(leaving, arriving);
    return;
  }
  const trail = standingTrail(leaving);
  const floor = trail[0];
  if (landing === "unwind") {
    /* A floor that is not the entry page's (a driven state drawn over it) is
       replaced like the entry page's own. */
    if (arriving === homePage || floor.page !== homePage) layTrail([], [arriving], floor.at);
    else layTrail([floor], [arriving], floor.at + 1);
    return;
  }
  const revisited = trail.findIndex((stop, index) => index > 0 && stop.page === arriving);
  if (revisited > 0) {
    const kept = trail.slice(0, revisited);
    let pages = [...trail.slice(revisited + 1).map((stop) => stop.page), arriving];
    /* THE ENTRY PAGE MOVED DOWN ONTO THE FLOOR IS THE FLOOR: two of it in a
       row would be a Retour that changes nothing. */
    if (kept.length === 1 && pages[0] === homePage) pages = pages.slice(1);
    if (pages.length === 0) layTrail([], [homePage], floor.at);
    else layTrail(kept, pages, trail[revisited].at);
    return;
  }
  const top = trail[trail.length - 1];
  layTrail(trail, [arriving], landing === "stackOnPage" ? top.at + 1 : standingIndex() + 1);
}

/**
 * Records an arrival made from a panel onto another view of the page it was
 * opened on — « Voir les torrents » lands on the « Torrents » tab.
 *
 * The panel's entry is KEPT under it (D-L13-1), so Retour reopens the panel.
 * The arrival continues the page's trail, the page's stop moved up to the new
 * entry, so the bar still unwinds onto the floor from it. A layer's entry
 * carries no trail, so the page's is derived from the entry UNDER it — the
 * derivation `trailOf` makes for an entry that holds none.
 *
 * Returns:
 *     Whether the entry was really written.
 */
function recordArrivalInPage(): boolean {
  const page = String(currentState().page);
  const homePage = addressSeam.homePage;
  const standing = standingIndex();
  const onLayer = Boolean(history.state && history.state.layer);
  const under = onLayer ? standing - 1 : standing;
  const floor = page === homePage ? [] : [{ page: homePage, at: under - 1 }];
  return recordPath([...floor, { page, at: standing + 1 }]);
}

/**
 * Lays a trail of pages under the one drawn, from the floor up — for a named
 * state that shows WHERE Retour goes, so the path replays on a finger.
 *
 * A named state is driven and writes no history; this is the one write it
 * makes, AFTER the drive (`harness/drive.ts`, `poseTrail`).
 *
 * Args:
 *     pages: The pages from the entry page up, the page drawn last.
 */
export function layNamedTrail(pages: string[]): void {
  const floor = trailOf(history.state, addressSeam.homePage, String(currentState().page))[0];
  layTrail([], pages, Math.max(floor.at, 1));
}

/**
 * The page switch of a session that arrived at an address nobody serves.
 *
 * NO FLOOR, NO STEP BACK: the entry under the arrival is the exit guard, and
 * stepping onto it arms the exit from an arrival nobody made as a back. So a
 * switch from or to the entry page RECORDS — the address as typed stays one
 * back away — and THE ENTRY IT WRITES IS THE FLOOR, so the next switch stands
 * on it. Between two other pages the entry is replaced.
 *
 * Args:
 *     leaving: The page left.
 *     arriving: The page arrived at.
 */
function switchWithoutFloor(leaving: string, arriving: string): void {
  const homePage = addressSeam.homePage;
  if (leaving === homePage || arriving === homePage) {
    const floor = arriving === homePage ? [{ page: homePage, at: standingIndex() + 1 }] : undefined;
    if (recordPath(floor)) walk.homeFloorExists = true;
    return;
  }
  replacePath();
}

/**
 * Settles history for a page switch made FROM A LAYER.
 *
 * The drawer's entries and the account menu's « Profil et préférences » are the
 * page switches a finger can reach while something is open over the page. They
 * obey `switchPage`'s rule, the layer's entry being one more entry the trail
 * says is there: a bar page unwinds onto the floor, a menu page stacks on the
 * PAGE left — the layer, and a rubric open under it, given back first
 * (DECIDED 3, 2026-09-30) — so Retour lands on the page's root.
 *
 * THE PAGE ONE IS ON is no arrival: the layer closes and nothing is written.
 *
 * Args:
 *     leaving: The page id the interface was on before the caller rendered the
 *         destination.
 *     landing: How the tap lands, decided by the verb.
 */
export function switchPageFromLayer(leaving: string, landing: Landing = "stackOnPage"): void {
  if (walk.driven) return;
  const homePage = addressSeam.homePage;
  const arriving = String(currentState().page);
  if (arriving === leaving) {
    /* The layer's entry goes, announced so the ladder does not read the pop. */
    try {
      bridge.rewind(1);
    } catch (error) {
      console.error("switchPageFromLayer: closing the layer failed", error);
      window.__navEchec = true;
    }
    return;
  }
  if (walk.homeFloorExists) {
    switchPage(leaving, landing);
    return;
  }
  /* NO FLOOR to walk down to: the entry under the layer is an arrival nobody
     serves, and the one below THAT is the exit guard. The layer's entry takes
     the destination — AND THAT WRITE CAN LAY THE FLOOR ITSELF, whose trail is
     said: this entry arriving home, the one under it leaving home. */
  const at = standingIndex();
  const trail = arriving === homePage ? [{ page: homePage, at }]
    : leaving === homePage ? [{ page: homePage, at: at - 1 }, { page: arriving, at }] : undefined;
  if (replacePath(trail) && trail) walk.homeFloorExists = true;
}

// THE FEATURES REACH THE REPLACE THROUGH A DOOR, not by importing this module: a
// tab or a lens is a page setting every feature may write, and a module every
// feature imported would be the hub the fan-in arm refuses.
fillReplaceAddressDoor(replacePath);
// AND THE RECORD, for a panel's link that lands on another tab of the page it
// was opened on: an arrival, which stacks over the panel's kept entry.
fillRecordAddressDoor(recordArrivalInPage);
