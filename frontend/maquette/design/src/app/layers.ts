// THE LADDER — the layers as registrations, and what Back does with them.
//
// A layer registers itself — a name, an `isOpen`, a `close(pop)` — and the
// ladder walks the registrations in RANK, never in the order they happened to
// register: the dialog, then the drawer, then the sheet. The walker never knows
// a layer's markup.
//
// THE STATE IS THE REGISTRATION'S, NEVER THE DOM'S. A caller asks in the middle
// of its own task (« is a layer up before I open a screen? ») and the answer
// must be right at that instant, whatever React has painted — the same reason
// `panel.isOpen()` reads the store.
import i18next from "../i18n";
import { addressSeam } from "../lib/addresses";
import { entryPatch } from "../lib/navigation-entry";
import { bridge, toast } from "../lib/shell-doors";
import { reopenAddressedPanel } from "./addressed-panels";
import { BACK_WINDOW, recordPath, walk } from "./page-switch";

export type LayerRegistration = {
  /** Whether it is up right now. */
  isOpen: () => boolean;
  /**
   * Closes it.
   *
   * Args:
   *     pop: True when the entry is already being popped by the gesture that
   *         got here, so the layer must not unwind one of its own.
   */
  close: (pop?: boolean) => void;
};

const layers = new Map<string, LayerRegistration>();

/* THE RANK. Back closes the first of these that is open, and nothing else. */
const RANK = ["dialog", "drawer", "sheet"] as const;

/**
 * Registers a layer under a name the ladder walks.
 *
 * Args:
 *     name: The rung's name — `"drawer"`, `"dialog"`, `"sheet"`.
 *     registration: What the walker may ask and say.
 *
 * Returns:
 *     The way to take it off the ladder again.
 */
export function registerLayer(
  name: string,
  registration: LayerRegistration,
): () => void {
  layers.set(name, registration);
  return () => {
    if (layers.get(name) === registration) layers.delete(name);
  };
}

/** The registrations, as the ladder walks them — published by the harness as `window.__layers`. */
export const registeredLayers = {
  isOpen: (name: string) => layers.get(name)?.isOpen() === true,
  close: (name: string, pop?: boolean) => layers.get(name)?.close(pop),
  // Published so a rule can ask what is ON the ladder rather than assume it: a
  // rung that stopped registering is invisible to every hold shaped like « Back
  // closed the thing that was open ».
  names: () => [...layers.keys()],
};

/* HOW A PAGE IS RESTORED, handed in by the engine, which still draws it: the
   layers hidden without touching history, the store written, the port back at
   the top when the patch names a new place, and the page drawn. It forwards a
   patch it did not compose, so it stays beside the `render` it calls.

   IT DID NOT LEAVE THE ENGINE AT b·7, and the reason is measured rather than
   chosen: the restore writes a patch composed elsewhere, and
   `check-state-ownership.py` refuses a store write whose argument it cannot
   read — « a key it cannot classify is a key that would otherwise leave the
   count meaning the ones I could read ». The engine is the one module that arm
   exempts, so the restore leaves when the engine does. */
let restorePage: (patch: Record<string, unknown>) => void = () => {};

/**
 * Installs how the handler restores the page an entry names.
 *
 * Args:
 *     restore: Writes the patch and draws the page, without touching history.
 */
export function installPageRestore(restore: (patch: Record<string, unknown>) => void): void {
  restorePage = restore;
}

/* Closing WITHOUT touching history — the harness driver uses it to restart from
   a clean surface. Chaining the « normal » close functions made
   `history.back()` pop past our own entries and leave the page entirely. */
export function hideLayers(): void {
  registeredLayers.close("drawer", true);
  registeredLayers.close("sheet", true);
  // The scrim is DERIVED, not written: `ui/sheet.tsx` raises it while any
  // scrim-backed layer is open, so clearing the layers clears it.
  registeredLayers.close("dialog", true);
}

/* The scrim covers three layers at once and a tap on it closes whichever is up;
   the drawer's swipe and Escape close through the same verb, so one gesture
   never has two answers. */
export function closeLayers(): void {
  registeredLayers.close("dialog");
  registeredLayers.close("sheet");
  registeredLayers.close("drawer");
}

/* A layer that closes itself pops the entry it pushed — and that pop must not be
   read as a navigation. The entry underneath describes where one ALREADY is, so
   applying it undoes whatever the close was accompanied by: tapping a drawer
   entry changed the page, then the drawer's own pop put the previous page back,
   and every entry in the drawer led nowhere.

   So an unwind announces itself, and the back handler consumes the announcement
   instead of interpreting the event. Two guards matter:

   · The name is checked against the entry actually on top, because only the
     layer that pushed it may pop it. Three close functions run in a row on the
     scrim, and without the name the second would pop an entry belonging to the
     page underneath.
   · One unwind is in flight at a time. A back is asynchronous, so
     `history.state` still reads the entry we just asked to pop, and a second
     call within the same task would ask for one entry too many. */
let unwindInProgress = 0;

/**
 * Pops the entry a layer pushed, announced so the handler does not read it.
 *
 * Args:
 *     name: The layer closing itself.
 */
export function unwindLayer(name: string): void {
  if (unwindInProgress) return;
  if (!history.state || history.state.layer !== name) return;
  unwindInProgress += 1;
  try {
    bridge.back();
  } catch {
    unwindInProgress -= 1;
  }
}

/* A settlement of SEVERAL entries at once (the bridge's `rewind`) announces
   itself through the same latch — and raises it by ONE, never by the number of
   entries: the browser coalesces a multi-entry traversal into a SINGLE popstate,
   fired at the destination. Measured: `history.go(-2)` reports one pop, where
   two `history.back()` calls issued in the same task report two. Raising the
   latch by n would leave the surplus standing and swallow the operator's next
   real back.

   No named-entry check here, unlike `unwindLayer`: what is being settled is a
   WALK of several entries whose top one is not necessarily a layer. The caller
   counts what it stacked and is the only one that can. */
export function announceEntries(entryCount: number): void {
  if (entryCount > 0) unwindInProgress += 1;
}

type NavigationEntry = {
  tm?: string;
  layer?: string;
  page?: string;
  [dial: string]: unknown;
};

/**
 * What a Back, a Forward or a jump does — the ladder's handler.
 *
 * The bridge hands over the state of the entry now CURRENT, which is the entry
 * the gesture landed on, and the DIRECTION: one entry shape means opposite
 * things stepped onto forwards and stepped back onto.
 *
 * Args:
 *     current: The state of the entry the gesture landed on.
 *     direction: `BACK`, `FORWARD` or `GO`.
 */
export function onEngineBack(
  current: unknown,
  direction: "BACK" | "FORWARD" | "GO",
): void {
  // Our own unwind, announced by the caller that issued it. It is not a back
  // gesture, so it is never INTERPRETED — but consuming it is not the whole
  // handling: a caller that rewound in order to write on the entry it lands on
  // leaves that write here, and this is the moment it becomes safe to make.
  // Read before the layer guards, because the layer is already gone by the
  // time its pop lands.
  if (unwindInProgress) {
    unwindInProgress -= 1;
    const settle = walk.afterUnwind;
    walk.afterUnwind = null;
    if (settle) settle();
    return;
  }

  /* A layer first: it is what sits on top, and it is what a back closes. THE
     DIALOG IS THE TOP RUNG (B-229): D1's third tier reads « Transient: no URL,
     but Back still closes it » and names a confirmation as its example. */
  for (const name of RANK) {
    if (registeredLayers.isOpen(name)) {
      registeredLayers.close(name, true);
      return;
    }
  }

  const state = current as NavigationEntry | null;
  /* A layer entry stood on with nothing open, and the DIRECTION decides which
     of two opposite things it is.

     FORWARD: going back off a panel leaves its entry AHEAD in the history, and
     stepping forward onto it fell through every branch below — so the address
     read `?panel=…` with nothing open. The entry names the panel in its own
     address, so it is asked for again; nothing is pushed, because this entry IS
     the panel's.

     BACK, or a jump: the entry is a closed panel's LEFTOVER, and reopening it
     would raise the panel over a page it was never opened on. The shape comes
     from a tab-bar tap made while a panel is up — no finger reaches a tab over a
     layer today, `node.click()` does, and so will any future surface that puts
     a page switch over a layer. So it is stepped OVER, and that second pop is
     NOT announced: the interface is on the page the tap moved it to, and only
     the entry beneath can put it back — so the pop must be READ, through the
     `tm: "nav"` branch below, exactly as the operator's own second back. */
  if (state && state.layer === "sheet" && !registeredLayers.isOpen("sheet")) {
    if (direction === "FORWARD") {
      reopenAddressedPanel(location.search, true);
      return;
    }
    bridge.back();
    return;
  }

  if (state && state.tm === "nav") {
    walk.armedExit = 0;
    /* BACK UNDER THE FLOOR, and it is a BACK that lowers the flag — never a
       FORWARD — and only in a session that arrived without one. There the floor
       was laid by a switch rather than by the boot, so a Back can land beneath
       it, and left raised the way out steps back onto the exit guard. A FORWARD
       RETRACES, IT DOES NOT DESCEND: lowering the flag on it made a cold
       not-found arrival grow its stack by two entries per Back+Forward cycle. A
       GO is left alone: its delta is not reported, and the flag is better left
       raised than lowered on a guess. */
    if (
      walk.arrivalWithoutFloor &&
      direction === "BACK" &&
      state.page !== addressSeam.homePage
    )
      walk.homeFloorExists = false;
    walk.driven = true;
    restorePage(entryPatch(state));
    walk.driven = false;
    return;
  }

  // Ownership, once more, decided by the entry's own SHAPE: only an entry that
  // carries the guard's own marker (written once, at boot) is the guard. An
  // entry the ROUTER wrote for a screen carries neither `layer` nor `tm`, and
  // the router has already re-rendered by the new URL, so a true no-op is the
  // correct handling — reading it as the guard armed the exit warning and
  // rewrote the address over the router's search params.
  if (!(state && state.tm === "garde")) return; // french-ok: the exit guard's entry marker, written by the boot and matched by the harness

  // The guard was popped: there is nowhere left to go back to.
  const now = Date.now();
  if (walk.armedExit && now - walk.armedExit < BACK_WINDOW) {
    walk.armedExit = 0;
    // Nothing is put back: from the guard, one more back leaves the document —
    // which is what closes an installed app on Android.
    bridge.back();
    return;
  }
  walk.armedExit = now;
  // Where one IS is pushed back on, so the route does not change and the next
  // back lands on the guard again.
  recordPath();
  toast?.show({ message: i18next.t("message.oneMoreBack") });
}
