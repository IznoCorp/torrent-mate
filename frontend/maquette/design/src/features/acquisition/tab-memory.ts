// The tab Acquisition opens on when nothing names one — the operator's rule:
// « Suivis par défaut, puis le dernier onglet ouvert (mémoire locale) ».
//
// THE DEVICE REMEMBERS, the server does not: the last tab opened is kept in this
// browser's local storage. Storage can be empty, refused or cleared — a private
// window, a blocked site — and each of those opens « Suivis », never a failure.
const STORAGE_KEY = "acquisition-tab";

/** The tab a first opening lands on. */
const FIRST_TAB = "follows";

/** Every tab Acquisition draws; a remembered value that is none of them is ignored. */
const TABS = new Set(["follows", "now", "todo", "discover"]);

/**
 * The tab to open when nothing names one.
 *
 * @returns The last tab opened on this device, or « Suivis ».
 */
export function rememberedTab(): string {
  try {
    const kept = localStorage.getItem(STORAGE_KEY);
    return kept !== null && TABS.has(kept) ? kept : FIRST_TAB;
  } catch {
    return FIRST_TAB;
  }
}

/** The candidates screen's address, whose every exit returns to « À traiter ». */
const CANDIDATES_SCREEN = "/resolution/";

/**
 * The tab Acquisition lands on.
 *
 * THE CANDIDATES SCREEN BELONGS TO « À TRAITER »: every exit from it returns
 * there, whichever way the screen was reached. Opened from the list, the exit
 * pops the list's own entry, which carries its tab. Opened cold from a link,
 * Acquisition is laid beneath the screen by the boot, and it is laid on
 * « À traiter » rather than on the tab the device remembers — or the exit would
 * land on a list the screen does not answer.
 *
 * @returns « À traiter » beneath the candidates screen, the remembered tab otherwise.
 */
export function landingTab(): string {
  return location.pathname.startsWith(CANDIDATES_SCREEN) ? "todo" : rememberedTab();
}

/**
 * Remembers the tab just opened, for the next entry.
 *
 * @param tab The tab.
 */
export function rememberTab(tab: string): void {
  try {
    if (TABS.has(tab)) localStorage.setItem(STORAGE_KEY, tab);
  } catch {
    // Storage refused: the next entry opens « Suivis », which is the rule.
  }
}
