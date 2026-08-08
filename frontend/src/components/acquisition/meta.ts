/**
 * Acquisition panel metadata — shared mappings and pure helpers.
 *
 * Extracted from the former monolithic `AcquisitionPage.tsx` (C12) so the page
 * shell, the four panels, and their tests can each import only what they need.
 * Everything here is framework-agnostic (no JSX, no hooks) — status→tone/label
 * maps, cadence-temperature tokens, event-invalidation sets and the small
 * epoch/format helpers.
 */

import {
  type FollowedSeriesItem,
  type ObligationItem,
  type SeasonCompleteness,
} from "@/api/acquisition";
import type { BadgeTone } from "@/components/ui/badge";
import {
  OUTCOME_LABEL,
  OUTCOME_TONE,
  STATE_LABEL,
  STATE_TONE,
} from "@/lib/outcome-labels";
import { mediaSheetHref } from "@/lib/media-href";

/** View ids for the two panels (spec §3). */
export type TabId = "maintenant" | "suivis";

/**
 * Scheduler `name` of the automatic followed-search (grab) cron job (C15).
 *
 * The followed-search cadence caption is built from this scheduler's live
 * ``schedule`` string — never hardcoded — and omitted when the job is absent.
 */
export const GRAB_JOB_NAME = "personalscraper-grab";

/** Event types the page listens for (DESIGN §Live invalidation). */
export const ACQ_EVENT_TYPES = new Set([
  "SeriesFollowed",
  "SeriesUnfollowed",
  "WantedEnqueued",
  "WantedAbandoned",
  "GrabSucceeded",
  "GrabFailed",
  "GrabReswitched",
  "SeedObligationRecorded",
  "SeedObligationBreached",
  "SeedObligationSatisfied",
  "RatioMeasured",
  "WatcherRunTriggered",
]);

/** Events that invalidate the entire acquisition namespace. */
export const FULL_INVALIDATE_EVENTS = new Set([
  "SeriesFollowed",
  "SeriesUnfollowed",
]);

/** Events that invalidate the wanted + followed queries. */
export const WANTED_INVALIDATE_EVENTS = new Set([
  "WantedEnqueued",
  "WantedAbandoned",
  "GrabSucceeded",
  "GrabFailed",
  // A reswitch sends a dead-stalled item back to searching — the wanted/followed
  // views must refresh so the card stops reading « en cours » (reswitch, ticket 342).
  "GrabReswitched",
]);

/** Events that invalidate the obligations queries. */
export const OBLIGATION_INVALIDATE_EVENTS = new Set([
  "SeedObligationRecorded",
  "SeedObligationBreached",
  "SeedObligationSatisfied",
  "RatioMeasured",
]);

/**
 * The two views.
 *
 * Named after the operator's QUESTIONS, not after data tables. The former seven
 * tabs (apercu / followed / file / obligations / watcher / parcours / reglages)
 * were named after the tables behind them, which is why each of the operator's
 * three real questions cut across several of them.
 */
export const TABS: readonly { id: TabId; label: string }[] = [
  // Operator directive (2026-08-08, overrides the maquette pane order):
  // Suivis comes first and is the default view.
  { id: "suivis", label: "Suivis" },
  { id: "maintenant", label: "Maintenant" },
];

/** The default view — no ``?tab=`` param, /acquisition stays clean. */
export const DEFAULT_TAB: TabId = "suivis";

/** Old ``?tab=`` values → the view that now answers them (DOIT-10: no dead deep link). */
export const LEGACY_TAB_REDIRECTS: Readonly<Record<string, TabId>> = {
  apercu: "maintenant",
  file: "maintenant",
  wanted: "maintenant",
  downloads: "maintenant",
  obligations: "maintenant",
  watcher: "maintenant",
  parcours: "maintenant",
  followed: "suivis",
};

/** Allowed status filter values for the wanted queue (includes "all"). */
export type WantedFilter =
  | "all"
  | "pending"
  | "searching"
  | "grabbed"
  | "done"
  | "abandoned"
  | "absorbed"
  | "fallback_episodes";

/** Allowed status filter values for obligations (includes "all"). */
export type ObligationFilter = "all" | "pending" | "breached" | "satisfied";

/** Obligation status filter options. */
export const OBLIGATION_STATUS_OPTIONS = [
  { value: "all", label: "Toutes" },
  { value: "pending", label: "En cours" },
  { value: "breached", label: "Non respectée" },
  { value: "satisfied", label: "Respectée" },
];

/**
 * Status → badge tone mapping.
 *
 * On `absorbed`, see {@link STATUS_LABEL} — the queue serves it only when the
 * absorption pointer could not be followed.
 */
export const STATUS_TONE: Record<string, BadgeTone> = {
  ...STATE_TONE,
  killed: "warning",
  absorbed: "info",
  // R6: a season past cutoff degraded to per-episode retry — warning tone so
  // the fallback is visible in the queue, never the raw slug (review F8).
  fallback_episodes: "warning",
};

/**
 * Status → French label mapping.
 *
 * `absorbed` is the DANGLING-POINTER reading, not the normal one. Since ticket 411 the
 * backend resolves an absorbed row onto the season row carrying its acquisition
 * (§13: a state that points elsewhere must follow the pointer), so a queue row
 * normally arrives already reading « Terminé », « En attente », … A row still
 * labelled `absorbed` is one whose `absorbed_by` is NULL or points at a row that
 * no longer exists: we know a season carries it, not where that season stands.
 * « En cours d'acquisition » is the arbitrated reading of that unknown — it must
 * NOT be taken as « an absorbed episode is always being acquired », which is what
 * this map used to assert and what kept 31 finished rows lying for weeks.
 */
export const STATUS_LABEL: Record<string, string> = {
  ...STATE_LABEL,
  killed: "Arrêté",
  absorbed: "En cours d'acquisition",
  fallback_episodes: "Reporté en épisodes",
};

/**
 * French labels for ``wanted.last_grab_reason`` slugs (§8: rien en silence).
 *
 * Spoken by the takeable card when its grabs keep failing — the fallback for
 * an unknown slug is provided at the call site, so a new orchestrator reason
 * degrades to a generic sentence rather than a raw slug on screen.
 */
export const GRAB_FAILURE_LABEL: Record<string, string> = {
  fetch_failed:
    "le téléchargement du torrent échoue (fichier invalide côté tracker)",
  add_failed: "l'envoi au client torrent a échoué",
  circuit_open: "tracker en défaut, nouvel essai plus tard",
  no_torrent_client: "client torrent indisponible",
  trackers_unavailable: "trackers injoignables",
  trackers_degraded: "trackers partiellement en panne",
  search_api_error: "erreur du tracker pendant la recherche",
  no_seeders: "plus aucune source active",
  tracker_auth: "authentification tracker refusée",
};

/** Cadence temperature token colour (DS `--temp-*`), by tier. */
export const TEMP_COLOR: Record<string, string> = {
  hot: "var(--temp-hot)",
  warm: "var(--temp-warm)",
  cold: "var(--temp-cold)",
  cutoff: "var(--temp-cutoff)",
};

/** French label for a cadence temperature tier. */
export const TIER_LABEL: Record<string, string> = {
  hot: "recherche fréquente",
  warm: "recherche régulière",
  cold: "recherche espacée",
  cutoff: "abandonnée",
};

// ---------------------------------------------------------------------------
// The five-state vocabulary (acq-states phase 8)
// ---------------------------------------------------------------------------
//
// Vocabulary HOME. The shared ``@/lib/outcome-labels`` module owns the
// CROSS-DOMAIN run-outcome / generic item-state vocabulary (success, killed,
// pending, …), keyed by loose strings because a dozen unrelated surfaces feed
// it. The acquisition five states are a different animal: they are a CLOSED
// enum of the acquisition contract, and the whole point of phase 8 is that the
// maps be exhaustive against that enum. Typing them here — where
// ``FOLLOW_STATUS_LABEL`` / ``FOLLOW_STATUS_LABEL_MOVIE`` have lived since
// systeme-hub unified them — keeps ONE map per state family (never a second
// one) while giving `tsc` the exhaustiveness check that
// ``Record<string, …>`` can never provide. Extend HERE; never re-declare a
// follow/episode label anywhere else.
// ---------------------------------------------------------------------------

/**
 * Closed domain for what a unit IS — film, série, or season pack.
 *
 * ``"movie"`` — a single-unit catalog; acquired or not, never « suivi ».
 * ``"show"`` — a multi-episode surveillance that accrues over time.
 * ``"season"`` — a wanted row can carry a season pack; the card still reads
 * as its parent show.
 *
 * Every caller passes a server-boundary ``string`` and narrows it to this
 * union locally — never invent a duplicate union in a component file
 * (see the header comment of this file).
 */
export type MediaKind = "movie" | "show" | "season";

/**
 * Narrow a server ``kind`` string to the {@link MediaKind} union.
 *
 * Falls back to ``"show"`` for unknown values — never crashes on a new kind.
 */
export function asMediaKind(kind: string): MediaKind {
  if (kind === "movie" || kind === "show" || kind === "season") return kind;
  return "show";
}

/**
 * A followed card's lifecycle status — read STRAIGHT from the generated OpenAPI
 * contract, never re-typed by hand.
 *
 * Because the maps below are ``Record<FollowStatus, …>``, a server-side change
 * to the enum (a new state, a renamed one) breaks `npm run typecheck` instead
 * of silently rendering a raw slug like ``a_recuperer`` to the operator.
 */
export type FollowStatus = FollowedSeriesItem["status"];

/**
 * One aired episode's state — same contract-derived guarantee as
 * {@link FollowStatus}, plus the ``"absorbed"`` status added by the
 * season-grab feature (R5). ``absorbed`` only appears on WantedItem rows
 * (not in the completeness matrix yet), but the legend and badge maps
 * define it here so every rendering surface sees it.
 */
export type EpisodeState =
  | SeasonCompleteness["episodes"][number]["state"]
  | "absorbed";

/**
 * Followed-card status → badge tone (phase-08 vocabulary table).
 *
 * The table's ``muted`` tone for ``disabled`` IS the DS ``neutral`` chip
 * (``bg-muted`` / ``text-muted-foreground``) — the design system exposes no
 * separate ``muted`` badge tone, so the two names denote the same paint.
 */
export const FOLLOW_STATUS_TONE: Record<FollowStatus, BadgeTone> = {
  disabled: "neutral",
  verification_en_cours: "info",
  a_recuperer: "warning",
  en_acquisition: "info",
  // « En attente de torrent » (searched, nothing conforming yet) and « Non
  // vérifié » (no verdict at all yet) must NOT read as the same colour — and
  // neither may collide with « En cours d'acquisition ». Same pair as the
  // episode matrix: teal ``waiting`` vs the colourless dashed ``muted`` ghost.
  en_attente: "waiting",
  non_verifie: "muted",
  a_jour: "success",
};

/** Followed-card status → French badge label, série wording (§5). */
export const FOLLOW_STATUS_LABEL: Record<FollowStatus, string> = {
  disabled: "En pause",
  verification_en_cours: "Vérification en cours",
  a_recuperer: "À récupérer",
  en_acquisition: "En cours d'acquisition",
  en_attente: "En attente de torrent",
  non_verifie: "Non vérifié",
  a_jour: "À jour",
};

/**
 * Film-specific label overrides (D2-B).
 *
 * A film has no episode catalog, so « À jour » reads wrong on a movie card: it
 * is either acquired or it is not. Only the states whose série wording does not
 * fit a single unit are overridden; every other state keeps the shared label.
 * Presentational only — tones are shared with {@link FOLLOW_STATUS_TONE}.
 */
export const FOLLOW_STATUS_LABEL_MOVIE: Partial<Record<FollowStatus, string>> = {
  a_jour: "Acquis",
  // A film is not « en pause »: the operator simply stopped searching for it.
  disabled: "Recherche arrêtée",
};

// ---------------------------------------------------------------------------
// §9 — Film vs series action labelling
// ---------------------------------------------------------------------------

/** Action wording for one media nature. */
/**
 * The film lifecycle sentence (§5/§9): a non-acquired film leaves the list by
 * itself once acquired. No label said it — the operator saw films vanish, which
 * reads as loss rather than rule. Lives here because it is vocabulary, and the
 * detail sheet once shipped the REMOVAL-confirmation body in its place.
 */
/**
 * Chip paint per DS tone — ONE map (§13). A panel that hand-rolls this as a
 * ternary chain is a second derivation of the same answer, and the two drift.
 */
export const TONE_CHIP_CLASS: Record<string, string> = {
  warning: "bg-warning/20 text-warning",
  success: "bg-success/20 text-success",
  danger: "bg-danger/20 text-danger",
  info: "bg-info/20 text-info",
  waiting: "bg-waiting/20 text-waiting",
  muted: "bg-muted text-muted-foreground",
  neutral: "bg-muted text-muted-foreground",
};

/**
 * DS tone → episode-CELL paint — the square matrix cells of the detail sheet.
 *
 * Tinted background + toned number, per the maquette's 22 % mix; the
 * no-verdict ghost is a dashed outline, not a colour. The legend swatches
 * read {@link TONE_SWATCH_CLASS} — same tones, stronger mix — so cell and
 * key can never drift apart.
 */
export const TONE_CELL_CLASS: Record<string, string> = {
  success: "bg-success/20 text-success",
  warning: "bg-warning/20 text-warning",
  info: "bg-info/20 text-info",
  waiting: "bg-waiting/20 text-waiting",
  upcoming: "bg-upcoming/20 text-upcoming",
  muted: "border border-dashed border-border bg-transparent text-muted-foreground",
  neutral: "bg-muted text-muted-foreground",
};

/** DS tone → legend-swatch paint — 9 px squares at the maquette's 60 % mix. */
export const TONE_SWATCH_CLASS: Record<string, string> = {
  success: "bg-success/60",
  warning: "bg-warning/60",
  info: "bg-info/60",
  waiting: "bg-waiting/60",
  upcoming: "bg-upcoming/60",
  muted: "border border-dashed border-border bg-transparent",
  neutral: "bg-muted",
};

/**
 * DS tone → square section-pip classes — the ONE header grammar (§13).
 *
 * « Maintenant » paints its five fixed sections from SECTION_META; the grouped
 * « Suivis » headers derive theirs from the group's status tone through this
 * map, so the two surfaces speak the same visual language without a second
 * hand-rolled color derivation.
 */
export const TONE_PIP_CLASS: Record<string, string> = {
  warning: "bg-warning",
  success: "bg-success",
  danger: "bg-danger",
  info: "bg-info",
  waiting: "bg-waiting",
  muted: "bg-muted-foreground",
  neutral: "bg-muted-foreground",
};

export const MOVIE_LIFECYCLE_NOTE =
  "Une fois acquis, ce film quittera automatiquement votre liste.";

export interface ActionWords {
  readonly add: string;
  readonly added: string;
  readonly pause: string;
  readonly pauseShort: string;
  readonly resume: string;
  readonly resumeShort: string;
  readonly remove: string;
  readonly removeConfirmTitle: string;
  readonly removeConfirmBody: string;
}

/**
 * Action verbs, by media nature (§9).
 *
 * One does not *follow* a film: nothing accrues, and §5 removes it from the list
 * once acquired — so « Suivre » is true of a série (a surveillance that lasts)
 * and false of a film, which one adds once. The `…Short` forms are the swipe
 * labels, where the button is 84px wide.
 */
const ACTION_WORDS: Record<"movie" | "show", ActionWords> = {
  movie: {
    add: "Ajouter",
    added: "✓ Ajouté",
    pause: "Ne plus chercher",
    pauseShort: "Ne plus chercher",
    resume: "Chercher à nouveau",
    resumeShort: "Chercher",
    remove: "Retirer de la liste",
    removeConfirmTitle: "Retirer ce film de la liste ?",
    removeConfirmBody:
      "Ce film ne sera plus cherché et quittera votre liste. Vous pourrez le rajouter par une recherche.",
  },
  show: {
    add: "Suivre",
    added: "✓ Suivi",
    pause: "Mettre en pause",
    pauseShort: "Pause",
    resume: "Réactiver",
    resumeShort: "Activer",
    remove: "Retirer le suivi",
    removeConfirmTitle: "Retirer ce suivi ?",
    removeConfirmBody:
      "Cette série ne sera plus surveillée. Le suivi est désactivé, pas supprimé : vous pourrez le réactiver depuis le filtre « En pause ».",
  },
};

/**
 * Return the action vocabulary for a media kind.
 *
 * Args:
 *   kind: ``"movie"`` or anything else (a série, including ``"season"``).
 *
 * Returns:
 *   The wording set — never a raw token, whatever the input.
 */
export function actionWords(kind: string): ActionWords {
  return kind === "movie" ? ACTION_WORDS.movie : ACTION_WORDS.show;
}

/**
 * Followed-card status → the sentence that disambiguates it (tooltip / title).
 *
 * « En attente » and « Non vérifié » must NEVER be confusable: one says « I
 * searched the trackers and nothing was takeable », the other « I have no
 * verdict at all yet ». They now carry DISTINCT tones (#24 — neutral grey vs the
 * muted info-blue), and the label + this hint spell the distinction out on top
 * (DOIT-1: compréhensible sans être ingénieur).
 */
export const FOLLOW_STATUS_HINT: Record<FollowStatus, string> = {
  disabled: "Suivi en pause — aucune recherche automatique n'est faite.",
  verification_en_cours:
    "Vérification en cours — le catalogue puis les trackers sont interrogés.",
  a_recuperer:
    "Une version conforme au profil est disponible — il reste à la récupérer.",
  en_acquisition:
    "Torrent pris — le pipeline le porte jusqu'à la médiathèque.",
  en_attente:
    "Recherché sur les trackers : rien de conforme au profil pour l'instant.",
  non_verifie:
    "Pas encore vérifié sur les trackers — aucune conclusion à ce jour.",
  a_jour: "Tout ce qui est sorti est en médiathèque.",
};

/** Film wording of {@link FOLLOW_STATUS_HINT}, for the overridden states only. */
export const FOLLOW_STATUS_HINT_MOVIE: Partial<Record<FollowStatus, string>> = {
  a_jour: "Le film est en médiathèque.",
  disabled:
    "Ce film n'est plus cherché — aucune recherche automatique n'est faite.",
};

/**
 * Return the French label of a card status for the right media kind.
 *
 * Zero derivation in JSX (phase-08 rule): the component passes the SERVER
 * status and the media kind, and gets the operator-facing wording back.
 *
 * Args:
 *   status: The server-derived card status.
 *   kind: ``"movie"`` or ``"show"`` (anything else reads as a série).
 *
 * Returns:
 *   The French label — film wording when one is defined for that state.
 */
export function followStatusLabel(status: FollowStatus, kind: string): string {
  if (kind === "movie") {
    return FOLLOW_STATUS_LABEL_MOVIE[status] ?? FOLLOW_STATUS_LABEL[status];
  }
  return FOLLOW_STATUS_LABEL[status];
}

/**
 * Return the disambiguating sentence of a card status for the right media kind.
 *
 * Args:
 *   status: The server-derived card status.
 *   kind: ``"movie"`` or ``"show"``.
 *
 * Returns:
 *   The French hint — film wording when one is defined for that state.
 */
export function followStatusHint(status: FollowStatus, kind: string): string {
  if (kind === "movie") {
    return FOLLOW_STATUS_HINT_MOVIE[status] ?? FOLLOW_STATUS_HINT[status];
  }
  return FOLLOW_STATUS_HINT[status];
}

/**
 * Per-state count noun, singular / plural (card caption wording).
 *
 * ``en_mediatheque`` is absent on purpose: owned episodes are already the
 * numerator of the ``NN/NN`` fraction, and repeating them would inflate the
 * caption with the only number that is never actionable.
 *
 * ``annonce`` is absent too (episode-states D2): a future episode is not an
 * action bucket — it never inflates the card caption and never degrades the
 * card status. It lives only in the completeness matrix.
 */
const COUNT_NOUN: Record<
  Exclude<EpisodeState, "en_mediatheque" | "annonce" | "absorbed">,
  { readonly one: string; readonly many: string }
> = {
  a_recuperer: { one: "à récupérer", many: "à récupérer" },
  en_acquisition: {
    one: "en cours d'acquisition",
    many: "en cours d'acquisition",
  },
  en_attente: {
    one: "en attente de torrent",
    many: "en attente de torrent",
  },
  non_verifie: { one: "non vérifié", many: "non vérifiés" },
};

/** The caption's bucket order — most actionable first, as the card status is. */
const COUNT_ORDER: readonly Exclude<
  EpisodeState,
  "en_mediatheque" | "annonce" | "absorbed"
>[] = ["a_recuperer", "en_acquisition", "en_attente", "non_verifie"];

/**
 * Derive a media sheet href from a followed item's provider ids.
 *
 * Priority: tvdb > tmdb.  imdb has no sheet route on the backend and is
 * skipped — an imdb-only item has no media sheet (§11 exception: unidentified
 * media must lead to resolution, never a dead link).
 *
 * Args:
 *   item: A followed series or film.
 *
 * Returns:
 *   A media sheet href, or ``null`` when no tvdb/tmdb id is known.
 */
export function followMediaRef(item: {
  readonly media_ref: FollowedSeriesItem["media_ref"];
  readonly kind: string;
}): string | null {
  const ref = item.media_ref;
  // tvdb first — primary provider for series.
  if (ref.tvdb_id != null) {
    return mediaSheetHref({
      provider: "tvdb",
      providerId: String(ref.tvdb_id),
      kind: item.kind === "movie" ? "movie" : "tv",
    });
  }
  // tmdb second — universal provider.
  if (ref.tmdb_id != null) {
    return mediaSheetHref({
      provider: "tmdb",
      providerId: String(ref.tmdb_id),
      kind: item.kind === "movie" ? "movie" : "tv",
    });
  }
  return null;
}

/**
 * Render a followed SHOW's library fraction, or ``null`` when it has none.
 *
 * A film is a catalog of exactly ONE unit: a fraction (« 1/1 ») says nothing
 * its status chip does not already say, and « 0/1 » would read as a
 * completeness failure rather than as « pas encore acquis ». So films get no
 * fraction at all — their card readout IS the status chip (+ the waiting
 * reason when they wait).
 *
 * Args:
 *   item: The followed item.
 *
 * Returns:
 *   ``"15/18"``, ``"—"`` when a série has no cached catalog (honest ignorance,
 *   matching its ``non_verifie`` status), or ``null`` for a film.
 */
export function followFraction(item: FollowedSeriesItem): string | null {
  if (item.kind === "movie") return null;
  if (item.aired_count == null) return "—";
  return `${String(item.owned_count ?? 0)}/${String(item.aired_count)}`;
}

/**
 * Render the non-zero five-state episode counts as a French caption.
 *
 * This is what makes the queue and the wait VISIBLE on the compact row
 * (NE-DOIT-PAS-2), and it replaces the raw ``wanted_pending`` chip: that
 * counter knows nothing about ownership or about the aired catalog, and
 * printing « 3 en attente » next to an « À jour » chip is exactly the founding
 * incident's lie. Every number here comes from the SAME server-side derivation
 * the status chip comes from, so the two can never contradict each other.
 *
 * Args:
 *   item: The followed item (its per-state counts).
 *
 * Returns:
 *   E.g. ``"3 à récupérer · 1 non vérifié"``, or ``null`` when every bucket is
 *   empty / unknown (a fully-owned série, or a follow with no catalog).
 */
export function followCountsCaption(item: FollowedSeriesItem): string | null {
  const counts: Record<
    Exclude<EpisodeState, "en_mediatheque" | "annonce" | "absorbed">,
    number | null
  > = {
    a_recuperer: item.a_recuperer_count ?? null,
    en_acquisition: item.en_acquisition_count ?? null,
    en_attente: item.en_attente_count ?? null,
    non_verifie: item.non_verifie_count ?? null,
  };
  const parts = COUNT_ORDER.filter((state) => (counts[state] ?? 0) > 0).map(
    (state) => {
      const n = counts[state] ?? 0;
      const noun = n > 1 ? COUNT_NOUN[state].many : COUNT_NOUN[state].one;
      return `${String(n)} ${noun}`;
    },
  );
  return parts.length > 0 ? parts.join(" · ") : null;
}

/**
 * Report whether « Récupérer maintenant » applies to this follow.
 *
 * Offered exactly where the SERVER says something is takeable right now
 * (``a_recuperer``) — never derived from a queue counter. Elsewhere the action
 * would have nothing to claim and would report success having done nothing.
 *
 * Args:
 *   item: The followed item.
 *
 * Returns:
 *   ``true`` when the grab-only action is meaningful for this follow.
 */
export function canGrabNow(item: FollowedSeriesItem): boolean {
  return item.active && item.status === "a_recuperer";
}

/** Followed kind → French badge label (§5 film vs série). */
export const FOLLOW_KIND_LABEL: Record<string, string> = {
  movie: "Film",
  show: "Série",
  season: "Saison",
};

/** Run outcome → badge tone (acquisition recent runs). */
export const RUN_OUTCOME_TONE: Record<string, BadgeTone> = {
  success: OUTCOME_TONE.success ?? "success",
  error: OUTCOME_TONE.error ?? "danger",
  killed: OUTCOME_TONE.killed ?? "warning",
};

/** Run outcome → French label (acquisition recent runs). */
export const RUN_OUTCOME_LABEL: Record<string, string> = {
  success: OUTCOME_LABEL.success ?? "Succès",
  error: OUTCOME_LABEL.error ?? "Échec",
  killed: OUTCOME_LABEL.killed ?? "Interrompu",
};

/** French labels for the §5 numeric-result keys persisted by the CLIs. */
export const RUN_RESULT_LABEL: Record<string, string> = {
  detected: "détecté(s)",
  enqueued: "mis en file",
  skipped_owned: "déjà en médiathèque",
  skipped_dup: "doublon(s)",
  grabbed: "récupéré(s)",
  retried: "à retenter",
  abandoned: "abandonné(s)",
  skipped: "ignoré(s)",
  // Pipeline-run fallback summary (derived from per-step native counts).
  processed: "traité(s)",
  errors: "erreur(s)",
  // Reconcile counters (detect runs) — surfaced raw in prod on 2026-07-15.
  closed_owned: "clôturé(s) (en médiathèque)",
  resurrected: "réouvert(s)",
  requeued_missing: "remis en recherche",
};

/** French labels for the watcher deferral reasons (transient ingest skips). */
export const DEFERRED_REASON_LABEL: Record<string, string> = {
  ratio_below_threshold: "ratio de partage insuffisant",
  content_missing: "contenu source introuvable",
  insufficient_space: "espace disque insuffisant",
};

/**
 * Render a run's §5 numeric result as a short French sentence.
 *
 * Args:
 *   result: The counts mapping from the run row, or null/undefined.
 *
 * Returns:
 *   E.g. "3 détecté(s), 2 mis en file" — or "rien de nouveau" when every
 *   count is zero, or "" when no result was recorded.
 */
export function formatRunResult(
  result: Record<string, number> | null | undefined,
): string {
  if (!result) return "";
  const parts = Object.entries(result)
    .filter(([, v]) => v > 0)
    .map(([k, v]) => `${String(v)} ${RUN_RESULT_LABEL[k] ?? k}`);
  return parts.length > 0 ? parts.join(", ") : "rien de nouveau";
}

/**
 * Per-episode §5 state → chip tone (completeness matrix + legend).
 *
 * SIX states, SIX distinct DS tones (operator #9 « une couleur par statut ») —
 * no two states share a tone, asserted by a test. ``non_verifie`` moved off the
 * grey it used to share with ``en_attente`` onto the dimmer dashed ``muted``,
 * and ``annonce`` onto the violet ``upcoming``.
 */
export const EPISODE_STATE_TONE: Record<EpisodeState, BadgeTone> = {
  non_verifie: "muted",
  annonce: "upcoming",
  en_attente: "waiting",
  a_recuperer: "warning",
  en_acquisition: "info",
  en_mediatheque: "success",
  // `absorbed` reaches a surface ONLY when the pointer cannot be followed: the
  // shared seam (states.substitute_absorbed_facts) otherwise replaces it with the
  // carrying season's own state. So this entry renders an UNKNOWN — we know an
  // acquisition is carried by a season, not where it stands. « In motion » is the
  // arbitrated reading of that unknown (never « never checked »); the hint below
  // is what keeps it honest by naming the season.
  absorbed: "info",
};

/**
 * Per-episode §5 state → French label (completeness matrix).
 *
 * ``en_mediatheque`` keeps the §5 wording « En médiathèque » on an EPISODE: the
 * vocabulary table's « À jour » is the CARD reading of that state (a card
 * aggregates to ``a_jour``), and an individual episode is never « à jour » — it
 * is on the disks or it is not.
 */
export const EPISODE_STATE_LABEL: Record<EpisodeState, string> = {
  non_verifie: "Non vérifié",
  annonce: "Annoncé",
  en_attente: "En attente de torrent",
  a_recuperer: "À récupérer",
  en_acquisition: "En cours d'acquisition",
  en_mediatheque: "En médiathèque",
  absorbed: "En cours d'acquisition",
};

/**
 * The legend's state order — the lifecycle an episode actually walks, as the
 * operator reads it: unknown → announced → searched-but-nothing → takeable →
 * being taken → owned.
 *
 * ``absorbed`` is deliberately absent: it renders exactly like
 * ``en_acquisition`` (same tone, same label), so listing it would print the
 * same chip twice for what is one operator-facing state.
 */
export const EPISODE_LEGEND_ORDER: readonly EpisodeState[] = [
  "non_verifie",
  "annonce",
  "en_attente",
  "a_recuperer",
  "en_acquisition",
  "en_mediatheque",
];

/**
 * Per-episode state → the sentence that disambiguates it (chip tooltip).
 *
 * Same anti-confusion contract as {@link FOLLOW_STATUS_HINT}: « En attente »
 * (searched, nothing conforming) must never read like « Non vérifié » (no
 * verdict yet).
 */
export const EPISODE_STATE_HINT: Record<EpisodeState, string> = {
  annonce: "Sortie prévue — l'épisode n'est pas encore diffusé.",
  en_mediatheque: "L'épisode est en médiathèque.",
  a_recuperer:
    "Une version conforme au profil est disponible — il reste à la récupérer.",
  en_acquisition:
    "Torrent pris — le pipeline le porte jusqu'à la médiathèque.",
  en_attente:
    "Recherché sur les trackers : rien de conforme au profil pour l'instant.",
  non_verifie:
    "Pas encore vérifié sur les trackers — aucune conclusion à ce jour.",
  // NEVER claim a torrent was taken here: absorption happens when the SEASON
  // row is enqueued (`pending`), before any search has run — an absorbed
  // episode can sit here with nothing taken at all (and stays if the season row
  // is abandoned without an R6 fallback). The hint says what is true: the
  // acquisition of this episode is carried by a season row.
  absorbed:
    "Récupération portée par un pack de saison — suivez la ligne « saison » dans la file.",
};

/**
 * Search outcome → the French reason an item is not acquired yet.
 *
 * The backend exposes the engine's machine verdict (``no_candidates``,
 * ``all_filtered``, …) because it is the very fact the state was derived from.
 * It is a MACHINE value: it is mapped here and never printed raw
 * (NE-DOIT-PAS-4). The three concluding verdicts explain an « En attente »;
 * the four inconclusive ones explain a « Non vérifié » — panne ≠ absence, and
 * an operator staring at « Non vérifié » deserves to know the trackers were
 * unreachable rather than assume nothing was found.
 */
export const SEARCH_OUTCOME_REASON: Record<string, string> = {
  // Concluding verdicts → « En attente ».
  no_candidates: "aucun résultat",
  no_matching_episode: "pas d'épisode exact",
  all_filtered: "rien de conforme au profil",
  // Inconclusive verdicts → « Non vérifié » (the search never concluded).
  trackers_unavailable: "trackers injoignables",
  circuit_open: "recherche suspendue après trop d'échecs",
  search_api_error: "erreur de recherche côté tracker",
  no_seeders: "aucune source active",
};

/** Fallback for a verdict this build does not know — still French, still honest. */
const UNKNOWN_OUTCOME_REASON = "rien de prenable au dernier passage";

/**
 * Return the French reason a unit is waiting, or ``null`` when there is none.
 *
 * Args:
 *   state: The unit's five-state reading (card status or episode state).
 *   outcome: The raw ``last_search_outcome`` served with it.
 *
 * Returns:
 *   The French reason — never the machine token — or ``null`` when the unit is
 *   not waiting, or when it has no verdict at all (never searched: the state's
 *   own hint already says exactly that).
 */
export function searchOutcomeReason(
  state: EpisodeState | FollowStatus,
  outcome: string | null | undefined,
): string | null {
  if (state !== "en_attente" && state !== "non_verifie") return null;
  if (outcome == null || outcome === "") return null;
  return SEARCH_OUTCOME_REASON[outcome] ?? UNKNOWN_OUTCOME_REASON;
}

/** One waiting reason and the episodes of a season that share it. */
export interface WaitingGroup {
  /** The French reason (already mapped — never a machine token). */
  readonly reason: string;
  /** The episode numbers waiting for that reason, in ascending order. */
  readonly episodes: readonly number[];
}


/**
 * Return the French reason a followed FILM is waiting, or ``null``.
 *
 * A film has no episode matrix, so the reason its single unit is not acquired
 * belongs on the card itself — read from the same ``movie_facts`` the server
 * derived the card status from.
 *
 * Args:
 *   item: The followed item (films only; a série always returns ``null``).
 *
 * Returns:
 *   The French reason, or ``null``.
 */
export function followWaitingReason(item: FollowedSeriesItem): string | null {
  if (item.kind !== "movie") return null;
  return searchOutcomeReason(
    item.status,
    item.movie_facts?.last_search_outcome,
  );
}

/** Live download state → Badge tone (A4). */
export const DOWNLOAD_STATE_TONE: Record<
  string,
  "success" | "warning" | "info" | "neutral" | "danger"
> = {
  downloading: "info",
  stalled: "warning",
  seeding: "success",
  paused: "neutral",
  queued: "neutral",
  in_client: "neutral",
  missing: "danger",
  errored: "danger",
};

/** Live download state → French label (A4). */
export const DOWNLOAD_STATE_LABEL: Record<string, string> = {
  downloading: "Téléchargement",
  stalled: "En attente de sources",
  seeding: "Terminé (partage)",
  paused: "En pause",
  queued: "En file",
  in_client: "Dans le client",
  missing: "Introuvable",
  errored: "En erreur",
};

// Relative-time + datetime formatters — re-exported from the single
// `lib/format` owner (ACC-10).
export { relativeTime, formatDatetime } from "@/lib/format";

/**
 * Derive the obligation status from timestamps.
 *
 * The backend does not expose a ``status`` field on ObligationItem — the
 * status is implicit in the ``satisfied_at`` / ``breached_at`` columns.
 */
export function obligationStatus(
  item: ObligationItem,
): "satisfied" | "breached" | "pending" {
  if (item.satisfied_at != null) return "satisfied";
  if (item.breached_at != null) return "breached";
  return "pending";
}



/** Truncate a long string for table display, appending "…" when cut. */
export function truncate(s: string, max: number): string {
  if (s.length <= max) return s;
  return `${s.slice(0, max)}…`;
}
