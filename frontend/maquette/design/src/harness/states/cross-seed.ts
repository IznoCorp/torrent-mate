// The named states of the cross-seed (L17), on the « Trackers » page.
//
// Each entry is `[id, label, run]`, as every states file writes them. The seed
// is INVENTED (L17 DESIGN § 2.3) and its default is the live states: every
// switch on. A state that needs another scenario turns a dial and says so.
import { applyState, type NamedState } from "../drive";
import { openCutConfirm, openSwitchConfirm } from "../../features/trackers/cross-seed-verbs";

// The page's reads, and the settings the switches are kept in: dropped before a
// state so the page asks the layer again rather than drawing a state before's.
const READS = ["/api/trackers", "/api/acquisition/downloads", "/api/acquisition/obligations", "/api/config/schema"];

/** Resets the layer and forgets the page's reads. */
function fresh(): void {
  window.__mocks?.reset();
  for (const address of READS) window.__queries?.removeQueries({ queryKey: [address] });
}

/**
 * The « Trackers » tab, under the scenario a dial set before.
 *
 * @param pose What the state poses on the layer before the page reads it.
 */
function roster(pose: () => void = () => undefined): void {
  fresh();
  pose();
  applyState({ page: "trackers", trackersTab: "trackers", phase: "ready" });
}

// How long a panel waits for the tab it opens over to be drawn.
const OPEN_AFTER = 300;

// THE ENTRIES THE STATES OPEN, each a seeded entry: President Curtis cross-seeding
// on two trackers, Star Trek refused three ways, and President Curtis's copy on tr4ker.
export const CROSS_SEEDING = "66e23ab395c438b7db4f7c855bd451d8bb1f0046";
export const REFUSED = "8d51568b1a4f46e1fb7e7b535b52a5203312fc28";
export const COPY = "7c1e0b2f95c438b7db4f7c855bd451d8bb1f0046";
// Les Zinzins de l'Espace, still downloading: never searched on either tracker.
export const UNSEARCHED = "c44e8cd75bec37a8337175c6580e85d4e2079da3";
// Ted Lasso, its whole title excluded.
export const EXCLUDED = "e1af6819d9e3159e0aa191b534b6a66af4344788";

/**
 * The « Torrents » tab with one entry's panel open, as a tap on its card's body opens it.
 *
 * @param entry The entry, `<hash>:<tracker>`.
 * @param pose What the state poses on the layer before the page reads it.
 * @param then What a finger does once the panel is open.
 */
function torrentPanel(entry: string, pose: () => void = () => undefined, then: () => void = () => undefined): void {
  fresh();
  pose();
  applyState({ page: "trackers", trackersTab: "torrents", trackersFilter: "", phase: "ready" });
  window.setTimeout(() => {
    window.__panel.produce("torrent", entry);
    then();
  }, OPEN_AFTER);
}

/**
 * The « Trackers » tab with one tracker's panel open, as a tap on its row opens it.
 *
 * @param tracker The tracker's configured name.
 * @param pose What the state poses on the layer before the page reads it.
 * @param then What a finger does once the panel is open.
 */
function trackerPanel(tracker: string, pose: () => void = () => undefined, then: () => void = () => undefined): void {
  roster(pose);
  window.setTimeout(() => {
    window.__panel.produce("tracker", tracker);
    then();
  }, OPEN_AFTER);
}

/**
 * Every cross-seed state.
 *
 * @returns The table.
 */
export function crossSeedStates(): NamedState[] {
  return [
    [
      "trackers-cross-seed",
      "Trackers — la ligne cross-seed de chaque tracker (INVENTÉ, L17 § 2.3)",
      () => roster(),
    ],
    [
      "trackers-cross-seed-engine-off",
      "Trackers — le moteur entier est coupé, l'interrupteur de chaque tracker dit ensuite (INVENTÉ)",
      () => roster(() => window.__mocks?.poseCrossSeedEngineOff()),
    ],
    [
      "torrents-cross-seed",
      "Torrents — la marque cross-seed d'un torrent d'origine, chaque autre tracker dans son état (INVENTÉ)",
      () => torrentPanel(`${CROSS_SEEDING}:c411`),
    ],
    [
      "torrents-cross-seed-refused",
      "Torrents — un refus, sa raison en entier : sa phrase, son genre d'ennui, le candidat, la source (INVENTÉ)",
      () => torrentPanel(`${REFUSED}:c411`),
    ],
    [
      "torrents-obligation-cross-seed",
      "Torrents — une obligation née d'un cross-seed, son origine et le chemin vers sa fiche (INVENTÉ)",
      () => torrentPanel(`${COPY}:tr4ker`),
    ],
    [
      "tracker-cross-seed-switch-off",
      "Tracker — l'interrupteur cross-seed de tr4ker est coupé, le cross-seed déjà actif continue (INVENTÉ)",
      () => trackerPanel("tr4ker", () => window.__mocks?.poseCrossSeedSwitchOff("tr4ker")),
    ],
    [
      "tracker-cross-seed-switch-confirm",
      "Tracker — confirmer la coupure sur tr4ker, avec ou sans les cross-seeds en cours, l'obligation nommée (INVENTÉ)",
      () => trackerPanel("tr4ker", () => undefined, () => openSwitchConfirm("tr4ker")),
    ],
    [
      "torrents-cross-seed-cut-confirm",
      "Torrents — couper le cross-seed de President Curtis sur tr4ker : sans ses fichiers, l'obligation nommée (INVENTÉ)",
      () => torrentPanel(`${CROSS_SEEDING}:c411`, () => undefined, () => openCutConfirm(CROSS_SEEDING, "tr4ker")),
    ],
    [
      "torrents-cross-seed-exclude",
      "Torrents — un titre exclu entier (Ted Lasso), l'annulation à portée, sans confirmation (INVENTÉ)",
      () => torrentPanel(`${EXCLUDED}:c411`),
    ],
    [
      "torrents-cross-seed-search",
      "Torrents — « Chercher un cross-seed » offert sur les paires pas encore cherchées, le quota du moteur dit (INVENTÉ)",
      () => torrentPanel(`${UNSEARCHED}:c411`),
    ],
    [
      "torrents-cross-seed-search-queued",
      "Torrents — la recherche est en file, dite ; le quota du jour atteint, elle partira demain (INVENTÉ, POSÉ)",
      () => torrentPanel(`${UNSEARCHED}:c411`, () => {
        window.__mocks?.poseCrossSeedQuotaSpent();
        window.__mocks?.poseCrossSeedPair(UNSEARCHED, "tr4ker", { searching: true });
      }),
    ],
  ];
}
