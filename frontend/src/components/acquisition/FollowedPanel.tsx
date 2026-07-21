/**
 * FollowedPanel — the "Suivis" tab: followed-series compact rows with add-by-ID,
 * per-series manual grab, cadence editing, unfollow, and active toggle.
 *
 * Extracted from `AcquisitionPage.tsx` (C12). Phase 02: compact rows replace the
 * MediaCard grid — 72 px poster thumb, mono completeness, one ⋯ DropdownMenu.
 * All data logic — the follow/unfollow/update/grab mutations, the live cadence
 * caption and the fire-and-track manual grab — lives in {@link useFollowedPanel};
 * this component is pure presentation over that machine and its ``data`` prop.
 */

import { Clock, MoreHorizontal, Power, Search, Trash2 } from "lucide-react";
import { type ReactElement } from "react";

import { type FollowedSeriesItem } from "@/api/acquisition";
import { MediaPoster } from "@/components/ds/MediaPoster";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useFollowedPanel } from "@/hooks/useFollowedPanel";

import { CompletenessAccordion } from "./CompletenessAccordion";
import {
  FOLLOW_KIND_LABEL,
  FOLLOW_STATUS_LABEL,
  FOLLOW_STATUS_LABEL_MOVIE,
  FOLLOW_STATUS_TONE,
  untilLabel,
} from "./meta";

/** Props for the Followed panel sub-component. */
export interface FollowedPanelProps {
  readonly data: readonly FollowedSeriesItem[];
  readonly isLoading: boolean;
  readonly isError: boolean;
  readonly error: unknown;
}

/**
 * FollowedPanel — followed-series management surface.
 *
 * Args:
 *   data: The followed-series items.
 *   isLoading: Whether the followed query is loading.
 *   isError: Whether the followed query failed.
 *   error: The query error, if any.
 *
 * Returns:
 *   The followed panel element.
 */
export function FollowedPanel({
  data,
  isLoading,
  isError,
  error,
}: FollowedPanelProps): ReactElement {
  const {
    grabSchedule,
    tvdbId,
    setTvdbId,
    title,
    setTitle,
    handleAdd,
    followPending,
    triggerSearch,
    triggerPendingId,
    handleUnfollow,
    unfollowPending,
    handleToggleActive,
    updatePending,
    editTarget,
    setEditTarget,
    editInterval,
    setEditInterval,
    openEditCadence,
    handleSaveCadence,
  } = useFollowedPanel();

  // ── Loading ────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, idx) => (
          <Skeleton key={`sk-f-${String(idx)}`} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  // ── Error ──────────────────────────────────────────────────────────────
  // Surface a real error instead of the empty state — otherwise a failed
  // query (e.g. an expired session → 401) would read as "you follow nothing"
  // and could trigger duplicate re-adds (adversarial-review finding).
  if (isError) {
    return (
      <p className="py-4 text-muted-foreground">
        Erreur de chargement des séries suivies :{" "}
        {error instanceof Error ? error.message : "Inconnue"}
      </p>
    );
  }

  // ── Add form (always visible) ──────────────────────────────────────────
  // Manual add-by-ID is the power-user fallback to the primary title search
  // above; collapsed by default so it does not compete with it. Inputs stack on
  // mobile (ID, then title, then a full-width Suivre) and inline on sm+.
  const addForm = (
    <Accordion className="rounded-lg border border-border bg-card px-3">
      <AccordionItem>
        <AccordionTrigger>Ajouter par ID TVDB</AccordionTrigger>
        <AccordionContent>
          <div className="flex flex-col gap-3 pb-3 sm:flex-row sm:items-end">
            <div className="flex flex-col gap-1 sm:w-36">
              <Label htmlFor="follow-tvdb-id">ID TVDB</Label>
              <Input
                id="follow-tvdb-id"
                type="number"
                placeholder="ex: 255968"
                value={tvdbId}
                onChange={(e) => {
                  setTvdbId(e.target.value);
                }}
              />
            </div>
            <div className="flex flex-1 flex-col gap-1">
              <Label htmlFor="follow-title">Titre (optionnel)</Label>
              <Input
                id="follow-title"
                type="text"
                placeholder="ex: Top Chef"
                value={title}
                onChange={(e) => {
                  setTitle(e.target.value);
                }}
              />
            </div>
            <Button
              className="w-full sm:w-auto sm:shrink-0"
              disabled={!tvdbId.trim() || followPending}
              onClick={handleAdd}
            >
              {followPending ? "Ajout…" : "Suivre"}
            </Button>
          </div>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );

  // ── Empty ──────────────────────────────────────────────────────────────
  // Operator review (2026-07-15): a retired follow (« Retirer » → active=0)
  // must LEAVE the rows — rendering it identically made the button look
  // broken. Retired follows collapse into a compact list below, from which
  // they can be reactivated.
  const activeItems = data.filter((item) => item.active);
  const inactiveItems = data.filter((item) => !item.active);

  if (data.length === 0) {
    return (
      <div className="space-y-4">
        {addForm}
        <div className="py-8 text-center">
          <p className="text-muted-foreground">
            Aucune série suivie. Ajoutez une série avec son identifiant TVDB
            pour commencer.
          </p>
        </div>
      </div>
    );
  }

  // ── Normal ─────────────────────────────────────────────────────────────
  return (
    <div className="space-y-4">
      {addForm}

      {/* Automatic-search cadence caption, built from the live grab scheduler
          (C15). Omitted entirely when the scheduler is unavailable — never a
          hardcoded/invented value. */}
      {grabSchedule != null && (
        <p className="text-xs text-muted-foreground">
          Recherche automatique : {grabSchedule}.
        </p>
      )}

      {/* Compact rows */}
      <div className="flex flex-col gap-2">
        {activeItems.map((item) => {
          const isMovie = item.kind === "movie";
          const statusLabel =
            (isMovie ? FOLLOW_STATUS_LABEL_MOVIE[item.status] : undefined) ??
            FOLLOW_STATUS_LABEL[item.status] ??
            item.status;
          // triggerPendingId is the id of the in-flight grab (or null) — the
          // hook's typed narrowing of the former `isPending && variables === id`
          // guard.
          const isSearching = triggerPendingId === item.id;

          return (
            <div key={`f-${String(item.id)}`} className="flex flex-col">
              {/* Compact row */}
              <div className="flex items-center gap-3 rounded-lg border border-border bg-card p-2">
                {/* Poster thumb (~72 px height, 2:3 ratio) — DS MediaPoster
                    handles the image + graceful initials fallback. */}
                <div className="shrink-0">
                  <MediaPoster
                    title={item.title}
                    src={item.poster_url ?? null}
                    className="w-[48px]"
                  />
                </div>

                {/* Title + metadata */}
                <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-medium">
                      {item.title}
                    </span>
                    <Badge
                      tone={FOLLOW_STATUS_TONE[item.status] ?? "neutral"}
                      dot
                    >
                      {statusLabel}
                    </Badge>
                    {/* Kind label — kept as a subtle hint for disambiguation. */}
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {FOLLOW_KIND_LABEL[item.kind] ?? "Série"}
                    </span>
                  </div>
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted-foreground">
                    {/* Completeness: NN/NN in font-mono tabular-nums.
                        "—" when aired_count is null (no catalog). */}
                    <span className="font-mono tabular-nums">
                      {item.aired_count != null
                        ? `${String(item.owned_count ?? 0)}/${String(item.aired_count)}`
                        : "—"}
                    </span>
                    {/* Next due. */}
                    {item.next_search_at != null && (
                      <span>{untilLabel(item.next_search_at, Date.now())}</span>
                    )}
                    {/* Wanted pending count — operator needs to know something
                        is queued even in the compact row. */}
                    {item.wanted_pending > 0 && (
                      <Badge tone="warning">
                        {String(item.wanted_pending)} en attente
                      </Badge>
                    )}
                  </div>
                </div>

                {/* Actions dropdown — ONE ⋯ button replacing all inline buttons. */}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-8 shrink-0"
                      aria-label={`Actions pour ${item.title}`}
                    >
                      <MoreHorizontal className="size-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem
                      disabled={!item.active || isSearching}
                      onSelect={() => {
                        triggerSearch(item.id);
                      }}
                    >
                      <Search className="size-4" aria-hidden="true" />
                      {isSearching ? "Recherche…" : "Rechercher maintenant"}
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onSelect={() => {
                        openEditCadence(item);
                      }}
                    >
                      <Clock className="size-4" aria-hidden="true" />
                      Cadence
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onSelect={() => {
                        handleToggleActive(item.id, !item.active);
                      }}
                    >
                      <Power className="size-4" aria-hidden="true" />
                      {item.active ? "Désactiver" : "Activer"}
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      variant="destructive"
                      disabled={unfollowPending}
                      onSelect={() => {
                        handleUnfollow(item.id);
                      }}
                    >
                      <Trash2 className="size-4" aria-hidden="true" />
                      Retirer
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>

              {/* §5 completeness: series show a season-by-season / episode-by-
                  episode matrix (aired vs médiathèque vs file); movies don't
                  (their lifecycle is the card status). Lazy — loads on open. */}
              {!isMovie && (
                <CompletenessAccordion
                  followedId={item.id}
                  title={item.title}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Retired follows — compact, reactivatable (operator review 2026-07-15). */}
      {inactiveItems.length > 0 && (
        <details className="rounded-md border border-border p-3">
          <summary className="cursor-pointer text-sm font-medium text-muted-foreground">
            Suivis retirés ({inactiveItems.length})
          </summary>
          <ul className="mt-2 space-y-2">
            {inactiveItems.map((item) => (
              <li
                key={`inactive-${String(item.id)}`}
                className="flex flex-wrap items-center justify-between gap-2"
              >
                <span className="min-w-0 break-words text-sm">
                  {item.title}
                  {item.year != null && (
                    <span className="text-muted-foreground">
                      {" "}
                      ({item.year})
                    </span>
                  )}
                </span>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    handleToggleActive(item.id, true);
                  }}
                  disabled={updatePending}
                >
                  Réactiver
                </Button>
              </li>
            ))}
          </ul>
        </details>
      )}

      {/* Edit-cadence dialog */}
      <Dialog
        open={editTarget !== null}
        onOpenChange={(open) => {
          if (!open) setEditTarget(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Modifier la cadence</DialogTitle>
            <DialogDescription>
              {editTarget?.title ?? ""} — définissez l&apos;intervalle en
              minutes entre deux vérifications.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div>
              <Label htmlFor="cadence-interval">Intervalle (minutes)</Label>
              <Input
                id="cadence-interval"
                type="number"
                min={0}
                value={editInterval}
                onChange={(e) => {
                  setEditInterval(e.target.value);
                }}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setEditTarget(null);
              }}
            >
              Annuler
            </Button>
            <Button onClick={handleSaveCadence} disabled={updatePending}>
              {updatePending ? "Enregistrement…" : "Enregistrer"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
