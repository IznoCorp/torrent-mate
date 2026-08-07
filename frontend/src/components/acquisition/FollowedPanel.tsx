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

import {
  Clock,
  Download,
  ExternalLink,
  MoreHorizontal,
  Power,
  Search,
  Trash2,
} from "lucide-react";
import { useState, type ReactElement } from "react";
import { useNavigate } from "react-router-dom";

import { type FollowedSeriesItem } from "@/api/acquisition";
import { MediaPoster } from "@/components/ds/MediaPoster";
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
  canGrabNow,
  FOLLOW_STATUS_TONE,
  followCountsCaption,
  followFraction,
  followMediaRef,
  followStatusHint,
  followStatusLabel,
  followWaitingReason,
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
  const navigate = useNavigate();
  const {
    grabSchedule,
    triggerSearch,
    triggerPendingId,
    grabNow,
    grabPendingId,
    isGrabQueued,
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

  // #20: séries / films sub-tabs. Declared before any early return so the hook
  // order stays stable. Default « Séries » (the primary followed-media kind).
  const [kindTab, setKindTab] = useState<"show" | "movie">("show");
  // Name filter over the followed list (applies on change, no submit).
  const [nameFilter, setNameFilter] = useState("");

  // ACQUISITION-3 (ticket 250): « Retirer » is destructive — it must confirm
  // before mutating. Holds the item pending confirmation, or null.
  const [confirmUnfollow, setConfirmUnfollow] =
    useState<FollowedSeriesItem | null>(null);

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

  // ── Empty ──────────────────────────────────────────────────────────────
  // Operator review (2026-07-15): a retired follow (« Retirer » → active=0)
  // must LEAVE the rows — rendering it identically made the button look
  // broken. Retired follows collapse into a compact list below, from which
  // they can be reactivated.
  const activeItems = data.filter((item) => item.active);
  const inactiveItems = data.filter((item) => !item.active);

  // #20: partition by kind so the « Séries » / « Films » sub-tabs each show only
  // their own follows (and the retired list follows the same split).
  const isFilm = (item: FollowedSeriesItem): boolean => item.kind === "movie";
  const activeSeries = activeItems.filter((item) => !isFilm(item));
  const activeMovies = activeItems.filter(isFilm);

  // Name filter. Accent- and case-insensitive so « evades » finds « Les Évadés »
  // — a filter that demands the exact diacritics is a filter the operator has to
  // fight. NFD decomposition + stripping combining marks is the same normalisation
  // the backend matching uses.
  const normalise = (text: string): string =>
    text
      .normalize("NFD")
      .replace(/\p{Diacritic}/gu, "")
      .toLocaleLowerCase();
  const filterTerm = normalise(nameFilter.trim());
  const matchesFilter = (item: FollowedSeriesItem): boolean =>
    filterTerm === "" || normalise(item.title).includes(filterTerm);

  // The counts on the Séries/Films toggle stay UNFILTERED: they answer "how many
  // do I follow", not "how many match what I typed". Filtering them would make
  // the toggle change under the operator's own typing.
  const visibleActive = (
    kindTab === "movie" ? activeMovies : activeSeries
  ).filter(matchesFilter);
  const visibleInactive = (
    kindTab === "movie"
      ? inactiveItems.filter(isFilm)
      : inactiveItems.filter((item) => !isFilm(item))
  ).filter(matchesFilter);

  if (data.length === 0) {
    return (
      <div className="py-8 text-center">
        <p className="text-muted-foreground">
          Aucune série suivie. Utilisez la recherche ci-dessus (par titre ou par
          identifiant TVDB, TMDB ou IMDB) pour commencer.
        </p>
      </div>
    );
  }

  // ── Normal ─────────────────────────────────────────────────────────────
  return (
    <div className="space-y-4">
      {/* #20: séries / films filter. A segmented toggle group (aria-pressed) —
          NOT a tablist: there is no separate tabpanel, and this matches the
          identical toggle-groups elsewhere on the screen (MediaSearchAdd's kind
          + provider pickers). Counts read the ACTIVE follows only (the retired
          list has its own collapsed section per tab). */}
      <div
        role="group"
        aria-label="Filtrer les suivis par type"
        className="flex items-center gap-1 rounded-md border border-border p-0.5 sm:w-fit"
      >
        {(["show", "movie"] as const).map((k) => (
          <Button
            key={k}
            type="button"
            aria-pressed={kindTab === k}
            size="sm"
            className="min-h-11 flex-1 sm:flex-none md:min-h-8"
            variant={kindTab === k ? "default" : "ghost"}
            onClick={() => {
              setKindTab(k);
            }}
          >
            {k === "show" ? "Séries" : "Films"} (
            {k === "show" ? activeSeries.length : activeMovies.length})
          </Button>
        ))}
      </div>

      {/* Automatic-search cadence caption, built from the live grab scheduler
          (C15). Omitted entirely when the scheduler is unavailable — never a
          hardcoded/invented value. */}
      {grabSchedule != null && (
        <p className="text-xs text-muted-foreground">
          Recherche automatique : {grabSchedule}.
        </p>
      )}

      {/* Name filter: the followed list only grows, and past a dozen rows
          finding one means scrolling the whole thing. Filters on change (no
          submit) because the list is already in memory — a round-trip would be
          latency for nothing. */}
      <div className="flex flex-col gap-1">
        <label
          htmlFor="followed-filter"
          className="text-xs font-medium text-muted-foreground"
        >
          Filtrer par nom
        </label>
        <Input
          id="followed-filter"
          type="search"
          value={nameFilter}
          placeholder={
            kindTab === "movie" ? "Titre du film" : "Titre de la série"
          }
          onChange={(e) => {
            setNameFilter(e.target.value);
          }}
        />
      </div>

      {/* Per-tab empty hint — there ARE follows, just none of this kind. */}
      {visibleActive.length === 0 && (
        <p className="py-4 text-center text-sm text-muted-foreground">
          {filterTerm !== "" ? (
            // A filter that hides everything must say it is the filter doing it,
            // otherwise the screen reads as "you follow nothing" (§8).
            <>
              Aucun résultat pour « {nameFilter.trim()} » parmi les{" "}
              {kindTab === "movie" ? "films" : "séries"} suivis.
            </>
          ) : kindTab === "movie" ? (
            "Aucun film suivi."
          ) : (
            "Aucune série suivie."
          )}
        </p>
      )}

      {/* Compact rows */}
      <div className="flex flex-col gap-2">
        {visibleActive.map((item) => {
          const isMovie = item.kind === "movie";
          // Every readout below is a pure mapping of SERVER facts computed
          // outside the JSX — no business derivation in the markup.
          const statusLabel = followStatusLabel(item.status, item.kind);
          const fraction = followFraction(item);
          const countsCaption = followCountsCaption(item);
          const waitingReason = followWaitingReason(item);
          // triggerPendingId / grabPendingId are the ids of the in-flight
          // runs (or null) — the hook's typed narrowing of the former
          // `isPending && variables === id` guards.
          const isSearching = triggerPendingId === item.id;
          const isGrabbing = grabPendingId === item.id;
          const isQueued = isGrabQueued(item.id);
          const sheetHref = followMediaRef(item);

          return (
            <div key={`f-${String(item.id)}`} className="flex flex-col">
              {/* Compact row */}
              <div className="flex items-center gap-3 rounded-lg border border-border bg-card p-2">
                {/* Poster thumb — clickable when a media sheet is available (§11). */}
                {sheetHref !== null ? (
                  <button
                    type="button"
                    className="shrink-0"
                    onClick={() => {
                      void navigate(sheetHref);
                    }}
                    aria-label={`Fiche de ${item.title}`}
                  >
                    <MediaPoster
                      title={item.title}
                      src={item.poster_url ?? null}
                      className="w-[48px]"
                    />
                  </button>
                ) : (
                  <div className="shrink-0">
                    <MediaPoster
                      title={item.title}
                      src={item.poster_url ?? null}
                      className="w-[48px]"
                    />
                  </div>
                )}

                {/* Title + metadata — MOBILE FIRST (§12): on a phone the width is
                    the scarce resource, so the title gets a line of its own and
                    everything that qualifies it drops to the line below. Sharing
                    that line (title + statut + type) truncated real titles to
                    « A Knight of the Seven King… » on the screen the operator
                    actually uses. */}
                <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                  {/* Line 1 — the title, alone. */}
                  <div className="min-w-0">
                    {sheetHref !== null ? (
                      <button
                        type="button"
                        className="block w-full truncate text-left text-sm font-medium hover:underline"
                        onClick={() => {
                          void navigate(sheetHref);
                        }}
                      >
                        {item.title}
                      </button>
                    ) : (
                      <span className="block w-full truncate text-sm font-medium">
                        {item.title}
                      </span>
                    )}
                  </div>
                  {/* Line 2 — completeness FIRST (the number the operator scans
                      for), then the status, then the rest. The kind label
                      (« Série » / « Film ») is gone: the Séries/Films sub-tabs
                      already say it, and on a phone a redundant word costs
                      width the title needs. */}
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted-foreground">
                    {/* Completeness: NN/NN in font-mono tabular-nums, "—" when
                        a série has no catalog, nothing at all for a film. */}
                    {fraction != null && (
                      <span className="font-mono tabular-nums">{fraction}</span>
                    )}
                    {/* Status chip: pure mapping of the SERVER state — no
                        client-side derivation. The wrapper's title spells the
                        state out so « En attente » and « Non vérifié », which
                        share a neutral tone, can never be confused (DOIT-1). */}
                    <span title={followStatusHint(item.status, item.kind)}>
                      <Badge tone={FOLLOW_STATUS_TONE[item.status]} dot>
                        {statusLabel}
                      </Badge>
                    </span>
                    {/* An active show with no resolved TVDB id is inert — episode
                        detection skips it. Surface it persistently (not just a
                        create-time toast) so a reactivated/resumed follow can
                        never look healthy while silently detecting nothing
                        (§méthode: never silently inert). */}
                    {item.tvdb_unresolved && (
                      <span title="Détection d'épisodes indisponible : l'ID TVDB de cette série n'a pas pu être résolu. Ajoutez-la par son ID TVDB.">
                        <Badge tone="warning" dot>
                          Sans ID TVDB
                        </Badge>
                      </span>
                    )}
                    {/* Next due. */}
                    {item.next_search_at != null && (
                      <span>{untilLabel(item.next_search_at, Date.now())}</span>
                    )}
                    {/* What is still moving / still owed, per the SAME
                        server-side five-state counts the chip reads — never the
                        raw wanted_pending counter (NE-DOIT-PAS-2 without the
                        founding lie). */}
                    {countsCaption != null && <span>{countsCaption}</span>}
                    {/* A film has no episode matrix: the reason its single unit
                        is not acquired belongs here, in French, mapped from the
                        same facts the chip was derived from. */}
                    {waitingReason != null && <span>{waitingReason}</span>}
                    {/* « Récupérer maintenant » — offered exactly where the
                        server says something is takeable. It sits on the
                        wrapping metadata line so it never pushes the row past
                        the viewport on a phone. */}
                    {canGrabNow(item) && (
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={isGrabbing || isQueued}
                        onClick={() => {
                          grabNow(item.id);
                        }}
                      >
                        <Download className="size-4" aria-hidden="true" />
                        {isQueued ? "En file" : "Récupérer maintenant"}
                      </Button>
                    )}
                  </div>
                </div>

                {/* Actions dropdown — ONE ⋯ button replacing all inline buttons. */}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-8 min-h-11 min-w-11 shrink-0 md:min-h-8 md:min-w-8"
                      aria-label={`Actions pour ${item.title}`}
                    >
                      <MoreHorizontal className="size-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    {/* §11 constitution: every identified media must lead to its sheet. */}
                    {sheetHref != null && (
                      <DropdownMenuItem
                        onSelect={() => {
                          void navigate(sheetHref);
                        }}
                      >
                        <ExternalLink className="size-4" aria-hidden="true" />
                        Voir la fiche
                      </DropdownMenuItem>
                    )}
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
                        // ACQUISITION-3: open the confirmation dialog — the
                        // mutation only fires on the dialog's « Retirer ».
                        setConfirmUnfollow(item);
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

      {/* Retired follows — compact, reactivatable (operator review 2026-07-15).
          Scoped to the active sub-tab's kind (#20). */}
      {visibleInactive.length > 0 && (
        <details className="rounded-md border border-border p-3">
          <summary className="cursor-pointer text-sm font-medium text-muted-foreground">
            Suivis retirés ({visibleInactive.length})
          </summary>
          <ul className="mt-2 space-y-2">
            {visibleInactive.map((item) => (
              <li
                key={`inactive-${String(item.id)}`}
                // #23 — no wrap: a long title truncates and the « Réactiver »
                // button stays on the same line (shrink-0) instead of dropping
                // below on mobile.
                className="flex items-center gap-2"
              >
                <span className="min-w-0 flex-1 truncate text-sm">
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
                  className="shrink-0"
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

      {/* ACQUISITION-3 (ticket 250): unfollow confirmation dialog — mirrors the
          edit-cadence Dialog pattern of this same panel. Cancel keeps the
          follow untouched; confirm fires the (soft-delete) unfollow. */}
      <Dialog
        open={confirmUnfollow !== null}
        onOpenChange={(open) => {
          if (!open) setConfirmUnfollow(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Retirer ce suivi ?</DialogTitle>
            <DialogDescription>
              « {confirmUnfollow?.title ?? ""} » ne sera plus surveillé. Le
              suivi est désactivé, pas supprimé : vous pourrez le réactiver
              depuis la liste « Suivis retirés ».
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setConfirmUnfollow(null);
              }}
            >
              Annuler
            </Button>
            <Button
              variant="destructive"
              disabled={unfollowPending}
              onClick={() => {
                if (confirmUnfollow !== null)
                  handleUnfollow(confirmUnfollow.id);
                setConfirmUnfollow(null);
              }}
            >
              Retirer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

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
