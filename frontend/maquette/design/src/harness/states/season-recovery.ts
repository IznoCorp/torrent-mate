// The named states of a whole season's recovery — the season's acquisition
// card, the episodes it covers, and how it ends (DESIGN maquette-season-recovery § 3).
//
// A FILE OF ITS OWN: the recovery is one subject that draws on three surfaces —
// « En cours », « À traiter », and the rows and journeys the later phases add —
// and `acquisition.ts` would pass its ceiling holding it.
//
// THE DENSE WORLD HOLDS THE RECOVERY RUNNING (Silo S03, its episode S03E07
// covered). Every other moment is POSED on it, never seeded (RULINGS 7).
import { applyState, type NamedState } from "../drive";

// The subject the dense world holds, and the one-off R158 draws.
const SERIES = "Silo";
const SEASON = 3;
const ONE_OFF = "Les aventures de Tintin";
const ONE_OFF_SEASON = 2;
// The season pack the dense world's releases hold, its line's tail once arrived.
const PACK = "MULTi · 1080p";

/** Drops the queue the reset already asked for, so the page asks the posed world again. */
function forgetQueue(): void {
  window.__queries?.removeQueries({ queryKey: ["/api/acquisition/to-handle"] });
}

/** « En cours », in the dense world. */
function now(): void {
  applyState({ page: "acq", acqTab: "now", scen: "loaded", phase: "ready" });
}

/**
 * Asks for a season the way the sheet's act does — through the layer's own
 * verb, so the world moves as a finger's ask moves it.
 *
 * @param title The series.
 * @param season The season, 1-based.
 */
async function ask(title: string, season: number): Promise<void> {
  const path = `/api/acquisition/follows/${encodeURIComponent(title)}/seasons/${season}/grab`;
  await fetch(path, { method: "POST" });
  forgetQueue();
}

export function seasonRecoveryStates(): NamedState[] {
  return [
    [
      "season-card-requested",
      "Récupération de saison — la carte de « Silo » S03 à peine demandée par le suivi, dans « En cours »",
      () => {
        window.__mocks?.seasonRecovery.beforeAsk(SERIES, SEASON);
        void ask(SERIES, SEASON).then(now);
      },
    ],
    [
      "season-card-searched-nothing",
      "Récupération de saison — la carte cherche encore, aucune release trouvée",
      () => {
        window.__mocks?.seasonRecovery.searching(SERIES, SEASON);
        forgetQueue();
        now();
      },
    ],
    [
      "season-card-downloading",
      "Récupération de saison — la carte en téléchargement (le monde dense au repos)",
      now,
    ],
    [
      "season-card-arrived",
      "Récupération de saison — le pack est arrivé dans la zone de transit, joint à la carte",
      () => {
        window.__mocks?.seasonRecovery.arrived(SERIES, SEASON, PACK);
        forgetQueue();
        now();
      },
    ],
    [
      "season-card-blocked",
      "Récupération de saison — la carte arrêtée pour votre main, dans « À traiter »",
      () => {
        window.__mocks?.seasonRecovery.blocked(SERIES, SEASON);
        forgetQueue();
        applyState({ page: "acq", acqTab: "todo", scen: "loaded", phase: "ready" });
      },
    ],
    [
      "season-card-one-off",
      "Récupération de saison — une saison d'une série non suivie, demandée une fois",
      () => {
        void ask(ONE_OFF, ONE_OFF_SEASON).then(now);
      },
    ],
    [
      "season-card-automatic",
      "Récupération de saison — lancée par le moteur, « S03 · auto »",
      () => {
        window.__mocks?.seasonRecovery.automatic(SERIES, SEASON);
        forgetQueue();
        now();
      },
    ],
    [
      "season-recovery-before-ask",
      "Récupération de saison — avant la demande : la carte S03E07 dans « En cours »",
      () => {
        window.__mocks?.seasonRecovery.beforeAsk(SERIES, SEASON);
        forgetQueue();
        now();
      },
    ],
    [
      "season-recovery-absorbs-episode",
      "Récupération de saison — après la demande : S03E07 absorbé, la carte de la saison le couvre",
      () => {
        window.__mocks?.seasonRecovery.beforeAsk(SERIES, SEASON);
        void ask(SERIES, SEASON).then(now);
      },
    ],
    [
      "season-recovery-closed-short",
      "Récupération de saison — close à court : les épisodes manquants redeviennent des cartes ordinaires",
      () => {
        window.__mocks?.seasonRecovery.ended(SERIES, SEASON, "closedShort");
        forgetQueue();
        now();
      },
    ],
    [
      "season-recovery-abandoned",
      "Récupération de saison — abandonnée : la carte s'en va, rien n'est relancé",
      () => {
        window.__mocks?.seasonRecovery.ended(SERIES, SEASON, "abandoned");
        forgetQueue();
        now();
      },
    ],
  ];
}
