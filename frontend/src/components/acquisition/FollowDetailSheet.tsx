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

import { type ReactElement } from "react";
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
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useCompleteness,
  useUnfollow,
  useUpdateFollow,
} from "@/hooks/useAcquisition";

import { EpisodeStateLegende } from "./EpisodeStateLegende";
import {
  EPISODE_STATE_HINT,
  EPISODE_STATE_LABEL,
  EPISODE_STATE_TONE,
  type FollowStatus,
  type MediaKind,
  actionWords,
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
}

// ── Loading / Error states ────────────────────────────────────────────────

function SheetLoading(): ReactElement {
  return (
    <div className="flex flex-col gap-4 p-4">
      <Skeleton className="h-6 w-2/3" />
      <Skeleton className="h-4 w-1/3" />
      <Skeleton className="h-32 w-full" />
    </div>
  );
}

function SheetError(): ReactElement {
  return (
    <p className="p-4 text-sm text-muted-foreground">
      Complétude indisponible pour le moment.
    </p>
  );
}

// ── Season row ────────────────────────────────────────────────────────────

function SeasonRow({ season }: { readonly season: SeasonCompleteness }): ReactElement {
  const { owned, aired } = seasonCounts(season.episodes);
  const complete = owned === aired;
  const missing = aired - owned;
  const seasonName = `Saison ${String(season.season)}`;

  return (
    <details
      data-testid={`season-${String(season.season)}`}
      className="group border-t border-border py-2 first:border-t-0"
      open={!complete}
    >
      <summary className="flex cursor-pointer items-center justify-between text-sm font-medium marker:text-xs">
        <span data-testid="season-name">{seasonName}</span>
        <span className="flex items-center gap-2">
          <span data-testid="season-fraction">
            <span
              data-testid={`season-${String(season.season)}-fraction`}
              className="text-xs text-muted-foreground"
            >
              {String(owned)}/{String(aired)}
            </span>
          </span>
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
  const title = `E${String(episode.episode)} — ${label}${hint ? ` · ${hint}` : ""}`;

  return (
    <span title={title} className="inline-flex">
      <Badge tone={EPISODE_STATE_TONE[episode.state]}>
        E{episode.episode}
        <span className="sr-only"> — {label}</span>
      </Badge>
    </span>
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
}: FollowDetailSheetProps): ReactElement {
  const { data, isLoading, isError } = useCompleteness(followedId, open);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="bottom"
        className="flex max-h-[85vh] flex-col overflow-y-auto"
      >
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
}: {
  readonly data: CompletenessResponse;
  readonly status: FollowStatus;
  readonly kind: MediaKind;
  readonly mediaHref?: string | null | undefined;
  readonly followedId: number;
  readonly onOpenChange: (open: boolean) => void;
}): ReactElement {
  const navigate = useNavigate();
  const words = actionWords(kind);
  const updateFollow = useUpdateFollow();
  const unfollow = useUnfollow();
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
        <h2 className="text-lg font-semibold">{data.title}</h2>
        {/* The one fraction — same derivation as card + season headers (§13). */}
        {aggregate != null && (
          <p data-testid="sheet-meta" className="text-sm text-muted-foreground">
            {String(aggregate.owned)}/{String(aggregate.aired)} en médiathèque
          </p>
        )}
        {data.kind === "movie" && (
          <p className="text-sm text-muted-foreground">{words.removeConfirmBody}</p>
        )}
        {unresolved && (
          <p className="text-sm text-muted-foreground">
            Ce suivi n&apos;a pas pu être résolu à un identifiant provider (TVDB/TMDB).
            Les actions de fiche détaillée ne sont pas disponibles.
          </p>
        )}
      </SheetHeader>

      {/* ── Primary action (§5.3) ── */}
      {canGrab && (
        <div data-testid="primary-action" className="px-4">
          <button
            type="button"
            className="w-full rounded-md bg-primary px-3 py-2 text-center text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
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
            <SeasonRow key={s.season} season={s} />
          ))}
        </div>
      )}

      {/* ── Secondary actions LAST ── */}
      {!unresolved && (
        <div data-testid="secondary-actions" className="mt-auto flex flex-col gap-2 p-4">
          {/* The remaining context-dependent actions (pause, resume, remove)
              are added by the surrounding panel. The two rendered here are
              always present. */}
          {mediaHref != null && (
            <button
              data-testid="voir-la-fiche"
              type="button"
              className="w-full rounded-md border border-border px-3 py-2 text-left text-sm hover:bg-accent"
              onClick={() => {
                void navigate(mediaHref);
              }}
            >
              Voir la fiche
            </button>
          )}
          {/* Both were rendered with no handler: controls that look alive and
              do nothing, which §11 forbids as firmly as a dead link. They act
              now; a failure toasts in French from the hook rather than snapping
              the row back in silence. */}
          <button
            data-testid="mettre-en-pause"
            type="button"
            disabled={updateFollow.isPending}
            className="w-full rounded-md border border-border px-3 py-2 text-left text-sm hover:bg-accent disabled:opacity-50"
            onClick={() => {
              updateFollow.mutate({ id: followedId, body: { active: false } });
              onOpenChange(false);
            }}
          >
            {words.pause}
          </button>
          <button
            data-testid="retirer-le-suivi"
            type="button"
            disabled={unfollow.isPending}
            className="w-full rounded-md border border-border px-3 py-2 text-left text-sm text-danger hover:bg-accent disabled:opacity-50"
            onClick={() => {
              unfollow.mutate(followedId);
              onOpenChange(false);
            }}
          >
            {words.remove}
          </button>
        </div>
      )}
    </>
  );
}
