/**
 * useFollowedPanel — the data machine behind {@link FollowedPanel}.
 *
 * Owns everything the "Suivis" tab needs beyond raw presentation: the follow /
 * unfollow / update / manual-grab mutations, the live grab-scheduler cadence
 * caption, the fire-and-track manual grab (launch → track to NUMERIC result →
 * toast only on real end, via {@link useTrackedAcquisitionRun}), the add-by-id
 * form buffer and the edit-cadence dialog buffer. The presentation component
 * (``components/acquisition/FollowedPanel.tsx``) consumes this hook's result and
 * renders it over the ``data`` prop — no data logic lives in the view layer.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import {
  acqKeys,
  triggerFollowedSearch,
  type CreateFollowRequest,
  type FollowedSeriesItem,
} from "@/api/acquisition";
import { ApiError } from "@/api/client";
import {
  cadenceInterval,
  formatRunResult,
  GRAB_JOB_NAME,
} from "@/components/acquisition/meta";
import {
  useFollow,
  useTrackedAcquisitionRun,
  useUnfollow,
  useUpdateFollow,
} from "@/hooks/useAcquisition";
import { useSchedulers } from "@/hooks/useSchedulers";

/** Everything {@link FollowedPanel} needs to render + drive the "Suivis" tab. */
export interface FollowedPanelMachine {
  /**
   * The automatic-search cadence read from the live grab scheduler (C15), or
   * ``null`` when the job is absent (caption omitted entirely).
   */
  readonly grabSchedule: string | null;

  // ---- Add-by-id form ----
  /** Add-form TVDB id input value. */
  readonly tvdbId: string;
  /** Set the add-form TVDB id. */
  readonly setTvdbId: (value: string) => void;
  /** Add-form title input value. */
  readonly title: string;
  /** Set the add-form title. */
  readonly setTitle: (value: string) => void;
  /** Submit the add-by-TVDB-id form (series-only). */
  readonly handleAdd: () => void;
  /** ``true`` while a follow (add) mutation is in flight. */
  readonly followPending: boolean;

  // ---- Per-series actions ----
  /** Launch a manual grab search for one followed series (OBJ3). */
  readonly triggerSearch: (id: number) => void;
  /** The id of the series whose manual grab is currently in flight, or ``null``. */
  readonly triggerPendingId: number | null;
  /** Unfollow (retire) a series. */
  readonly handleUnfollow: (id: number) => void;
  /** ``true`` while an unfollow mutation is in flight. */
  readonly unfollowPending: boolean;
  /** Toggle a series active / paused in place (C16). */
  readonly handleToggleActive: (id: number, active: boolean) => void;
  /** ``true`` while an update (toggle / cadence) mutation is in flight. */
  readonly updatePending: boolean;

  // ---- Edit-cadence dialog ----
  /** The series being edited in the cadence dialog, or ``null`` (dialog closed). */
  readonly editTarget: FollowedSeriesItem | null;
  /** Set the cadence-dialog target (``null`` closes it). */
  readonly setEditTarget: (item: FollowedSeriesItem | null) => void;
  /** Cadence-dialog interval input value. */
  readonly editInterval: string;
  /** Set the cadence-dialog interval. */
  readonly setEditInterval: (value: string) => void;
  /** Open the cadence dialog for a series (seeds the interval). */
  readonly openEditCadence: (item: FollowedSeriesItem) => void;
  /** Save the edited cadence. */
  readonly handleSaveCadence: () => void;
}

/**
 * Drive the followed-series management surface.
 *
 * Returns:
 *   A {@link FollowedPanelMachine} the presentation renders over its ``data``
 *   prop.
 */
export function useFollowedPanel(): FollowedPanelMachine {
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

  return {
    grabSchedule,
    tvdbId,
    setTvdbId,
    title,
    setTitle,
    handleAdd,
    followPending: followMutation.isPending,
    triggerSearch: (id: number) => {
      triggerMutation.mutate(id);
    },
    // In TanStack's pending state ``variables`` is the id passed to ``mutate``
    // (the result type narrows it to non-undefined), so this is the id of the
    // in-flight grab or null — matching the former
    // ``isPending && variables === item.id`` guard.
    triggerPendingId: triggerMutation.isPending
      ? triggerMutation.variables
      : null,
    handleUnfollow,
    unfollowPending: unfollowMutation.isPending,
    handleToggleActive,
    updatePending: updateMutation.isPending,
    editTarget,
    setEditTarget,
    editInterval,
    setEditInterval,
    openEditCadence,
    handleSaveCadence,
  };
}
