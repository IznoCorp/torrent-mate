// THE MENU ON A DESKTOP — pinned open, or collapsed to its icons (DECIDED 2, 2026-10-01).
//
// The operator: « B, le même menu latéral, épinglé ouvert par défaut, avec possibilité de le
// "fermé" version réduite (barre verticale avec icones seulement) ». From the desktop threshold
// the SAME drawer stays beside the content; this module only holds which of its two widths the
// reader chose, and answers whether the threshold holds at all.
//
// THE CHOICE IS THE DEVICE'S, in `localStorage` (his 09-08 ruling « desktop = localStorage »),
// under a key the envelope's pre-paint script reads too, so a reload opens at the chosen width
// without the menu snapping from one to the other. Renaming the key orphans every saved choice.

/** The two widths of the pinned menu. */
export type Rail = "open" | "collapsed";

/** Where the choice is kept — read by `index.html` before the first paint. */
const STORAGE_KEY = "tm-rail";

/**
 * The width the pinned menu is drawn at.
 *
 * Returns:
 *     « collapsed » when the reader folded it on this device, « open » otherwise — which covers
 *     a private window and a browser that refuses storage.
 */
export function currentRail(): Rail {
  try {
    if (localStorage.getItem(STORAGE_KEY) === "collapsed") return "collapsed";
  } catch (error) {
    void error;
  }
  return "open";
}

/**
 * Draws the pinned menu at one width and remembers it for this device.
 *
 * Args:
 *     rail: Which of the two.
 */
export function chooseRail(rail: Rail): void {
  try {
    localStorage.setItem(STORAGE_KEY, rail);
  } catch (error) {
    void error;
  }
  applyRail(rail);
}

/**
 * Writes the width onto the document, where `styles/base.css` reads it.
 *
 * Args:
 *     rail: Which of the two.
 */
export function applyRail(rail: Rail): void {
  if (rail === "collapsed") document.documentElement.setAttribute("data-rail", "collapsed");
  else document.documentElement.removeAttribute("data-rail");
}

/**
 * Whether the shell is drawn for a desktop — the `desk:` variant's own condition.
 *
 * READ FROM THE STYLESHEET, never re-derived: `--tm-desk` is set under the very media query and
 * selector the variant is (`styles/base.css`), so a script and a utility cannot disagree.
 *
 * Returns:
 *     True when the menu is pinned and the panels open at the side.
 */
export function isDesktop(): boolean {
  return getComputedStyle(document.documentElement).getPropertyValue("--tm-desk").trim() === "1";
}
