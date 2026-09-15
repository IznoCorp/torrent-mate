// THE SHELL'S FIVE DOORS — the message, the panel, the confirmation, the
// history and the screens.
//
// A verb that shows a message, a producer that closes the panel, a screen that
// steps back: each asks one of these. They are OWNED by the shell's hosts
// (`app/toast-host.ts`, `app/panel-host.ts`, `app/dialog-host.ts`,
// `app/history-bridge.ts`), which
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
/** The confirmation's verbs. */
export let dialog: Window["__dialog"];
/** The titles followed right now — asked by a feature that may not import acquisition. */
export let followedTitles: (() => string[]) | undefined;
/** Rewrites the current history entry's address for a page setting — a tab, a lens. */
export let replaceAddress: (() => boolean) | undefined;
/** Opening the panel an element addresses — the press reads it while the gesture is still the engine's. */
export let openAddressedPanel: ((element: Element) => void) | undefined;
/** What a page puts back at its default when a landing arrives on it — filled by the page's own feature. */
export let resetLandingDial: ((page: string) => void) | undefined;
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
 * Fills the confirmation door, from the confirmation host's install.
 *
 * @param verbs What opening and closing a confirmation call.
 */
export function fillDialogDoor(verbs: Window["__dialog"]): void {
  dialog = verbs;
}

/**
 * Fills the followed-titles door, from the follows' install.
 *
 * @param read What answers the titles followed right now.
 */
export function fillFollowedTitlesDoor(read: () => string[]): void {
  followedTitles = read;
}

/**
 * Fills the address-replacing door, from the page switch.
 *
 * @param write What rewrites the current entry's address, answering whether it did.
 */
export function fillReplaceAddressDoor(write: () => boolean): void {
  replaceAddress = write;
}

/**
 * Fills the addressed-panel door, from the frame's verbs.
 *
 * @param open What opens the panel an element addresses.
 */
export function fillAddressedPanelDoor(open: (element: Element) => void): void {
  openAddressedPanel = open;
}

/**
 * Fills the landing door, from a feature that resets a dial on arrival.
 *
 * A page's dials are the page's own — the frame may not name one (invariant 10)
 * and the state-ownership arm reads every write by the keys it can SEE, so the
 * write is made where the dial is understood rather than forwarded as a patch.
 *
 * @param land What a feature does when a landing arrives on one of its pages.
 */
export function fillLandingDoor(land: (page: string) => void): void {
  resetLandingDial = land;
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
