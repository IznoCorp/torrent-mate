import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactElement } from "react";
import { toast } from "sonner";
import { MoreHorizontal } from "lucide-react";

import { getPipelineHistory } from "@/api/pipeline";
import { enqueueStagingDecision, type StagingMediaItem } from "@/api/staging";
import { decisionsKeys } from "@/api/decisions";
import { pipelineStagesKeys } from "@/hooks/usePipelineStages";
import { stagingMediaKeys } from "@/hooks/useStagingMedia";
import { useContinueMedia } from "@/hooks/useContinueMedia";
import { MediaPoster } from "@/components/ds/MediaPoster";
import { StatusBadge } from "@/components/ds/StatusBadge";
import { IgnoreDiscardButton } from "@/components/staging/IgnoreDiscardButton";
import { MediaTimeline } from "@/components/staging/MediaTimeline";
import {
  dispatchLabel,
  formatSize,
  kindLabel,
  matchBadge,
  posterKind,
} from "@/components/staging/meta";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

/** Props for {@link StagingMediaDetail}. */
export interface StagingMediaDetailProps {
  /** The staged media to detail. */
  readonly item: StagingMediaItem;
  /**
   * Invoked to open the resolution deck on a decision (C18): the ambiguous
   * item's own ``decision_id``, or the id returned by enqueuing a
   * non-identified item.
   */
  readonly onResolve?: (decisionId?: number) => void;
}

/** One labelled provider-id chip (tvdb / tmdb / imdb). */
function IdChip({ family, id }: { family: string; id: string }): ReactElement {
  return (
    <span className="inline-flex items-center gap-1 rounded border border-border px-1.5 py-0.5 text-xs">
      <span className="uppercase text-muted-foreground">{family}</span>
      <span className="font-mono tabular-nums">{id}</span>
    </span>
  );
}

/** One labelled meta cell (label over value). */
function MetaCell({
  label,
  value,
}: {
  label: string;
  value: string;
}): ReactElement {
  return (
    <div className="flex flex-col">
      <span className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      <span className="text-sm">{value}</span>
    </div>
  );
}

/**
 * Poll for a promised ``run_uid`` after a non-deferred continue (A2).
 *
 * Checks ``GET /api/pipeline/history?limit=5`` every 2 s for up to ~10 s.  If
 * the run does not appear within that window it surfaces a warning toast so the
 * operator knows the run may not have started.
 *
 * Args:
 *   runUid: The ``run_uid`` promised by the continue response.
 */
async function pollForRunUid(runUid: string): Promise<void> {
  const maxAttempts = 5;
  const intervalMs = 2000;

  for (let i = 0; i < maxAttempts; i++) {
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
    try {
      const history = await getPipelineHistory({
        limit: 5,
        kind: "pipeline",
        sort: "-started_at",
      });
      const found = history.runs.some((r) => r.run_uid === runUid);
      if (found) return;
    } catch {
      // History endpoint unreachable — keep trying until the window closes.
    }
  }

  // Final check after the last sleep.
  try {
    const history = await getPipelineHistory({
      limit: 5,
      kind: "pipeline",
      sort: "-started_at",
    });
    const found = history.runs.some((r) => r.run_uid === runUid);
    if (!found) {
      toast.warning("Le run promis n'a pas démarré — consultez les journaux.");
    }
  } catch {
    toast.warning("Le run promis n'a pas démarré — consultez les journaux.");
  }
}

/**
 * Full detail sheet for one staged media item.
 *
 * Poster + title/year, matching verdict, provider ids, overview, season
 * breakdown, on-disk facts, the optional dispatch-target preview, and the
 * per-media pipeline {@link MediaTimeline}. When the media is awaiting a
 * matching decision it offers a jump to the resolution deck.
 *
 * Args:
 *   item: The staged media read-model item.
 *   onResolve: Optional handler to open the resolution deck for an ambiguous item.
 *
 * Returns:
 *   The detail element.
 */
export function StagingMediaDetail({
  item,
  onResolve,
}: StagingMediaDetailProps): ReactElement {
  const badge = matchBadge(item.match);
  const kind = posterKind(item.media_kind);
  const dispatch = item.dispatch_target;
  const queryClient = useQueryClient();
  const continueMut = useContinueMedia();

  // A non-identified (absent) movie/tvshow has no pending decision and therefore
  // no resolve path — enqueue it as a decision so it appears in the deck, then
  // jump there (the deck's manual search resolves it via the #3-fixed scrape).
  // An item the sort dumped into 098-AUTRES ('other') is resolvable too, but the
  // operator must first say what type it really is (T1.2 / §3 safety net).
  const needsKind = item.media_kind === "other";
  const [chosenKind, setChosenKind] = useState<"movie" | "tvshow" | null>(null);
  const canManualResolve =
    item.match === "absent" &&
    (item.media_kind === "movie" || item.media_kind === "tvshow" || needsKind);
  const enqueueMut = useMutation({
    mutationFn: (kind: "movie" | "tvshow" | undefined) =>
      enqueueStagingDecision(item.id, kind),
    onSuccess: (data) => {
      // §3 — the deck now opens WITH proposals when the provider search seeded them
      // at enqueue. Be honest when it could not (fail-soft) so the operator knows to
      // adjust the title/year and re-search, rather than face a silent empty grid.
      const n = data.candidates_count;
      if (data.candidates_seeded && n > 0) {
        toast.success(
          `Ajouté à la file — ${String(n)} proposition${n > 1 ? "s" : ""} trouvée${n > 1 ? "s" : ""}, choisissez dans le deck`,
        );
      } else {
        toast.warning(
          "Ajouté à la file — aucune proposition automatique. Ajustez le titre / l'année et relancez la recherche dans le deck.",
        );
      }
      // Invalidate every surface the new decision touches: the deck/queue, the
      // staging grid chip (absent → ambiguous), and the per-media pipeline stages
      // (the matching frontier is now a pending decision). Without the staging +
      // stages invalidation the grid keeps showing the item as 'absent' until an
      // unrelated refetch (§3 — the queue/matching state must reflect reality now).
      void queryClient.invalidateQueries({ queryKey: decisionsKeys.all });
      void queryClient.invalidateQueries({ queryKey: stagingMediaKeys.all });
      void queryClient.invalidateQueries({
        queryKey: pipelineStagesKeys.stages,
      });
      // C18: same grammar as an ambiguous card — jump the deck to the freshly
      // enqueued decision.
      onResolve?.(data.decision_id ?? undefined);
    },
    onError: (err: unknown) => {
      toast.error(
        err instanceof Error ? err.message : "Échec de la mise en file",
      );
    },
  });

  return (
    <div className="flex flex-col gap-4">
      {/* Hero: poster + identity. */}
      <div className="flex gap-4">
        <div className="w-28 shrink-0">
          <MediaPoster
            title={item.title}
            src={item.poster_url ?? null}
            {...(kind !== undefined ? { kind } : {})}
          />
        </div>
        <div className="flex min-w-0 flex-col gap-2">
          <div className="flex items-baseline gap-2">
            <h3 className="text-lg font-semibold leading-tight">
              {item.title}
            </h3>
            {item.year != null && (
              <span className="shrink-0 font-mono text-sm tabular-nums text-muted-foreground">
                {item.year}
              </span>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge tone={badge.tone} label={badge.label} />
            <span className="text-xs text-muted-foreground">
              {kindLabel(item.media_kind)}
            </span>
            {/* A1: durable deferral trace — « Reprise demandée » chip. */}
            {item.continuation_requested_at != null && (
              <span className="inline-flex items-center rounded border border-border px-1.5 py-0.5 text-2xs font-medium text-muted-foreground">
                Reprise demandée
              </span>
            )}
          </div>
          {Object.keys(item.provider_ids).length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(item.provider_ids).map(([family, id]) => (
                <IdChip key={family} family={family} id={id} />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Blocked-before-dispatch callout: the real verify gate refuses this item
          (e.g. unrenamed episodes). Shown even for a "matched" media so the
          operator is never misled by an "Identifié" badge on a stuck item
          (product-intent.md §méthode rule 6). */}
      {item.blocked_reason != null && item.blocked_reason !== "" && (
        <div
          role="alert"
          className="rounded-md border border-danger bg-danger/10 p-3 text-sm text-danger"
        >
          {item.blocked_reason}
        </div>
      )}

      {item.overview != null && item.overview !== "" && (
        <p className="text-sm text-muted-foreground">{item.overview}</p>
      )}

      {/* On-disk facts. */}
      <div className="grid grid-cols-3 gap-3">
        <MetaCell label="Catégorie" value={item.category} />
        <MetaCell label="Taille" value={formatSize(item.size_bytes)} />
        <MetaCell
          label="Vidéos"
          value={item.video_count > 0 ? String(item.video_count) : "—"}
        />
      </div>

      {/* Seasons (TV shows only). */}
      {item.seasons != null && item.seasons.length > 0 && (
        <div className="flex flex-col gap-1">
          <span className="text-xs uppercase tracking-wide text-muted-foreground">
            Saisons
          </span>
          <ul className="flex flex-col gap-0.5 text-sm">
            {item.seasons.map((s) => (
              <li key={s.season} className="flex justify-between gap-2">
                <span>{s.label}</span>
                <span className="text-muted-foreground">
                  {s.episode_count} épisode{s.episode_count > 1 ? "s" : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Dispatch-target preview (only present when requested). */}
      {dispatch != null && (
        <div className="rounded-md border border-border p-3 text-sm">
          <div className="flex items-center justify-between gap-2">
            <span className="font-medium">Dispatch prévu</span>
            <span className="text-muted-foreground">
              {dispatchLabel(dispatch.mode)}
              {dispatch.disk != null ? ` → ${dispatch.disk}` : ""}
            </span>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {dispatch.reason}
          </p>
        </div>
      )}

      {/* Per-media pipeline timeline. */}
      <div className="flex flex-col gap-2">
        <span className="text-xs uppercase tracking-wide text-muted-foreground">
          Parcours pipeline
        </span>
        <MediaTimeline stages={item.stages} />
      </div>

      {/* Resolution jump for an ambiguous match — opens the deck on THIS
          decision (C18). */}
      {item.match === "ambiguous" && onResolve !== undefined && (
        <Button
          type="button"
          onClick={() => {
            onResolve(item.decision_id ?? undefined);
          }}
        >
          Résoudre le matching
        </Button>
      )}

      {/* §5.2 continuation for matched-but-blocked items (verify-gate refusal,
          etc.). The endpoint returns a truthful French detail string — use it
          verbatim for both the toast and the deferred inline feedback (guarantor
          override: server detail is the single source of truth). */}
      {item.match === "matched" &&
        item.blocked_reason != null &&
        item.blocked_reason !== "" && (
          <div className="flex flex-col gap-2">
            <Button
              type="button"
              disabled={continueMut.isPending}
              onClick={() => {
                continueMut.mutate(item.id, {
                  onSuccess: (data) => {
                    toast.success(data.detail);
                    // A2: verify the promised run materialised within ~10 s.
                    if (!data.deferred && data.run_uid != null) {
                      void pollForRunUid(data.run_uid);
                    }
                  },
                  onError: (err: unknown) => {
                    toast.error(
                      err instanceof Error
                        ? err.message
                        : "Échec de la relance",
                    );
                  },
                });
              }}
            >
              {continueMut.isPending
                ? "Envoi…"
                : "Relancer et terminer le pipeline"}
            </Button>
            {continueMut.isSuccess && continueMut.data.deferred && (
              <p className="text-xs text-muted-foreground">
                {continueMut.data.detail}
              </p>
            )}
          </div>
        )}

      {/* Secondary re-scrape action for matched items that are NOT blocked.
          Calls the same §5.2 endpoint.  The only differences from the primary
          "Relancer" button above are: (a) it lives in a dropdown menu instead of
          the primary slot, and (b) there is no inline deferred-feedback rendering
          (the dropdown closes on select; the toast is the sole surface). */}
      {item.match === "matched" &&
        (item.blocked_reason == null || item.blocked_reason === "") && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" type="button">
                <MoreHorizontal className="size-4" aria-hidden="true" />
                <span className="sr-only">Actions</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem
                disabled={continueMut.isPending}
                onSelect={() => {
                  continueMut.mutate(item.id, {
                    onSuccess: (data) => {
                      toast.success(data.detail);
                      // A2: verify the promised run materialised within ~10 s.
                      if (!data.deferred && data.run_uid != null) {
                        void pollForRunUid(data.run_uid);
                      }
                    },
                    onError: (err: unknown) => {
                      toast.error(
                        err instanceof Error
                          ? err.message
                          : "Échec de la relance",
                      );
                    },
                  });
                }}
              >
                Re-scraper cet élément
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}

      {/* Manual resolution for a non-identified (absent) item — no auto match, so
          send it to the deck and search there. */}
      {canManualResolve && (
        <div className="flex flex-col gap-2">
          {needsKind && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">
                Type mal classé — choisissez&nbsp;:
              </span>
              <Button
                type="button"
                size="sm"
                variant={chosenKind === "movie" ? "default" : "outline"}
                onClick={() => {
                  setChosenKind("movie");
                }}
              >
                Film
              </Button>
              <Button
                type="button"
                size="sm"
                variant={chosenKind === "tvshow" ? "default" : "outline"}
                onClick={() => {
                  setChosenKind("tvshow");
                }}
              >
                Série
              </Button>
            </div>
          )}
          <Button
            type="button"
            disabled={
              enqueueMut.isPending || (needsKind && chosenKind === null)
            }
            onClick={() => {
              enqueueMut.mutate(
                needsKind ? (chosenKind ?? undefined) : undefined,
              );
            }}
          >
            {enqueueMut.isPending
              ? "Envoi…"
              : "Rechercher / résoudre manuellement"}
          </Button>
        </div>
      )}

      {/* §7 — non-media artifact egress: confirmation dialog + journal-backed
          discard.  Rendered for every "other" item so the operator can clean it
          regardless of match status. */}
      {needsKind && (
        <IgnoreDiscardButton
          mediaId={item.id}
          onSuccess={() => {
            onResolve?.();
          }}
        />
      )}
    </div>
  );
}
