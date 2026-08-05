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
  type EpisodeCompleteness,
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

/** Tab ids for the panels. */
export type TabId =
  | "apercu"
  | "followed"
  | "file"
  | "obligations"
  | "watcher"
  | "parcours"
  | "reglages";

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

/** Tabs displayed in the page header. */
export const TABS: readonly { id: TabId; label: string }[] = [
  { id: "apercu", label: "Vue d'ensemble" },
  { id: "followed", label: "Suivis" },
  { id: "file", label: "File d'acquisition" },
  { id: "obligations", label: "Obligations" },
  { id: "watcher", label: "Watcher" },
  { id: "parcours", label: "Parcours" },
  { id: "reglages", label: "Réglages" },
];

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

/** Wanted status filter options. */
export const WANTED_STATUS_OPTIONS = [
  { value: "all", label: "Tous" },
  { value: "pending", label: "En attente" },
  { value: "searching", label: "En recherche" },
  { value: "grabbed", label: "Récupéré" },
  { value: "done", label: "Terminé" },
  { value: "abandoned", label: "Abandonné" },
  // `absorbed` is NOT offered as a filter: it is not a state the operator reasons
  // about, and since ticket 411 the queue no longer SHOWS it either — the backend
  // resolves an absorbed row onto its season's status (§13: follow the pointer),
  // so those rows are reached through « Terminé », « En attente », etc., like any
  // other. A row still reading `absorbed` means its pointer could not be followed
  // — an anomaly the coherence check reports, not a filter the operator needs.
  { value: "fallback_episodes", label: "Reporté en épisodes" },
];

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
};

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
 * Group a season's waiting episodes by their French reason.
 *
 * A tooltip alone would be invisible on a phone (no hover), so the accordion
 * prints these groups under the chips. Grouping keeps the line short when a
 * whole season shares one verdict, which is the common case.
 *
 * Args:
 *   episodes: The season's episodes, as served.
 *
 * Returns:
 *   One group per distinct reason, in first-appearance order. Empty when
 *   nothing is waiting or no verdict was recorded.
 */
export function waitingGroups(
  episodes: readonly EpisodeCompleteness[],
): WaitingGroup[] {
  const byReason = new Map<string, number[]>();
  for (const ep of episodes) {
    const reason = searchOutcomeReason(ep.state, ep.last_search_outcome);
    if (reason == null) continue;
    const bucket = byReason.get(reason);
    if (bucket) bucket.push(ep.episode);
    else byReason.set(reason, [ep.episode]);
  }
  return [...byReason.entries()].map(([reason, eps]) => ({
    reason,
    episodes: [...eps].sort((a, b) => a - b),
  }));
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

/** Extract ``interval_minutes`` from a cadence JSON blob, returning a safe default. */
export function cadenceInterval(
  cadence: Record<string, unknown> | null | undefined,
): number {
  if (cadence == null) return 0;
  const v = cadence.interval_minutes;
  return typeof v === "number" ? v : 0;
}

/** Relative human label until an epoch-seconds instant ("imminente" when due). */
export function untilLabel(epochSec: number, nowMs: number): string {
  const deltaMs = epochSec * 1000 - nowMs;
  if (deltaMs <= 60_000) return "imminente";
  const mins = Math.round(deltaMs / 60_000);
  if (mins < 60) return `dans ~${String(mins)} min`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `dans ~${String(hours)} h`;
  return `dans ~${String(Math.round(hours / 24))} j`;
}

/** Truncate a long string for table display, appending "…" when cut. */
export function truncate(s: string, max: number): string {
  if (s.length <= max) return s;
  return `${s.slice(0, max)}…`;
}
