/**
 * FollowedPanel — the "Suivis" tab: followed-series cards with add-by-ID,
 * per-series manual grab, cadence editing and unfollow.
 *
 * Extracted from `AcquisitionPage.tsx` (C12). Behaviour unchanged.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactElement } from "react";
import { toast } from "sonner";

import {
  acqKeys,
  triggerFollowedSearch,
  type CreateFollowRequest,
  type FollowedSeriesItem,
} from "@/api/acquisition";
import { ApiError } from "@/api/client";
import { MediaCard } from "@/components/ds/MediaCard";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  useFollow,
  useTrackedAcquisitionRun,
  useUnfollow,
  useUpdateFollow,
} from "@/hooks/useAcquisition";
import { useSchedulers } from "@/hooks/useSchedulers";

import { CompletenessAccordion } from "./CompletenessAccordion";
import {
  cadenceInterval,
  FOLLOW_KIND_LABEL,
  FOLLOW_STATUS_LABEL,
  FOLLOW_STATUS_TONE,
  formatRunResult,
  GRAB_JOB_NAME,
  TEMP_COLOR,
  TIER_LABEL,
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
  const queryClient = useQueryClient();
  const followMutation = useFollow();
  const unfollowMutation = useUnfollow();
  const updateMutation = useUpdateFollow();

  // C15: the automatic-search cadence caption is read from the live grab
  // scheduler, never hardcoded — and omitted entirely when the job is absent.
  const { data: schedulers } = useSchedulers();
  const grabSchedule =
    schedulers?.schedulers.find((s) => s.name === GRAB_JOB_NAME)?.schedule ??
    null;

  // Per-series manual grab trigger (OBJ3). Fire-and-track: the 202 launches a
  // grab run; feedback is a toast (409 = already running, 404 = gone). On
  // success we also refresh the acquisition views (C16) so the card's pending
  // count / status reflect the freshly enqueued search without a manual reload.
  // §5: never a success toast on the 202 — track the launched grab to its
  // NUMERIC result and toast only once the run actually ends.
  const [trackedRun, setTrackedRun] = useState<string | null>(null);
  const finishedRun = useTrackedAcquisitionRun(trackedRun);
  if (finishedRun?.ended_at != null && trackedRun != null) {
    if (finishedRun.outcome === "success") {
      const summary = formatRunResult(finishedRun.result);
      toast.success(`Recherche terminée${summary ? ` — ${summary}` : ""}.`);
    } else {
      toast.error("La recherche a échoué — voir les exécutions récentes.");
    }
    setTrackedRun(null);
    void queryClient.invalidateQueries({ queryKey: acqKeys.all });
  }

  const triggerMutation = useMutation({
    mutationFn: (id: number) => triggerFollowedSearch(id),
    onSuccess: (res) => {
      toast.info("Recherche lancée…");
      setTrackedRun(res.run_uid);
    },
    onError: (err: unknown) => {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          toast.error("Une recherche est déjà en cours pour cette série.");
        } else if (err.status === 404) {
          toast.error("Série introuvable.");
        } else {
          toast.error(err.detail);
        }
      } else {
        toast.error("Erreur lors du lancement de la recherche.");
      }
    },
  });

  // Add-form state
  const [tvdbId, setTvdbId] = useState("");
  const [title, setTitle] = useState("");

  // Edit-cadence dialog state
  const [editTarget, setEditTarget] = useState<FollowedSeriesItem | null>(null);
  const [editInterval, setEditInterval] = useState("");

  const handleAdd = (): void => {
    const tvdb = tvdbId.trim() ? Number(tvdbId.trim()) : null;
    if (tvdb === null || !Number.isFinite(tvdb)) return;
    // The manual add-by-TVDB-id form is series-only (a TVDB id is a series id);
    // films are followed from the search cards, which carry kind='movie'.
    const body: CreateFollowRequest = { tvdb_id: tvdb, kind: "show" };
    if (title.trim()) body.title = title.trim();
    followMutation.mutate(body, {
      onSuccess: () => {
        setTvdbId("");
        setTitle("");
      },
    });
  };

  const handleUnfollow = (id: number): void => {
    unfollowMutation.mutate(id);
  };

  // Toggle active/paused in place (C16) — the update hook invalidates the
  // acquisition views, so the status badge follows without leaving the card.
  const handleToggleActive = (id: number, active: boolean): void => {
    updateMutation.mutate({ id, body: { active } });
  };

  const openEditCadence = (item: FollowedSeriesItem): void => {
    setEditTarget(item);
    setEditInterval(String(cadenceInterval(item.cadence)));
  };

  const handleSaveCadence = (): void => {
    if (editTarget === null) return;
    const interval = Number(editInterval);
    if (!Number.isFinite(interval) || interval < 0) return;
    updateMutation.mutate(
      { id: editTarget.id, body: { cadence: { interval_minutes: interval } } },
      {
        onSuccess: () => {
          setEditTarget(null);
        },
      },
    );
  };

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
              disabled={!tvdbId.trim() || followMutation.isPending}
              onClick={handleAdd}
            >
              {followMutation.isPending ? "Ajout…" : "Suivre"}
            </Button>
          </div>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );

  // ── Empty ──────────────────────────────────────────────────────────────
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

      {/* Card grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {data.map((item) => {
          const interval = cadenceInterval(item.cadence);
          const seasons = item.season_count ?? 0;
          const isMovie = item.kind === "movie";
          return (
            <div key={`f-${String(item.id)}`} className="flex flex-col gap-2">
              <MediaCard
                title={item.title}
                year={item.year ?? null}
                kind={isMovie ? "movie" : "tv"}
                posterUrl={item.poster_url ?? null}
                overview={item.overview ?? null}
                badges={
                <>
                  {/* Film vs Série (§5). */}
                  <Badge tone="neutral">
                    {FOLLOW_KIND_LABEL[item.kind] ?? "Série"}
                  </Badge>
                  {/* Backend-derived lifecycle status (C14): the UI only maps
                      status → tone/label, no business derivation in JSX. */}
                  <Badge
                    tone={FOLLOW_STATUS_TONE[item.status] ?? "neutral"}
                    dot
                  >
                    {FOLLOW_STATUS_LABEL[item.status] ?? item.status}
                  </Badge>
                  {/* TVDB id kept as its own node (test + operator reference). */}
                  {item.media_ref.tvdb_id != null && (
                    <span className="font-mono text-xs text-muted-foreground">
                      {String(item.media_ref.tvdb_id)}
                    </span>
                  )}
                  {seasons > 0 && (
                    <span className="text-xs text-muted-foreground">
                      {seasons} saison{seasons > 1 ? "s" : ""}
                    </span>
                  )}
                  {item.wanted_pending > 0 && (
                    <Badge tone="warning">
                      {String(item.wanted_pending)} en attente
                    </Badge>
                  )}
                  {item.active &&
                  item.cadence_tier != null &&
                  item.next_search_at != null ? (
                    <span
                      className="inline-flex items-center gap-1 text-xs font-medium"
                      style={{
                        color:
                          TEMP_COLOR[item.cadence_tier] ??
                          "var(--muted-foreground)",
                      }}
                      title={TIER_LABEL[item.cadence_tier] ?? item.cadence_tier}
                    >
                      <span
                        className="size-1.5 rounded-full"
                        style={{
                          backgroundColor:
                            TEMP_COLOR[item.cadence_tier] ?? "currentColor",
                        }}
                        aria-hidden
                      />
                      Prochaine recherche{" "}
                      {untilLabel(item.next_search_at, Date.now())}
                    </span>
                  ) : (
                    interval > 0 && (
                      <span className="text-xs text-muted-foreground">
                        cadence {String(interval)} min
                      </span>
                    )
                  )}
                  {item.quality_profile != null && (
                    <Badge tone="info">Personnalisé</Badge>
                  )}
                </>
              }
              footer={
                <div className="flex w-full flex-wrap items-center gap-2">
                  {/* C16: primary in-card action — launch a search now, with a
                      spinner + toast + refresh (see triggerMutation). */}
                  <Button
                    size="sm"
                    onClick={() => {
                      triggerMutation.mutate(item.id);
                    }}
                    disabled={
                      !item.active ||
                      (triggerMutation.isPending &&
                        triggerMutation.variables === item.id)
                    }
                    title={
                      item.active
                        ? "Lancer une recherche maintenant pour cette série"
                        : "Série désactivée — réactivez-la pour lancer une recherche"
                    }
                  >
                    {triggerMutation.isPending &&
                    triggerMutation.variables === item.id
                      ? "Recherche…"
                      : "Rechercher maintenant"}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      openEditCadence(item);
                    }}
                  >
                    Cadence
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      handleUnfollow(item.id);
                    }}
                    disabled={unfollowMutation.isPending}
                  >
                    Retirer
                  </Button>
                  {/* C16: activate/pause the series in place. */}
                  <div className="ml-auto flex items-center gap-1.5">
                    <Switch
                      id={`follow-active-${String(item.id)}`}
                      checked={item.active}
                      onCheckedChange={(checked) => {
                        handleToggleActive(item.id, checked);
                      }}
                      disabled={updateMutation.isPending}
                      aria-label={
                        item.active
                          ? `Désactiver le suivi de ${item.title}`
                          : `Activer le suivi de ${item.title}`
                      }
                    />
                    <label
                      htmlFor={`follow-active-${String(item.id)}`}
                      className="text-xs text-muted-foreground"
                    >
                      {item.active ? "Actif" : "Inactif"}
                    </label>
                  </div>
                </div>
              }
              />
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
            <Button
              onClick={handleSaveCadence}
              disabled={updateMutation.isPending}
            >
              {updateMutation.isPending ? "Enregistrement…" : "Enregistrer"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
