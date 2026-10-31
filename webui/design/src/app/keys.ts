// design/src/app/keys.ts
// THE DECLARED KEYS (DECIDED 6 = B, 2026-10-01).
//
// The operator ruled « a small declared key set — `/` to the page's search, ↑/↓ in a list, Enter
// opens, Escape closes — and no action exists only on a key ». This module is the whole set but two:
// Enter needs nothing, every row, card and tile being a native `<button>` that Enter presses; Escape
// is `app/focus.ts`'s, beside the layers it closes. Each key here only MOVES THE FOCUS to a control
// the pointer and the finger already reach: nothing is done that a click does not do.
//
// THE SCOPE IS THE SURFACE ON TOP. Under a sheet or a confirmation the page is `inert` background:
// a key there would reach what the reader cannot see, so neither key answers. Over a screen, the
// screen's own search and rows; else the page's.
//
// A FIELD KEEPS ITS KEYS. In an input, `/` is a character and ↑/↓ move a caret or a number — except
// ↓ out of a SEARCH, which goes to the first row the search found: the way from the field to the
// list it filters, the one move a keyboard otherwise has to Tab for.

/** The openers a list holds: a card's body, a tile, a topic, a fact row, a setting, a tracker. */
const ITEM =
  'button:is([data-part="card/body"], [data-part="tile"], [data-part="topic"], [data-part="flux/row-body"], ' +
  '[data-part="setting/row"], [data-part="trackers/body"])';

/** A page's search: the field `/` reaches. */
const SEARCH = 'input[type="search"]';

/** The layers that cover the page and leave no key to it. */
const COVER = "#sheet[data-open], #dlg[data-open]";

/** A box, as the geometry below reads it. */
export type Box = { top: number; bottom: number; left: number; right: number };

/**
 * The item a ↑ or a ↓ moves to, by where the items are drawn.
 *
 * By GEOMETRY, never by document order: in a list the next row is the one below, and in a gallery
 * of tiles it is the tile BELOW too — the one whose middle is nearest the current one's, in the
 * nearest row past it — where document order would walk the row sideways.
 *
 * Args:
 *     boxes: Every item's box, in any order.
 *     current: The index of the focused item in `boxes`.
 *     direction: 1 for ↓, -1 for ↑.
 *
 * Returns:
 *     The index to focus, or `current` when nothing lies that way.
 */
export function nextItem(boxes: readonly Box[], current: number, direction: 1 | -1): number {
  const from = boxes[current];
  const middle = (from.left + from.right) / 2;
  // A row is « ahead » of this one when it starts beyond this one's line, with a pixel's tolerance for
  // sub-pixel layouts.
  const ahead = boxes
    .map((box, index) => ({ box, index }))
    .filter(({ box }) => (direction === 1 ? box.top >= from.bottom - 1 : box.bottom <= from.top + 1));
  if (!ahead.length) return current;
  const closestLine = direction === 1
    ? Math.min(...ahead.map(({ box }) => box.top))
    : Math.max(...ahead.map(({ box }) => box.bottom));
  const line = ahead.filter(({ box }) => Math.abs((direction === 1 ? box.top : box.bottom) - closestLine) <= 1);
  line.sort((a, b) =>
    Math.abs((a.box.left + a.box.right) / 2 - middle) - Math.abs((b.box.left + b.box.right) / 2 - middle));
  return line[0].index;
}

/** Whether an element is drawn — a hidden tab or a closed popover holds no reachable item. */
function drawn(element: Element): boolean {
  return element.getClientRects().length > 0 && !element.closest("[inert]");
}

/** The surface the keys act on, or null when a layer covers it. */
function surface(): Element | null {
  if (document.querySelector(COVER)) return null;
  const screen = [...document.querySelectorAll('[data-part="screen"][data-open]')].filter((s) => s.isConnected).pop();
  return screen ?? document.getElementById("view");
}

/** Whether the key was typed into something that takes text. */
function typing(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || target.matches("input, textarea, select");
}

/**
 * Moves the focus to a control, and the view to it.
 *
 * Args:
 *     control: The control.
 */
function reach(control: HTMLElement): void {
  control.focus({ preventScroll: true });
  control.scrollIntoView({ block: "nearest" });
}

/**
 * Answers one key, or leaves it to the browser.
 *
 * Args:
 *     event: The key.
 */
function answer(event: KeyboardEvent): void {
  if (event.defaultPrevented || event.isComposing || event.metaKey || event.ctrlKey || event.altKey) return;
  const root = surface();
  if (!root) return;
  if (event.key === "/") {
    if (typing(event.target)) return;
    const search = [...root.querySelectorAll<HTMLInputElement>(SEARCH)].find(drawn);
    if (!search) return;
    event.preventDefault();
    reach(search);
    search.select();
    return;
  }
  if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
  const items = [...root.querySelectorAll<HTMLElement>(ITEM)].filter(drawn);
  if (!items.length) return;
  const active = document.activeElement;
  const at = items.findIndex((item) => item === active);
  if (at === -1) {
    // From a search, ↓ goes to the first row; from nowhere (the body, the main region), ↓ enters the
    // list. Anywhere else — a tab, a switch, a field — the arrow is that control's own.
    const fromSearch = active instanceof HTMLInputElement && active.matches(SEARCH) && root.contains(active);
    const fromNowhere = !active || active === document.body || active.id === "port" || active === root;
    if (event.key !== "ArrowDown" || !(fromSearch || (fromNowhere && !typing(event.target)))) return;
    event.preventDefault();
    reach(items[0]);
    return;
  }
  event.preventDefault();
  const boxes = items.map((item) => item.getBoundingClientRect());
  reach(items[nextItem(boxes, at, event.key === "ArrowDown" ? 1 : -1)]);
}

let installed = false;

/** Installs the declared keys. Idempotent — a second call is a no-op. */
export function installKeys(): void {
  if (installed) return;
  installed = true;
  document.addEventListener("keydown", answer);
}
