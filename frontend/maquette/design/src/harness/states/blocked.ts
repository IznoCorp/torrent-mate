// The named states of « À traiter » holding every block (Q7, Q8, Q9), and of
// the one pill on the Médiathèque and Suivis (§ 1.9) — the maquette-blocked
// lot's own file (its DESIGN § 0.1 item 11: `tunnel.ts` is
// near its ceiling).
//
// Each entry is `[id, label, run]`, as every state file's. A block is a
// DERIVATION, SHOWN AS ONE: no real card is stopped by an external cause, so
// the cause is posed (`poseBlock`) on a real acquisition, and the backend
// serves it (BK1).
import { applyState, type NamedState } from "../drive";
import { as } from "./rights";
import type { BlockDetails } from "../../mocks/handlers/posed-block";

// The one acquisition in flight of the dense world that has not arrived: the
// subject of every deferral since R265.
const SUBJECT = "This City Is Ours";

/**
 * The queue's reads dropped, so the next draw reads what was just posed.
 */
function dropQueue(): void {
  window.__queries?.removeQueries({ queryKey: ["/api/acquisition/to-handle"] });
  window.__queries?.removeQueries({ queryKey: ["/api/staging/media"] });
}

/** One block to pose: the acquisition's key, the cause, what it names. */
type Pose = [string, string, BlockDetails?];

/** What a state does besides posing its blocks. */
type Options = {
  /** Poses what is not a block — a tunnel error, an empty list — before the blocks. */
  before?: () => void;
  /** The dials it pins on « À traiter » — a filter, a sort. */
  dials?: Record<string, unknown>;
  /** Acts once « À traiter » is drawn — a pill tapped. */
  after?: () => void;
};

// How long after « À traiter » is asked for a pill is tapped: the read has to
// answer and the tab draw before there is a pill to tap.
const TAP_AFTER = 400;

/**
 * One state: blocks posed on acquisitions, « À traiter » drawn.
 *
 * @param id The state's id.
 * @param label What it shows, in words.
 * @param poses The blocks it poses.
 * @param extra What else it does.
 * @returns The named state.
 */
function posed(id: string, label: string, poses: Pose[], extra: Options = {}): NamedState {
  return [id, label, () => {
    window.__mocks?.reset();
    extra.before?.();
    for (const [title, cause, details] of poses) window.__mocks?.poseBlock(title, cause, details);
    dropQueue();
    applyState({ page: "acq", acqTab: "todo", scen: "loaded", phase: "ready", ...extra.dials });
    if (extra.after !== undefined) window.setTimeout(extra.after, TAP_AFTER);
  }];
}

/**
 * Taps one of « À traiter »'s pills, the way a finger does.
 *
 * @param pill The pill's verb attribute.
 */
function tapPill(pill: string): void {
  document.querySelector<HTMLElement>(`#view [${pill}]`)?.click();
}

/**
 * A finger on one card's door, the way a finger does.
 *
 * @param key The acquisition the card stands for.
 */
function tapDoor(key: string): void {
  document.querySelector<HTMLElement>(`#view [data-part="card"][data-acquisition="${CSS.escape(key)}"] [data-go]`)?.click();
}

/**
 * A finger on one card's body: its bottom panel rises.
 *
 * @param key The acquisition the card stands for.
 */
function tapCard(key: string): void {
  document.querySelector<HTMLElement>(`#view [data-part="card"][data-acquisition="${CSS.escape(key)}"] [data-part="card/body"]`)?.click();
}

// How long after the finger on a card its panel has the reads it needs to
// offer its acts.
const PANEL_READY = 900;

/**
 * « Marquer comme vu », the way a finger does it: on the card, then on the act
 * of its panel (DECIDED 2).
 *
 * @param key The closed acquisition.
 */
function markSeen(key: string): void {
  tapCard(key);
  window.setTimeout(() => document.querySelector<HTMLElement>("#sheet[data-open] [data-closure-seen]")?.click(), PANEL_READY);
}

// An account that reads every card of « À traiter » and may not open Système.
const WITHOUT_SYSTEM = "household-member-sees-all";
// How long ago Plex stopped answering, on Système's own state.
const PLEX_DOWN_FOR = 25;

// The dense world's cards in flight, by the key their ladder is held under.
const SEASON_IN_FLIGHT = "Silo|S03";
const SECOND_SERIES = "President Curtis";
const TUNNEL_ERROR = "Furious";
// Its arrivals on their way, both films.
const FIRST_FILM = "Conclave";
const SECOND_FILM = "The Alabama Solution";
// One card per cause, in no order of urgency: the list orders them.
const EVERY_CAUSE: Pose[] = [
  [SUBJECT, "insufficient_space", { minutesAgo: 40 }],
  [SECOND_SERIES, "ratio_below_threshold", { tracker: "c411", minutesAgo: 5 }],
  [SEASON_IN_FLIGHT, "tracker_unreachable", { tracker: "c411", minutesAgo: 90 }],
  [FIRST_FILM, "provider_unreachable", { provider: "TMDB", minutesAgo: 20 }],
];
// What qBittorrent's outage holds on the lift of many: every card in flight
// but the subject, which another cause holds.
const HELD_BY_CLIENT = [SEASON_IN_FLIGHT, SECOND_SERIES, TUNNEL_ERROR];
/** A tunnel error on a follow's card, the judgement's third kind. */
const tunnelError = () => window.__mocks?.poseTunnelError(TUNNEL_ERROR, "scrape");
/** The list whole: the tunnel error, and a closure not yet seen — the third group (DECIDED 1). */
const everyCause = () => {
  tunnelError();
  window.__mocks?.poseClosure(SECOND_FILM, "torrent_removed", null, { minutesAgo: 60 });
};
// THE CLOSURES (Q8, Q9): the season's pack and the episode chosen before it,
// the film's 1080p chosen after its 2160p — each release line as its torrent
// carries it.
const SUPERSEDED_EPISODE = "Silo|S03E07";
const PACK_RELEASE = "Silo.S03.MULTi.1080p.WEB-DL.DDP5.1.H264-FRATERNITY";
const FILM_IN_PLACE = "Conclave.2024.MULTi.1080p.WEB-DL.H264-FW";
const FILM_SUPERSEDED = "Conclave.2024.MULTi.2160p.WEB-DL.DV.HDR.H265-FW";
/** This City Is Ours' torrent removed from qBittorrent half an hour ago. */
const torrentRemoved = () => window.__mocks?.poseClosure(SUBJECT, "torrent_removed", null, { minutesAgo: 30 });
/** Silo · S03E07 arrived after the season's pack, filed and verifying. */
const supersededEpisode = () => {
  window.__mocks?.poseFiled(SEASON_IN_FLIGHT);
  window.__mocks?.poseClosure(SUPERSEDED_EPISODE, "superseded", PACK_RELEASE, { minutesAgo: 15 });
};
// What a film needs, in bytes, for a library with no disk to receive it.
const FILM_SIZE = 58_000_000_000;

export function blockedStates(): NamedState[] {
  return [
    // MOVED (Q7): the deferred card leaves « En cours » for « À traiter », ids kept.
    posed("acq-card-deferred-ratio",
      "À traiter — un torrent terminé différé pour ratio sous le seuil de c411, POSÉ sur This City Is Ours (le back-end servira la cause — BK1)",
      [[SUBJECT, "ratio_below_threshold", { tracker: "c411" }]]),
    posed("acq-card-deferred-space",
      "À traiter — un torrent terminé différé faute d'espace sur le disque de staging, POSÉ sur This City Is Ours",
      [[SUBJECT, "insufficient_space"]]),
    posed("acq-card-deferred-missing",
      "À traiter — un torrent terminé différé, le disque où qBittorrent l'a téléchargé illisible, POSÉ sur This City Is Ours",
      [[SUBJECT, "content_missing"]]),
    // THE FIVE CAUSES Q7 ADDS, and the ratio with no threshold, each on one card.
    posed("acq-block-ratio-no-threshold",
      "À traiter — différé pour ratio sur tr4ker, qui n'a aucun seuil réglé, POSÉ sur This City Is Ours",
      [[SUBJECT, "ratio_below_threshold", { tracker: "tr4ker" }]]),
    posed("acq-block-library-full",
      "À traiter — aucun disque de la médiathèque n'a la place, POSÉ sur President Curtis (le back-end lira l'espace des disques — BK1)",
      [[SECOND_SERIES, "library_full", { size: 4_200_000_000 }]]),
    posed("acq-block-tracker-unreachable",
      "À traiter — c411 ne répond pas, POSÉ sur Silo · S03 (le back-end lira la joignabilité du tracker — BK6)",
      [[SEASON_IN_FLIGHT, "tracker_unreachable", { tracker: "c411" }]]),
    posed("acq-block-provider-unreachable",
      "À traiter — TMDB ne répond pas, l'identification attend, POSÉ sur Conclave",
      [[FIRST_FILM, "provider_unreachable", { provider: "TMDB" }]]),
    posed("acq-block-plex-unreachable",
      "À traiter — Plex ne répond pas, la vérification attend, POSÉ sur The Alabama Solution",
      [[SECOND_FILM, "plex_unreachable"]]),
    posed("acq-block-client-unreachable",
      "À traiter — qBittorrent ne répond pas : CHAQUE carte en vol tenue à la fois",
      [SEASON_IN_FLIGHT, SECOND_SERIES, TUNNEL_ERROR, SUBJECT].map((key, index): Pose => [key, "client_unreachable", { minutesAgo: index }])),
    posed("acq-block-film",
      "À traiter — un FILM tenu par une médiathèque pleine, POSÉ sur Conclave",
      [[FIRST_FILM, "library_full", { size: FILM_SIZE }]]),
    posed("acq-block-content-volume",
      "À traiter — le disque où qBittorrent l'a téléchargé n'est pas lisible : un blocage, pas une clôture (DECIDED 4)",
      [[SUBJECT, "content_missing"]]),
    // THE DOORS (§ 1.3) — after the finger on each, where it landed.
    posed("acq-block-door-disks",
      "Système, « Disques » en vue — après le doigt sur « Voir les disques » d'une carte différée faute d'espace",
      [[SUBJECT, "insufficient_space"]], { after: () => tapDoor(SUBJECT) }),
    posed("acq-block-door-dependencies",
      "Système, « Dépendances » en vue, Plex hors ligne — après le doigt sur « Voir les dépendances »",
      [[SECOND_FILM, "plex_unreachable", { minutesAgo: 12 }]], { after: () => tapDoor(SECOND_FILM) }),
    posed("acq-block-door-tracker",
      "Trackers, le panneau de c411 « Ne répond pas depuis … » — après le doigt sur « Voir le tracker »",
      [[SEASON_IN_FLIGHT, "tracker_unreachable", { tracker: "c411", minutesAgo: 30 }]],
      { after: () => tapDoor(SEASON_IN_FLIGHT) }),
    posed("acq-block-door-reserved",
      "À traiter, un compte sans « system.view » : la cause et ce qui la lève, aucune porte",
      [[SUBJECT, "insufficient_space"]], { before: () => as(WITHOUT_SYSTEM) }),
    ["system-dependency-plex-down",
      "Système — Plex parmi les dépendances, hors ligne depuis 25 min (le back-end servira la joignabilité — BK6)",
      () => {
        window.__mocks?.reset();
        window.__mocks?.poseServiceDown("Plex", PLEX_DOWN_FOR);
        window.__queries?.removeQueries({ queryKey: ["/api/system/dependencies"] });
        applyState({ page: "sys", phase: "ready", fault: false });
      }],
    // THE AUTO-RESUME (§ 1.4) — the engine lifts, the card leaves on its own.
    posed("acq-block-lifted",
      "En cours — après que le moteur a levé la cause : This City Is Ours y est revenu, l'échelon « arrivé » en cours",
      [[SUBJECT, "insufficient_space"]],
      { dials: { acqTab: "now" }, after: () => window.__mocks?.liftBlock(SUBJECT) }),
    posed("acq-block-lifted-many",
      "À traiter — qBittorrent répond de nouveau : chaque carte qu'il tenait est repartie, celle d'une autre cause reste",
      [...HELD_BY_CLIENT.map((key, index): Pose => [key, "client_unreachable", { minutesAgo: index }]),
        [SUBJECT, "insufficient_space"]],
      { after: () => window.__mocks?.liftCause("client_unreachable") }),
    posed("acq-resumed-message",
      "À traiter — le moteur lève la cause sous ses yeux : le message « This City Is Ours est reparti »",
      [[SUBJECT, "insufficient_space"]], { after: () => window.__mocks?.liftBlock(SUBJECT) }),
    posed("acq-block-lifted-journey",
      "Le parcours de This City Is Ours après la reprise : « bloqué — disque de staging plein » puis « repris »",
      [[SUBJECT, "insufficient_space", { minutesAgo: 40 }]],
      { after: () => {
        window.__mocks?.liftBlock(SUBJECT);
        window.__panel.produce("journey", SUBJECT);
      } }),
    // THE CLOSURES (Q8) — a vanished medium, said once, « Marquer comme vu » in its panel.
    posed("acq-closure-torrent-removed",
      "À traiter — le torrent de This City Is Ours retiré de qBittorrent : le parcours est clos, dit une fois (le back-end le fermera — BK3)",
      [], { before: torrentRemoved }),
    posed("acq-closure-files-absent",
      "À traiter — les fichiers de President Curtis disparus d'un disque présent : le parcours est clos (DECIDED 4)",
      [], { before: () => window.__mocks?.poseClosure(SECOND_SERIES, "files_absent") }),
    posed("acq-closure-panel",
      "Le panneau de la carte close : « Marquer comme vu » parmi ses actions — après le doigt sur la carte",
      [], { before: torrentRemoved, after: () => tapCard(SUBJECT) }),
    posed("acq-closure-seen",
      "À traiter — après le doigt sur « Marquer comme vu » : la carte est partie, le badge −1 (le vu est au back-end — BK5)",
      [], { before: torrentRemoved, after: () => markSeen(SUBJECT) }),
    posed("acq-closure-dismiss-failed",
      "À traiter — « Marquer comme vu » refusé par le serveur : la carte revient, l'erreur est dite",
      [], { before: () => {
        torrentRemoved();
        window.__mocks?.setOperationOutcome("dismissClosure", { status: 500 });
      }, after: () => markSeen(SUBJECT) }),
    posed("acq-closure-filed-by-hand",
      "À traiter — This City Is Ours rangé à la main ailleurs : son parcours finit sans carte",
      [], { before: () => window.__mocks?.poseFiledByHand(SUBJECT) }),
    posed("acq-closure-medium-back",
      "En cours et À traiter — le média revenu ouvre un nouveau parcours, l'ancien clos pas encore vu reste dit",
      [], { before: () => {
        torrentRemoved();
        window.__mocks?.poseMediumBack(SUBJECT);
      } }),
    // SUPERSEDED (Q9) — the last chosen wins; the earlier one is said once, its torrent seeding.
    posed("acq-superseded-episode",
      "À traiter — Silo · S03E07, choisi avant le pack de la saison et arrivé après : remplacé, son torrent sème (BK4)",
      [], { before: supersededEpisode }),
    posed("acq-superseded-film",
      "À traiter — le 2160p de Conclave, choisi avant le 1080p en place : remplacé, son torrent sème",
      [], { before: () => window.__mocks?.poseClosure(FIRST_FILM, "superseded", FILM_IN_PLACE,
        { release: FILM_SUPERSEDED, minutesAgo: 10 }) }),
    posed("acq-superseded-seen",
      "À traiter — après « Marquer comme vu » sur Silo · S03E07 : la carte est partie, le badge −1",
      [], { before: supersededEpisode, after: () => markSeen(SUPERSEDED_EPISODE) }),
    posed("acq-superseded-pack-keeps-newer",
      "Le parcours du pack Silo · S03 rangé, S03E07 gardé car choisi plus récemment : aucune carte",
      [], { before: () => window.__mocks?.poseKeptNewer(SEASON_IN_FLIGHT, ["S03E07"]),
        after: () => window.__panel.produce("journey", SEASON_IN_FLIGHT) }),
    // THE LIST WHOLE — one card per cause, flat, in the urgency order.
    posed("acq-todo-every-cause",
      "À traiter — une carte par cause, à plat, par urgence : jugement, puis ce qui repart seul, puis ce qui est clos",
      EVERY_CAUSE, { before: everyCause }),
    posed("acq-todo-external-only",
      "À traiter — rien que des blocages extérieurs : la note du vide n'est pas dessinée",
      [[SUBJECT, "insufficient_space"]], { before: () => window.__mocks?.clearBlocked() }),
    posed("acq-todo-filter-panel",
      "À traiter — le panneau du filtre ouvert : chaque cause avec son nombre de cartes",
      EVERY_CAUSE, { before: everyCause, after: () => tapPill("data-todo-filter-pill") }),
    posed("acq-todo-filter-disks",
      "À traiter — filtré sur « Disque plein »",
      EVERY_CAUSE, { before: everyCause, dials: { todoFilter: "disks" } }),
    posed("acq-todo-filter-empty",
      "À traiter — un filtre sans carte : ses propres mots",
      EVERY_CAUSE, { before: everyCause, dials: { todoFilter: "plex" } }),
    posed("acq-todo-sort-panel",
      "À traiter — le panneau du tri ouvert",
      EVERY_CAUSE, { before: everyCause, after: () => tapPill("data-todo-sort-pill") }),
    posed("acq-todo-sort-oldest",
      "À traiter — trié « Plus ancien »",
      EVERY_CAUSE, { before: everyCause, dials: { todoSort: "oldest" } }),
    // THE PILLS ELSEWHERE (§ 1.9): the Médiathèque and Suivis filter and sort
    // with « À traiter »'s one pill.
    ["library-filter-panel", "Médiathèque — le panneau du filtre ouvert : chaque catégorie avec son nombre de titres",
      () => pillsOf(LIBRARY, "data-library-filter-pill")],
    ["library-sort-panel", "Médiathèque — le panneau du tri ouvert : ses six façons, celle en vigueur cochée",
      () => pillsOf(LIBRARY, "data-sort")],
    ["library-filter-movies", "Médiathèque — filtrée sur « Films » : la pastille le dit, enfoncée, avec son nombre",
      () => pillsOf({ ...LIBRARY, libCat: "movies" })],
    ["follows-filter-panel", "Suivis — le panneau du filtre ouvert : Tout, Séries, Films avec leur nombre",
      () => pillsOf(FOLLOWS, "data-follows-filter-pill")],
    ["follows-sort-panel", "Suivis — le panneau du tri ouvert : ses cinq façons, « Urgence » cochée",
      () => pillsOf(FOLLOWS, "data-follows-sort-pill")],
    ["follows-sort-next-release", "Suivis — triés « Prochaine sortie » : la plus proche d'abord, sans date en dernier",
      () => pillsOf({ ...FOLLOWS, followSort: "nextRelease" })],
  ];
}

// The Médiathèque and Suivis as their pills' states draw them.
const LIBRARY = { page: "lib", libLens: "cat", libMode: "list", libCat: "all", q: "", phase: "ready", selMode: false };
const FOLLOWS = { page: "acq", acqTab: "follows", followMode: "list", pill: "tout", filter: "", phase: "ready" }; // french-ok: « tout » is the filter pill's id, a data value

/**
 * One page drawn with its pills, one of them tapped if asked.
 *
 * @param dials The page's dials.
 * @param pill The pill a finger taps once the page is drawn, if any.
 */
function pillsOf(dials: Record<string, unknown>, pill?: string): void {
  applyState(dials);
  if (pill !== undefined) window.setTimeout(() => tapPill(pill), TAP_AFTER);
}
