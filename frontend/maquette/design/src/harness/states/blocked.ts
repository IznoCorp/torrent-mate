// The named states of « À traiter » holding every block (Q7, Q8, Q9) — the
// maquette-blocked lot's own file (its DESIGN § 0.1 item 11: `tunnel.ts` is
// near its ceiling).
//
// Each entry is `[id, label, run]`, as every state file's. A block is a
// DERIVATION, SHOWN AS ONE: no real card is stopped by an external cause, so
// the cause is posed (`poseBlock`) on a real acquisition, and the backend
// serves it (BK1).
import { applyState, type NamedState } from "../drive";
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
/** A tunnel error on a follow's card, the judgement's third kind. */
const tunnelError = () => window.__mocks?.poseTunnelError(TUNNEL_ERROR, "scrape");
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
    // THE LIST WHOLE — one card per cause, flat, in the urgency order.
    posed("acq-todo-every-cause",
      "À traiter — une carte par cause, à plat, par urgence : jugement, puis ce qui repart seul",
      EVERY_CAUSE, { before: tunnelError }),
    posed("acq-todo-external-only",
      "À traiter — rien que des blocages extérieurs : la note du vide n'est pas dessinée",
      [[SUBJECT, "insufficient_space"]], { before: () => window.__mocks?.clearBlocked() }),
    posed("acq-todo-filter-panel",
      "À traiter — le panneau du filtre ouvert : chaque cause avec son nombre de cartes",
      EVERY_CAUSE, { before: tunnelError, after: () => tapPill("data-todo-filter-pill") }),
    posed("acq-todo-filter-disks",
      "À traiter — filtré sur « Disque plein »",
      EVERY_CAUSE, { before: tunnelError, dials: { todoFilter: "disks" } }),
    posed("acq-todo-filter-empty",
      "À traiter — un filtre sans carte : ses propres mots",
      EVERY_CAUSE, { before: tunnelError, dials: { todoFilter: "plex" } }),
    posed("acq-todo-sort-panel",
      "À traiter — le panneau du tri ouvert",
      EVERY_CAUSE, { before: tunnelError, after: () => tapPill("data-todo-sort-pill") }),
    posed("acq-todo-sort-oldest",
      "À traiter — trié « Plus ancien »",
      EVERY_CAUSE, { before: tunnelError, dials: { todoSort: "oldest" } }),
  ];
}
