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
