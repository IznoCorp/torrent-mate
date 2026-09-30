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
const ONE_OFF_SEASON = 3;
// The season pack the dense world's releases hold, its line's tail once arrived.
const PACK = "MULTi · 1080p";

/** Drops the queue the reset already asked for, so the page asks the posed world again. */
function forgetQueue(): void {
  window.__queries?.removeQueries({ queryKey: ["/api/acquisition/to-handle"] });
}

/** Drops the seasons reads already held, so a surface reads what a posed shelving put in the library. */
function forgetSeasons(): void {
  window.__queries?.removeQueries({ queryKey: ["/api/media"] });
}

/** One acquisition's journey, over « Suivis », in the dense world. */
function journey(subject: string): void {
  applyState({ page: "acq", acqTab: "follows", scen: "loaded", phase: "ready" });
  window.__panel.produce("journey", subject);
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

/** The media sheet of the subject, in the dense world, opened as a tap on its card opens it. */
function sheet(title: string): void {
  applyState({ page: "lib", scen: "loaded", phase: "ready" });
  window.__screens.mediaSheet(title, window.__carriedFor(title) ?? undefined);
}

/** The follow panel of the subject, over « Suivis », in the dense world. */
function followPanel(title: string): void {
  applyState({ page: "acq", acqTab: "follows", scen: "loaded", phase: "ready" });
  window.__panel.produce("follow", title);
}

// How long the act is looked for once the surface is asked for, and how often.
const ACT_WAIT = 3000;
const ACT_POLL = 100;

/**
 * Taps « Récupérer la saison N » once its surface has drawn it — a finger's
 * tap, so the interface's own verb says what came back.
 *
 * @param title The series.
 * @param season The season, 1-based.
 */
function tapAct(title: string, season: number): void {
  const started = Date.now();
  const look = () => {
    const act = document.querySelector<HTMLElement>(`[data-grab-season="${CSS.escape(`${title}|${season}`)}"]`);
    if (act !== null) act.click();
    else if (Date.now() - started < ACT_WAIT) window.setTimeout(look, ACT_POLL);
  };
  look();
}

// The sheet the subject's library holds it under.
const SERIES_SHEET = "Silo (2023)";
// Long enough that the ask is still in flight when the surface is measured.
const HELD_BACK = 60000;

export function seasonRecoveryStates(): NamedState[] {
  return [
    // ── S1 — the season's row, on both surfaces ────────────────────────────
    [
      "season-row-requested-sheet",
      "Ligne de saison — « Demandée » sur la fiche de Silo (suivie)",
      () => sheet(SERIES_SHEET),
    ],
    [
      "season-row-requested-panel",
      "Ligne de saison — « Demandée » sur la fiche de suivi de Silo",
      () => followPanel(SERIES),
    ],
    [
      "season-row-requested-one-off",
      "Ligne de saison — « Demandée » sur la fiche d'une série non suivie (ponctuelle)",
      () => {
        void ask(ONE_OFF, ONE_OFF_SEASON).then(() => sheet(ONE_OFF));
      },
    ],
    [
      "season-row-requested-automatic-sheet",
      "Ligne de saison — « Demandée · auto » sur la fiche, lancée par le moteur",
      () => {
        window.__mocks?.seasonRecovery.automatic(SERIES, SEASON);
        forgetQueue();
        sheet(SERIES_SHEET);
      },
    ],
    [
      "season-row-requested-automatic-panel",
      "Ligne de saison — « Demandée · auto » sur la fiche de suivi, lancée par le moteur",
      () => {
        window.__mocks?.seasonRecovery.automatic(SERIES, SEASON);
        forgetQueue();
        followPanel(SERIES);
      },
    ],
    [
      "season-row-queued",
      "Ligne de saison — « En file — pipeline en cours » tant que la demande attend",
      () => {
        window.__mocks?.seasonRecovery.beforeAsk(SERIES, SEASON);
        window.__mocks?.setPipelineState("running");
        forgetQueue();
        followPanel(SERIES);
        tapAct(SERIES, SEASON);
      },
    ],
    [
      "season-row-queue-loading",
      "Ligne de saison — la demande part : l'acte occupé, aucune marque encore",
      () => {
        window.__mocks?.seasonRecovery.beforeAsk(SERIES, SEASON);
        window.__mocks?.setOperationOutcome("grabSeasonForFollow", { latencyMilliseconds: HELD_BACK });
        forgetQueue();
        followPanel(SERIES);
        tapAct(SERIES, SEASON);
      },
    ],
    [
      "season-row-queue-unread",
      "Ligne de saison — la file n'a pas pu être lue : aucune marque affirmée, l'acte offert",
      () => {
        window.__mocks?.setOperationOutcome("readAcquisitionQueue", { status: 500 });
        forgetQueue();
        followPanel(SERIES);
      },
    ],
    [
      "season-row-ask-failed",
      "Ligne de saison — la demande est refusée : le refus est dit, l'acte reste offert",
      () => {
        window.__mocks?.seasonRecovery.beforeAsk(SERIES, SEASON);
        window.__mocks?.setOperationOutcome("grabSeasonForFollow", { status: 500 });
        forgetQueue();
        followPanel(SERIES);
        tapAct(SERIES, SEASON);
      },
    ],
    [
      "season-row-ask-held",
      "Ligne de saison — hors ligne : la demande est retenue, et dite retenue",
      () => {
        window.__mocks?.seasonRecovery.beforeAsk(SERIES, SEASON);
        forgetQueue();
        followPanel(SERIES);
        window.setTimeout(() => {
          window.__mocks?.setOffline(true);
          tapAct(SERIES, SEASON);
        }, ACT_WAIT / 3);
      },
    ],
    // ── S2 — the season's acquisition card ─────────────────────────────────
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
    // ── S2's journey, S3's covered episode, S4 — the pointer ───────────────
    [
      "season-card-journey",
      "Récupération de saison — le parcours de la saison, qui liste l'épisode qu'elle couvre",
      () => journey(`${SERIES}|S03`),
    ],
    [
      "season-recovery-absorbed-downloading",
      "Récupération de saison — le parcours de la saison nomme S03E07, « téléchargement déjà en cours »",
      () => journey(`${SERIES}|S03`),
    ],
    [
      "absorbed-journey-pointer",
      "Parcours d'un épisode couvert — la note et « Voir la carte de la saison »",
      () => journey(`${SERIES}|S03E07`),
    ],
    [
      "absorbed-journey-pointer-blocked",
      "Parcours d'un épisode couvert — la carte de la saison arrêtée : le renvoi mène à « À traiter »",
      () => {
        window.__mocks?.seasonRecovery.blocked(SERIES, SEASON);
        forgetQueue();
        journey(`${SERIES}|S03E07`);
      },
    ],
    [
      "absorbed-journey-pointer-ended",
      "Parcours d'un épisode couvert — la saison est en médiathèque : « Voir la fiche »",
      () => {
        window.__mocks?.seasonRecovery.shelved(SERIES, SEASON);
        forgetQueue();
        journey(`${SERIES}|S03E07`);
      },
    ],
    // ── S6 — the end, on the rows ──────────────────────────────────────────
    [
      "season-recovery-shelved-sheet",
      "Récupération de saison — rangée : la fiche lit 7/7, plus de marque",
      () => {
        window.__mocks?.seasonRecovery.shelved(SERIES, SEASON);
        forgetQueue();
        forgetSeasons();
        sheet(SERIES_SHEET);
      },
    ],
    [
      "season-recovery-shelved-panel",
      "Récupération de saison — rangée : la fiche de suivi lit 7/7, plus de marque",
      () => {
        window.__mocks?.seasonRecovery.shelved(SERIES, SEASON);
        forgetQueue();
        forgetSeasons();
        followPanel(SERIES);
      },
    ],
  ];
}
