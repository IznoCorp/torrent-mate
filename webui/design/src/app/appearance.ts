// THE THEME — three honest states, and the one place that knows which.
//
// It was the dying engine's: a constant, a reader, a writer, a media listener
// and a click branch, beside the drawer's markup that offered them. It is the
// FRAME's (`MODEL.md` § 2 Part 9): the theme belongs to the entry, and §17
// redraws the sign-in gate beside it — which cannot happen while the entry is
// engine code (D5 allows no addition there).
//
// THE DEFAULT PAINTS DARK. No `data-theme` attribute is the default and it is
// dark; « light » forces light; « system » follows the operating system's
// preference, LIVE — the media listener acts only while that mode is chosen.
//
// THE CHOICE PERSISTS UNDER THE KEY THE ENVELOPE READS BEFORE THE FIRST PAINT.
// `index.html` carries an inline script that applies the saved appearance
// before any module runs, so a reload opens in the chosen appearance without a
// flash. The storage key is a CONTRACT with that script and is not renamed:
// renaming it would orphan every choice already saved.
//
// THE VALUES AND THAT SCRIPT AGREE SINCE B-245, and they did not before: the
// script tested « clair » and « systeme » while this module and its predecessor
// wrote « light » and « system », so no value it could store matched either
// literal — and the pre-paint script is the ONLY reader of the stored choice at
// boot, so a saved « light » was not applied at all until the control was
// touched again. A `data-*` contract has three ends and moves in one step; this
// one's third end is `localStorage`, and the English rename left it behind.

/** The three states the drawer offers, in the order it offers them. */
export const APPEARANCES = ["system", "light", "dark"] as const;

export type Appearance = (typeof APPEARANCES)[number];

/** Where the choice is kept — read by `index.html` before the first paint. */
const STORAGE_KEY = "tm-apparence";

/**
 * The appearance in force.
 *
 * Returns:
 *     The stored choice, or « system » where nothing valid is stored — which
 *     covers a private window and a browser that refuses storage outright.
 */
export function currentAppearance(): Appearance {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if ((APPEARANCES as readonly string[]).includes(stored ?? ""))
      return stored as Appearance;
  } catch (error) {
    void error;
  }
  return "system";
}

/**
 * Paints the document in one appearance, without recording it.
 *
 * Args:
 *     mode: Which of the three.
 */
export function applyAppearance(mode: Appearance): void {
  const light =
    mode === "light" ||
    (mode === "system" && matchMedia("(prefers-color-scheme: light)").matches);
  if (light) document.documentElement.setAttribute("data-theme", "light");
  else document.documentElement.removeAttribute("data-theme");
  followTheme();
}

/**
 * Puts the status bar's colour where the document's ground is (B-233).
 *
 * `theme-color` was a CONSTANT — `#0b0b0d` — while the document paints light
 * under `data-theme="light"`, so an installed application in the light theme
 * wore a dark status bar. P21 of `MODEL.md` § 3 was false.
 *
 * THE VALUE IS READ FROM WHAT IS PAINTED, never retyped beside it. A second
 * copy of a colour is a colour that drifts, and this repository has the
 * measurement: the brand colour was renamed and a retyped copy went on
 * rendering correctly while the reference was broken. `getComputedStyle` on the
 * body answers what the ground really is under whichever theme is in force, in
 * whatever colour space the token declares — and the meta accepts that string,
 * because it is the same value the page paints.
 *
 * THE DOCUMENT KEEPS ITS OWN DECLARATION and this does not replace it: the
 * static meta is the DARK value, which is what the default paints, and it is
 * there for the frames before any module runs.
 */
function followTheme(): void {
  const meta = document.querySelector<HTMLMetaElement>(
    'meta[name="theme-color"]',
  );
  if (!meta) return;
  const ground = getComputedStyle(document.body).backgroundColor;
  if (ground) meta.setAttribute("content", ground);
}

/**
 * Records a choice and paints it.
 *
 * Args:
 *     mode: Which of the three.
 */
export function chooseAppearance(mode: Appearance): void {
  try {
    localStorage.setItem(STORAGE_KEY, mode);
  } catch (error) {
    void error;
  }
  applyAppearance(mode);
}

/**
 * Follows the operating system while — and only while — « system » is chosen.
 *
 * Installed once, from the frame. The listener is permanent and the CONDITION
 * is checked inside it: a listener added and removed as the mode changes is
 * two ends kept in step by hand, and the mode is read from one place anyway.
 */
export function installAppearance(): void {
  matchMedia("(prefers-color-scheme: light)").addEventListener("change", () => {
    if (currentAppearance() === "system") applyAppearance("system");
  });
  // AND ONCE AT BOOT, because the pre-paint script in `index.html` writes the
  // ATTRIBUTE and knows nothing of the meta: it runs before any stylesheet is
  // parsed, so it could not read a painted colour even if it wanted to. The
  // document's static `theme-color` covers those first frames; this is the
  // first moment the real ground exists to be read.
  followTheme();
}
