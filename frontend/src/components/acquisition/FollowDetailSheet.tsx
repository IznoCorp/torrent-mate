/**
 * FollowDetailSheet — per-season / per-episode detail drawer for one followed
 * series or film, opened by tap on a card.
 *
 * It replaces the always-rendered « Détail par épisode » accordion. Layout order
 * IS part of the spec (design-spec §5.3): title → meta → the one offered primary
 * action (if any) → legend → season matrix → secondary actions LAST.
 *
 * The single derivation IS server-side
 * (``states.derive_episode_state``, consumed by both ``truth.py`` for the card
 * aggregates and ``completeness.py`` for this sheet); ``seasonCounts()`` is this
 * component's LOCAL re-aggregation of the same server-derived episode states, and
 * it must stay consistent with ``truth.py``'s rule — announced episodes excluded
 * from ``aired``.
 *
 * A COMPLETE season is collapsed (``<details>`` without ``open``); an INCOMPLETE one
 * is open and carries a « N manquant(s) » chip. The legend sits ABOVE the matrix
 * — under 390 episodes it would otherwise be invisible exactly when needed.
 */

import { useState, type ReactElement } from "react";

import {
  Clock,
  Download,
  FileText,
  Pause,
  Play,
  Route,
  Search,
  Trash2,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

import type {
  CompletenessResponse,
  EpisodeCompleteness,
  SeasonCompleteness,
} from "@/api/acquisition";
import { Badge } from "@/components/ui/badge";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { MediaPoster } from "@/components/ds/MediaPoster";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useCompleteness,
  useGrabNow,
  useGrabSeason,
  useUnfollow,
  useUpdateFollow,
} from "@/hooks/useAcquisition";

import { EpisodeDatePopover } from "./EpisodeDatePopover";
import { EpisodeStateLegende } from "./EpisodeStateLegende";
import { relativeTimeUntil } from "@/lib/format";

import {
  EPISODE_STATE_HINT,
  EPISODE_STATE_LABEL,
  EPISODE_STATE_TONE,
  TONE_CELL_CLASS,
  searchOutcomeReason,
  type FollowStatus,
  type MediaKind,
  actionWords,
  MOVIE_LIFECYCLE_NOTE,
} from "./meta";

// ── §13 — the single derivation the three surfaces read ──────────────────

/**
 * Owned / aired counts for a season.
 *
 * The card fraction, the sheet header and every season header answer the SAME
 * question, so they must read the SAME computation. An announced episode is not
 * aired and therefore can never be missing from the denominator.
 *
 * Args:
 *   episodes: The season's episodes as served.
 *
 * Returns:
 *   ``{ owned, aired }``.
 */
export function seasonCounts(
  episodes: readonly { readonly state: EpisodeCompleteness["state"] }[],
): { readonly owned: number; readonly aired: number } {
  return {
    owned: episodes.filter((e) => e.state === "en_mediatheque").length,
    aired: episodes.filter((e) => e.state !== "annonce").length,
  };
}

// ── Props ─────────────────────────────────────────────────────────────────

/** Props for {@link FollowDetailSheet}. */
export interface FollowDetailSheetProps {
  readonly followedId: number;
  /** The card's lifecycle status — drives the primary action (§5.3). */
  readonly status: FollowStatus;
  /** The card's media kind (``"movie"`` or ``"show"``) — drives action wording. */
  readonly kind: MediaKind;
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  /** Media sheet href, or ``null`` when no provider id is known (§11).
   *  Derived by the panel from ``followMediaRef(item)`` — the sheet does
   *  not own the derivation. */
  readonly mediaHref?: string | null | undefined;
  /** Next scheduled search instant (epoch s) — the meta line says when the
   *  machine looks again; silence about it reads as « never » (§8). */
  readonly nextSearchAt?: number | null | undefined;
  /** Opens the cadence editor (owned by the panel's action source, §13). */
  readonly onEditCadence?: (() => void) | undefined;
  /** Opens the journey detail — provided only when a journey exists (§11). */
  readonly onVoirLeParcours?: (() => void) | undefined;
  /** Poster URL for the header (maquette: 84×126 beside the title). */
  readonly posterUrl?: string | null | undefined;
}

// ── Loading / Error states ────────────────────────────────────────────────

function SheetLoading(): ReactElement {
  return (
    <>
    <SheetTitle className="sr-only">Détail du suivi</SheetTitle>
    <div className="flex flex-col gap-4 p-4">
      <Skeleton className="h-6 w-2/3" />
      <Skeleton className="h-4 w-1/3" />
      <Skeleton className="h-32 w-full" />
    </div>
    </>
  );
}

function SheetError(): ReactElement {
  return (
    <>
    <SheetTitle className="sr-only">Détail du suivi</SheetTitle>
    <p className="p-4 text-sm text-muted-foreground">
      Complétude indisponible pour le moment.
    </p>
    </>
  );
}

// ── Season row ────────────────────────────────────────────────────────────

function SeasonRow({
  season,
  followedId,
}: {
  readonly season: SeasonCompleteness;
  readonly followedId: number;
}): ReactElement {
  const grabSeasonMut = useGrabSeason();
  const { owned, aired } = seasonCounts(season.episodes);
  const complete = owned === aired;
  const missing = aired - owned;
  const seasonName = `Saison ${String(season.season).padStart(2, "0")}`;

  return (
    <details
      data-testid={`season-${String(season.season)}`}
      className="group border-t border-border py-2 first:border-t-0"
      open={!complete}
    >
      <summary className="flex cursor-pointer items-center gap-2 py-1 text-[11px] font-bold uppercase tracking-[0.06em] text-muted-foreground [&::-webkit-details-marker]:hidden">
        <span data-testid="season-name">{seasonName}</span>
        <span className="ml-auto flex items-center gap-2 normal-case tracking-normal">
          <span data-testid="season-fraction">
            <span
              data-testid={`season-${String(season.season)}-fraction`}
              className="font-mono text-xs font-semibold text-foreground tabular-nums"
            >
              {String(owned)}/{String(aired)}
            </span>
          </span>
          {!complete && (
            <button
              data-testid={`grab-season-${String(season.season)}`}
              type="button"
              disabled={grabSeasonMut.isPending}
              className="rounded border border-border px-2 py-0.5 text-xs hover:bg-accent disabled:opacity-50"
              // A button inside <summary> would also toggle the details.
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                grabSeasonMut.mutate({ id: followedId, season: season.season });
              }}
            >
              Récupérer
            </button>
          )}
          {!complete && (
            <Badge tone="warning">
              {String(missing)} manquant{missing > 1 ? "s" : ""}
            </Badge>
          )}
        </span>
      </summary>
      <div className="mt-2 flex flex-wrap gap-1">
        {season.episodes.map((ep) => (
          <EpisodeChip key={ep.episode} episode={ep} />
        ))}
      </div>
    </details>
  );
}

// ── Episode chip ──────────────────────────────────────────────────────────

function EpisodeChip({
  episode,
}: {
  readonly episode: EpisodeCompleteness;
}): ReactElement {
  const label = EPISODE_STATE_LABEL[episode.state];
  const hint = EPISODE_STATE_HINT[episode.state];
  // §14.1 — a waiting episode names WHY the last search rested there. The
  // reason survived its old accordion home through this tooltip.
  const reason = searchOutcomeReason(episode.state, episode.last_search_outcome);
  // The air date, when known: what tells « announced for Friday » apart from
  // « announced, date unknown » without opening anything.
  const aired = episode.air_date != null ? ` · ${episode.air_date}` : "";
  const title = `E${String(episode.episode)} — ${label}${hint ? ` · ${hint}` : ""}${reason ? ` · ${reason}` : ""}${aired}`;

  return (
    // Tap → the air date, said in French. The hover title stays as the
    // desktop fallback; on touch a tooltip does not exist, and losing the
    // date with the old accordion was a regression, not a simplification.
    <EpisodeDatePopover
      state={episode.state}
      airDate={episode.air_date ?? null}
      triggerLabel={`E${String(episode.episode)} — ${label}`}
      hoverTitle={title}
    >
      <span
        className={`grid h-[27px] w-[31px] place-items-center rounded-[5px] font-mono text-[11px] font-semibold ${TONE_CELL_CLASS[EPISODE_STATE_TONE[episode.state]] ?? "bg-muted text-muted-foreground"}`}
      >
        {String(episode.episode).padStart(2, "0")}
        <span className="sr-only"> — {label}</span>
      </span>
    </EpisodeDatePopover>
  );
}

// ── Aggregate meta ────────────────────────────────────────────────────────

/**
 * Compute the sheet-level fraction: sum of `seasonCounts` across all seasons.
 *
 * Returns ``null`` for a film (no episode matrix) or an empty catalogue.
 */
function aggregateFraction(
  data: CompletenessResponse,
): { owned: number; aired: number } | null {
  if (data.kind === "movie") return null;
  const total = data.seasons.reduce(
    (acc, s) => {
      const c = seasonCounts(s.episodes);
      return { owned: acc.owned + c.owned, aired: acc.aired + c.aired };
    },
    { owned: 0, aired: 0 },
  );
  if (total.aired === 0 && data.source === "unknown") return null;
  return total;
}

// ── Main component ────────────────────────────────────────────────────────

/**
 * FollowDetailSheet — a side/bottom drawer showing one followed item's state.
 *
 * The sheet is opened by tapping a card. It lays out
 * state-first: the aggregate then the season matrix, then the actions. A
 * COMPLETE season is collapsed; an INCOMPLETE one is open with a missing chip.
 *
 * Args:
 *   followedId: The ``followed_series`` row id.
 *   status: The card's lifecycle status — drives « Récupérer maintenant »
 *           as the primary action when ``"a_recuperer"``.
 *   kind: The card's media kind — drives action wording (film vs série).
 *   open: Whether the sheet is visible.
 *   onOpenChange: Called when the sheet opens or closes (Radix controlled).
 *
 * Returns:
 *   The sheet element.
 */
export function FollowDetailSheet({
  followedId,
  status,
  kind,
  open,
  onOpenChange,
  mediaHref,
  nextSearchAt,
  onEditCadence,
  onVoirLeParcours,
  posterUrl,
}: FollowDetailSheetProps): ReactElement {
  const { data, isLoading, isError } = useCompleteness(followedId, open);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="bottom"
        // Maquette .sheet: a grab handle and the outside tap close it — no
        // cross. 16px top radius, 86% max height.
        className="mq flex max-h-[86%] flex-col overflow-y-auto rounded-t-2xl border-t border-border"
        showCloseButton={false}
      >
        <div className="sheetgrab" aria-hidden="true" />
        {isLoading ? (
          <SheetLoading />
        ) : isError ? (
          <SheetError />
        ) : data ? (
          <FollowDetailSheetContent
            data={data}
            status={status}
            kind={kind}
            mediaHref={mediaHref}
            followedId={followedId}
            onOpenChange={onOpenChange}
            nextSearchAt={nextSearchAt}
            onEditCadence={onEditCadence}
            onVoirLeParcours={onVoirLeParcours}
            posterUrl={posterUrl ?? null}
          />
        ) : null}
      </SheetContent>
    </Sheet>
  );
}

// ── Content (extracted so the happy path is un-indented) ──────────────────

function FollowDetailSheetContent({
  data,
  status,
  kind,
  mediaHref,
  followedId,
  onOpenChange,
  nextSearchAt,
  onEditCadence,
  onVoirLeParcours,
  posterUrl,
}: {
  readonly data: CompletenessResponse;
  readonly status: FollowStatus;
  readonly kind: MediaKind;
  readonly mediaHref?: string | null | undefined;
  readonly followedId: number;
  readonly onOpenChange: (open: boolean) => void;
  readonly nextSearchAt?: number | null | undefined;
  readonly onEditCadence?: (() => void) | undefined;
  readonly onVoirLeParcours?: (() => void) | undefined;
  readonly posterUrl?: string | null | undefined;
}): ReactElement {
  const navigate = useNavigate();
  const words = actionWords(kind);
  const updateFollow = useUpdateFollow();
  const unfollow = useUnfollow();
  const grabNow = useGrabNow();
  // Removal is confirmed (§9) — the wording differs by nature: a série is
  // deactivated and reactivable, a film leaves the list and returns via a
  // search. Swiping past a destructive action must never BE the action.
  const [confirmRemove, setConfirmRemove] = useState(false);
  const aggregate = aggregateFraction(data);

  // §11: a follow that can't be resolved to a provider id has no catalogue.
  const unresolved = data.kind === "show" && data.seasons.length === 0 && data.source === "unknown";

  // §5.3: « Récupérer maintenant » is the primary action ONLY when something is
  // takeable — else there is no primary action at all (never a disabled one).
  const canGrab = status === "a_recuperer";

  // Most-recent season first (§5.3). Sort explicitly; the API makes no ordering
  // promise and a fixture that happens to be descending proves nothing.
  const seasons = [...data.seasons].sort((a, b) => b.season - a.season);

  return (
    <>
      {/* ── Header ── */}
      <SheetHeader>
        <div className="flex items-start gap-3">
          <MediaPoster title={data.title} src={posterUrl ?? null} className="w-[84px]" />
          <div className="min-w-0 flex-1">
        <SheetTitle className="sheettitle [text-wrap:balance]">{data.title}</SheetTitle>
        {/* The one fraction — same derivation as card + season headers (§13) —
            then WHEN the machine looks again, or why it will not (paused). */}
        {(aggregate != null || data.kind === "movie") && (
          <p data-testid="sheet-meta" className="sheetmeta">
            {/* An announced-only catalogue has aired 0: « 0/0 » would read as
                an empty série. §14.1 separates « not aired yet » from
                « nothing there ». */}
            {data.kind === "movie"
              ? status === "a_jour"
                ? "en médiathèque"
                : "pas encore acquis"
              : aggregate == null || aggregate.aired === 0
                ? "Aucun épisode diffusé pour l'instant"
                : `${String(aggregate.owned)}/${String(aggregate.aired)} en médiathèque`}
            {status === "disabled"
              ? kind === "movie"
                ? " · recherche arrêtée"
                : " · suivi en pause"
              : nextSearchAt != null
                ? ` · prochaine recherche ${relativeTimeUntil(nextSearchAt)}`
                : ""}
          </p>
        )}
        {/* §5/§9 — the lifecycle rule, NOT the removal-confirmation body this
            once shipped: telling the operator their film « ne sera plus
            cherché » on every open read as a threat, and said nothing about
            the automatic exit that §5 makes normal. An acquired film is past
            the rule, so it gets no sentence. */}
        {data.kind === "movie" && status !== "a_jour" && (
          <p className="rulenote">{MOVIE_LIFECYCLE_NOTE}</p>
        )}
        {unresolved && (
          <p className="text-sm text-muted-foreground">
            Ce suivi n&apos;a pas pu être résolu à un identifiant provider (TVDB/TMDB).
            La matrice d&apos;épisodes et la fiche ne sont pas disponibles.
          </p>
        )}
          </div>
        </div>
      </SheetHeader>

      {/* ── Primary action (§5.3) ── */}
      {canGrab && (
        <div data-testid="primary-action" className="sheetacts px-4">
          {/* Wired to the real search chain: the ONE action this sheet exists
              to offer was shipped as a button with no onClick — a dead control
              on the primary path (§11). The 202 means « launched »; the toast
              says so and the card moves on its own refresh. */}
          <button
            type="button"
            disabled={grabNow.isPending}
            className="sact primary"
            onClick={() => {
              grabNow.mutate(followedId);
              onOpenChange(false);
            }}
          >
            <Download aria-hidden="true" />
            Récupérer maintenant
          </button>
        </div>
      )}

      {/* ── Legend ABOVE the matrix (§5.3) ── */}
      {seasons.length > 0 && (
        <div data-testid="episode-legend" className="px-4">
          <EpisodeStateLegende />
        </div>
      )}

      {/* ── Season matrix, most-recent first ── */}
      {seasons.length > 0 && (
        <div className="flex flex-col px-4">
          {seasons.map((s) => (
            <SeasonRow key={s.season} season={s} followedId={followedId} />
          ))}
        </div>
      )}

      {/* ── Secondary actions LAST ──
          NOT gated on `unresolved`: pause and removal need no provider id, and
          an unresolved follow whose only exits are invisible is a trap — the
          operator could neither stop nor drop the one follow most likely to
          need it. Only « Voir la fiche » depends on an id, and it gates itself
          through mediaHref. */}
      <div data-testid="secondary-actions" className="sheetacts secondary mt-auto px-4 pb-4">
        {mediaHref != null ? (
          <button
            data-testid="voir-la-fiche"
            type="button"
            className="sact hover:bg-accent"
            onClick={() => {
              // replace: the sheet holds a useBackCloses marker entry — the
              // fiche takes its place, so one Back lands under the sheet.
              void navigate(mediaHref, { replace: true });
            }}
          >
            <FileText aria-hidden="true" />
            Voir la fiche
          </button>
        ) : unresolved ? null : (
          /* §8/§11 — the absent link is EXPLAINED, never silent: a fiche
             button that simply is not there reads as a bug, not a fact. The
             header's unresolved paragraph already says it for a catalogue-less
             follow — no second sentence there (§12). */
          <p className="nofiche">
            Pas de fiche : l&apos;identifiant TVDB de ce média n&apos;a pas pu
            être résolu.
          </p>
        )}
        {/* Always offered — the chain searches, and only takes what is
            takeable; on a resting follow it IS the manual re-check. */}
        <button
          data-testid="rechercher-maintenant"
          type="button"
          disabled={grabNow.isPending}
          className="sact hover:bg-accent"
          onClick={() => {
            grabNow.mutate(followedId);
            onOpenChange(false);
          }}
        >
          <Search aria-hidden="true" />
          Rechercher maintenant
        </button>
        {onVoirLeParcours != null && (
          <button
            data-testid="voir-le-parcours"
            type="button"
            className="sact hover:bg-accent"
            onClick={() => {
              onOpenChange(false);
              onVoirLeParcours();
            }}
          >
            <Route aria-hidden="true" />
            Voir le parcours
          </button>
        )}
        {onEditCadence != null && (
          <button
            data-testid="cadence-de-recherche"
            type="button"
            className="sact hover:bg-accent"
            onClick={() => {
              onEditCadence();
            }}
          >
            <Clock aria-hidden="true" />
            Cadence de recherche
          </button>
        )}
        {/* §9 suspend/resume is a PAIR: a paused follow offers « Réactiver »,
            never a second pause. `disabled` is the server's derivation of
            active=0 — one derivation, read here rather than re-derived. */}
        {status === "disabled" ? (
          <button
            data-testid="reactiver"
            type="button"
            disabled={updateFollow.isPending}
            className="sact hover:bg-accent"
            onClick={() => {
              updateFollow.mutate({ id: followedId, body: { active: true } });
              onOpenChange(false);
            }}
          >
            <Play aria-hidden="true" />
            {words.resume}
          </button>
        ) : (
          <button
            data-testid="mettre-en-pause"
            type="button"
            disabled={updateFollow.isPending}
            className="sact hover:bg-accent"
            onClick={() => {
              updateFollow.mutate({ id: followedId, body: { active: false } });
              onOpenChange(false);
            }}
          >
            <Pause aria-hidden="true" />
            {words.pause}
          </button>
        )}
        <button
          data-testid="retirer-le-suivi"
          type="button"
          disabled={unfollow.isPending}
          className="sact danger hover:bg-accent"
          onClick={() => {
            setConfirmRemove(true);
          }}
        >
          <Trash2 aria-hidden="true" />
          {words.remove}
        </button>
      </div>

      {/* ── Removal confirmation (§9) ── */}
      <Dialog open={confirmRemove} onOpenChange={setConfirmRemove}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{words.removeConfirmTitle}</DialogTitle>
            <DialogDescription>{words.removeConfirmBody}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <button
              type="button"
              className="rounded-md border border-border px-3 py-2 text-sm hover:bg-accent"
              onClick={() => {
                setConfirmRemove(false);
              }}
            >
              Annuler
            </button>
            <button
              data-testid="confirmer-le-retrait"
              type="button"
              disabled={unfollow.isPending}
              className="rounded-md bg-danger px-3 py-2 text-sm font-medium text-danger-foreground hover:bg-danger/90 disabled:opacity-50"
              onClick={() => {
                unfollow.mutate(followedId);
                setConfirmRemove(false);
                onOpenChange(false);
              }}
            >
              {words.remove}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
