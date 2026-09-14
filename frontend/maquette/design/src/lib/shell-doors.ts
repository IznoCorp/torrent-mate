// THE SHELL'S FOUR DOORS — the message, the panel, the history and the screens.
//
// A verb that shows a message, a producer that closes the panel, a screen that
// steps back: each asks one of these. They are OWNED by the shell's hosts
// (`app/toast-host.ts`, `app/panel-host.ts`, `app/history-bridge.ts`), which
// fill them when they install. They are DECLARED here because a door every
// feature passes through belongs where the frame keeps what it shares: a module
// outside `ui/` and `lib/` that every feature imported would be the hub
// invariant 8 refuses.
//
// THEY ARE `let`, AND THAT IS THE WHOLE MECHANISM — the one `engine/seams.ts`
// uses. Each is filled at its host's install, after this module has evaluated;
// an ES export is a live binding, so a caller reads the filled value at call
// time, which is the only time it calls.
//
// NOTHING HERE READS `window`, and this module imports nothing. A rule reaches
// the same objects under their seam names, which the harness publishes.

/** The message's verbs. Undefined until the message host installs. */
export let toast: Window["__toast"];
/** The panel's verbs. */
export let panel: Window["__panel"];
/** The history primitives the navigation logic speaks through. */
export let bridge: Window["__bridge"];
/** The screen openers. */
export let screens: Window["__screens"];

/**
 * Fills the message door, from the message host's install.
 *
 * @param verbs What showing, hiding and reading a message call.
 */
export function fillToastDoor(verbs: NonNullable<Window["__toast"]>): void {
  toast = verbs;
}

/**
 * Fills the panel door, from the panel host's install.
 *
 * @param verbs What opening, closing and producing a panel call.
 */
export function fillPanelDoor(verbs: Window["__panel"]): void {
  panel = verbs;
}

/**
 * Fills the history door, from the history bridge's install.
 *
 * @param primitives The verbs every history write goes through.
 */
export function fillBridgeDoor(primitives: Window["__bridge"]): void {
  bridge = primitives;
}

/**
 * Fills the screens door, from the screen bridge's install.
 *
 * @param openers One opener per screen.
 */
export function fillScreensDoor(openers: Window["__screens"]): void {
  screens = openers;
}
