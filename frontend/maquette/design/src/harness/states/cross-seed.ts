// The named states of the cross-seed (L17), on the « Trackers » page.
//
// Each entry is `[id, label, run]`, as every states file writes them. The seed
// is INVENTED (L17 DESIGN § 2.3) and its default is the live states: every
// switch on. A state that needs another scenario turns a dial and says so.
import { applyState, type NamedState } from "../drive";
import { openCutConfirm, openSwitchConfirm, openUploadConfirm } from "../../features/trackers/cross-seed-verbs";
import { owed } from "../owed";

// The page's reads, and the settings the switches are kept in: dropped before a
// state so the page asks the layer again rather than drawing a state before's.
const READS = ["/api/v1/trackers", "/api/v1/acquisition/downloads", "/api/v1/acquisition/obligations", "/api/v1/config/schema"];

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
// Les Zinzins de l'Espace, still downloading: never searched on either tracker, and
// nothing offered until it is complete.
export const UNSEARCHED = "c44e8cd75bec37a8337175c6580e85d4e2079da3";
// Ted Lasso, its whole title excluded.
export const EXCLUDED = "e1af6819d9e3159e0aa191b534b6a66af4344788";
// American Dad!, seeding, refused on v3x.club for a mismatch: nothing cross-seeds
// there, so « Créer et publier un torrent » is offered (L23 § 2.3).
export const UPLOADABLE = "e5c6f4e9bc5d619c15aa476ec0e278f2267bf0bb";

/**
 * A DERIVATION, SHOWN AS ONE: Les Zinzins finished downloading, so the engine
 * would search it — its pairs no longer wait on the original.
 */
function completeUnsearched(): void {
  window.__mocks?.poseEntry(UNSEARCHED, { state: "seeding", progress: 1 });
  for (const tracker of ["tr4ker", "v3x.club"]) window.__mocks?.poseCrossSeedPair(UNSEARCHED, tracker, { waitReason: null });
}

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
  owed(() => {
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
  owed(() => {
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
      "Torrents — « Chercher un cross-seed » offert sur les paires pas encore cherchées, l'original terminé, le quota du moteur dit (INVENTÉ, POSÉ)",
      () => torrentPanel(`${UNSEARCHED}:c411`, completeUnsearched),
    ],
    [
      "torrents-cross-seed-search-queued",
      "Torrents — la recherche est en file, dite ; le quota du jour atteint, elle partira demain (INVENTÉ, POSÉ)",
      () => torrentPanel(`${UNSEARCHED}:c411`, () => {
        completeUnsearched();
        window.__mocks?.poseCrossSeedQuotaSpent();
        window.__mocks?.poseCrossSeedPair(UNSEARCHED, "tr4ker", { searching: true });
      }),
    ],
    // ── L23: « Créer et publier un torrent » (§ 19 point 5, round 11) ──
    [
      "torrents-cross-seed-upload",
      "Torrents — « Créer et publier un torrent » offert là où rien ne cross-seed, l'original en partage (INVENTÉ, L23 § 2.3)",
      () => torrentPanel(`${UPLOADABLE}:c411`),
    ],
    [
      "torrents-cross-seed-upload-confirm",
      "Torrents — confirmer la publication sur v3x.club : le tracker et les fichiers nommés (INVENTÉ)",
      () => torrentPanel(`${UPLOADABLE}:c411`, () => undefined, () => openUploadConfirm(UPLOADABLE, "v3x.club")),
    ],
    [
      "torrents-cross-seed-upload-queued",
      "Torrents — la publication est en file, dite, jamais « occupé » (INVENTÉ, POSÉ)",
      () => torrentPanel(`${UPLOADABLE}:c411`, () => window.__mocks?.poseCrossSeedPair(UPLOADABLE, "v3x.club", { uploading: true })),
    ],
    [
      "torrents-cross-seed-upload-refused-creation",
      "Torrents — la création du torrent a échoué : « erreur de cross-seed », sa phrase (INVENTÉ, POSÉ)",
      () => torrentPanel(`${UPLOADABLE}:c411`,
        () => window.__mocks?.posePairRefusedByUpload(UPLOADABLE, "v3x.club", "creation_failed")),
    ],
    [
      "torrents-cross-seed-upload-refused-publish",
      "Torrents — le tracker a refusé la publication : sa phrase et la raison du tracker (INVENTÉ, POSÉ)",
      () => torrentPanel(`${UPLOADABLE}:c411`,
        () => window.__mocks?.posePairRefusedByUpload(UPLOADABLE, "v3x.club", "publish_failed")),
    ],
    [
      "tracker-upload-disabled",
      "Tracker — v3x.club n'accepte pas les uploads, son cross-seed actif (INVENTÉ, POSÉ)",
      () => trackerPanel("v3x.club", () => window.__mocks?.poseUploadsOff("v3x.club")),
    ],
    [
      "torrents-cross-seed-published",
      "Torrents — un torrent publié par vous sur tr4ker, sa marque d'origine à part (INVENTÉ, POSÉ, round 11 OPEN 5)",
      () => torrentPanel(`${COPY}:tr4ker`, () => {
        window.__mocks?.poseEntry(COPY, { provenance: "published" });
        window.__mocks?.poseCrossSeedPair(CROSS_SEEDING, "tr4ker", { via: "upload" });
      }),
    ],
  ];
}
