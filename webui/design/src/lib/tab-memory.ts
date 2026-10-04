// The tab a tabbed page opens on when nothing names one — one rule for every
// such page: its first tab the first time, then the tab opened last on this
// device.
//
// THE DEVICE REMEMBERS, the server does not: the last tab opened is kept in this
// browser's local storage, under a key each page brings. Storage can be empty,
// refused or cleared — a private window, a blocked site — and each of those
// opens the first tab, never a failure. A remembered value the page no longer
// draws is ignored the same way.

/** One page's memory of its tab. */
export type TabMemory = {
  /** The last tab opened on this device, or the first tab. */
  remembered: () => string;
  /** Keeps a tab just opened, for the next entry; a value that is no tab is not kept. */
  remember: (tab: string) => void;
};

/**
 * A tabbed page's memory of the tab it opens on.
 *
 * @param storageKey The key the page's tab is kept under.
 * @param firstTab The tab a first opening lands on.
 * @param tabs Every tab the page draws.
 * @returns The page's memory.
 */
export function tabMemory(storageKey: string, firstTab: string, tabs: ReadonlySet<string>): TabMemory {
  return {
    remembered: () => {
      try {
        const kept = localStorage.getItem(storageKey);
        return kept !== null && tabs.has(kept) ? kept : firstTab;
      } catch {
        return firstTab;
      }
    },
    remember: (tab) => {
      try {
        if (tabs.has(tab)) localStorage.setItem(storageKey, tab);
      } catch {
        // Storage refused: the next entry opens the first tab, which is the rule.
      }
    },
  };
}
