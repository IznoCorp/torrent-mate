// The tab Acquisition opens on when nothing names one — the operator's rule:
// « Suivis par défaut, puis le dernier onglet ouvert (mémoire locale) ».
//
// THE DEVICE REMEMBERS, the server does not, through the memory every tabbed
// page shares (`lib/tab-memory.ts`) — this page brings its key, its first tab
// and its tabs. Storage that is empty, refused or cleared opens « Suivis ».
import { tabMemory } from "../../lib/tab-memory";
import { heldRights } from "../../lib/account";
import type { Rights } from "../../lib/rights";

const STORAGE_KEY = "acquisition-tab";

/** The tab a first opening lands on. */
const FIRST_TAB = "follows";

/**
 * Every tab Acquisition draws; a remembered value that is none of them is
 * ignored — « discover » included, now a page of the bottom bar.
 */
const TABS = new Set(["follows", "now", "todo"]);

const MEMORY = tabMemory(STORAGE_KEY, FIRST_TAB, TABS);

/**
 * The tab to open when nothing names one.
 *
 * @returns The last tab opened on this device, or « Suivis ».
 */
export function rememberedTab(): string {
  return MEMORY.remembered();
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
 * A LANDING THAT NAMES ITS TAB opens that tab, as an address that names one
 * does; it is not remembered, since the operator did not choose it.
 *
 * @param asked The tab the landing names, if any; a value that is no tab is ignored.
 * @returns The tab asked for, « À traiter » beneath the candidates screen, the remembered tab otherwise.
 */
export function landingTab(asked?: string): string {
  if (asked !== undefined && TABS.has(asked)) return asked;
  if (location.pathname.startsWith(CANDIDATES_SCREEN)) return "todo";
  // THE VIEWER'S MEMORY IS THE VIEWER'S (R-L18-x): a tab remembered under a role
  // that opened it is ignored under one that does not.
  // Before the account is read nothing is known to be closed: the memory stands.
  const remembered = rememberedTab();
  const rights = heldRights();
  if (!rights.known) return remembered;
  return tabsOpenTo(rights).includes(remembered) ? remembered : tabsOpenTo(rights)[0] ?? remembered;
}

/**
 * The tabs of Acquisition an account opens, in their order (§ 17): « Suivis »
 * to a role that manages follows or sees everyone's, the two others to any
 * role that reaches the section.
 *
 * @param rights What the account may do.
 * @returns The tab ids.
 */
export function tabsOpenTo(rights: Rights): string[] {
  const follows = rights.holdsAny(["acquisition.follow", "acquisition.see.others"]);
  return [...(follows ? ["follows"] : []), "now", "todo"];
}

/**
 * Remembers the tab just opened, for the next entry.
 *
 * @param tab The tab.
 */
export function rememberTab(tab: string): void {
  MEMORY.remember(tab);
}
