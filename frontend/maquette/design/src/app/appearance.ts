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
// ⚠ THE VALUES AND THAT SCRIPT DISAGREE TODAY (B-245): it tests « clair » and
// « systeme », and nothing written here has matched either since the English
// rename. That is a BEHAVIOUR defect and it is repaired in its own commit,
// never inside this move — a conversion proves the rendering did not change.

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
}
