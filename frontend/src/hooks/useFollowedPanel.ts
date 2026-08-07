/**
 * useFollowedPanel — the data machine behind {@link FollowedPanel}.
 *
 * Owns everything the "Suivis" tab needs beyond raw presentation: the follow /
 * unfollow / update / verification / « Récupérer maintenant » mutations, the
 * live grab-scheduler cadence caption, the fire-and-track runs (launch → track
 * to NUMERIC result → toast only on real end, via
 * {@link useTrackedAcquisitionRun}), the queued-grab readouts and the
 * edit-cadence dialog buffer. The presentation component
 * (``components/acquisition/FollowedPanel.tsx``) consumes this hook's result and
 * renders it over the ``data`` prop — no data logic lives in the view layer.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import {
  acqKeys,
  triggerFollowedGrab,
  triggerFollowedSearch,
  type FollowedSeriesItem,
} from "@/api/acquisition";
import { ApiError } from "@/api/client";
import {
  cadenceInterval,
  formatRunResult,
  GRAB_JOB_NAME,
} from "@/components/acquisition/meta";
import {
  useTrackedAcquisitionRun,
  useUnfollow,
  useUpdateFollow,
} from "@/hooks/useAcquisition";
import { useSchedulers } from "@/hooks/useSchedulers";

export { buildIdFollowBody, type FollowProvider } from "@/api/acquisition";


/** Everything {@link FollowedPanel} needs to render + drive the "Suivis" tab. */
export interface FollowedPanelMachine {
  /**
   * The automatic-search cadence read from the live grab scheduler (C15), or
   * ``null`` when the job is absent (caption omitted entirely).
   */
  readonly grabSchedule: string | null;

  // ---- Per-series actions ----
  /** Launch a manual grab search for one followed series (OBJ3). */
  readonly triggerSearch: (id: number) => void;
  /** The id of the series whose verification run is in flight, or ``null``. */
  readonly triggerPendingId: number | null;
  /**
   * Launch « Récupérer maintenant » for one item the server says is takeable
   * (five-state ``a_recuperer``).
   */
  readonly grabNow: (id: number) => void;
  /** The id of the item whose grab request is in flight, or ``null``. */
  readonly grabPendingId: number | null;
  /**
   * ``true`` when *id* has a queued grab whose run has not ended yet — the row
   * reads « En file ». A 202 is a queued state, never a promise of success
   * (NE-DOIT-PAS-1); the set is cleared when the tracked run actually ends.
   */
  readonly isGrabQueued: (id: number) => boolean;
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
  // « Récupérer maintenant » (§6): the operator must not wait for the 03:20
  // cron when a takeable version is already known. The row shows « En file »
  // until the launched run ends — a 202 is a queued state, never a promise of
  // success (NE-DOIT-PAS-1). Declared before the run tracker below, which
  // clears it when the run it belongs to ends.
  const [queuedGrabs, setQueuedGrabs] = useState<ReadonlySet<number>>(
    () => new Set(),
  );
  const markQueued = (id: number): void => {
    setQueuedGrabs((prev) => new Set(prev).add(id));
  };

  const [trackedRun, setTrackedRun] = useState<string | null>(null);
  const finishedRun = useTrackedAcquisitionRun(trackedRun);
  if (finishedRun?.ended_at != null && trackedRun != null) {
    if (finishedRun.outcome === "success") {
      const summary = formatRunResult(finishedRun.result);
      toast.success(`Exécution terminée${summary ? ` — ${summary}` : ""}.`);
    } else {
      toast.error("L'exécution a échoué — voir les exécutions récentes.");
    }
    setTrackedRun(null);
    // The « En file » readouts end with the run that carried them.
    setQueuedGrabs(new Set());
    void queryClient.invalidateQueries({ queryKey: acqKeys.all });
  }

  const triggerMutation = useMutation({
    mutationFn: (id: number) => triggerFollowedSearch(id),
    onSuccess: (res) => {
      // The action now runs the whole chain server-side (catalogue → trackers →
      // récupération), so the wording says so instead of promising a "search".
      toast.info(
        "Vérification lancée — catalogue, trackers, puis récupération…",
      );
      setTrackedRun(res.run_uid);
    },
    onError: (err: unknown) => {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          // §6 / NE-DOIT-PAS-3: the duplicate of the SAME action is the one
          // legitimate refusal — it is an information, never an error.
          toast.info("Une vérification est déjà en cours pour ce titre.");
        } else if (err.status === 404) {
          toast.error("Série introuvable.");
        } else {
          toast.error(err.detail);
        }
      } else {
        toast.error("Erreur lors du lancement de la vérification.");
      }
    },
  });

  const grabMutation = useMutation({
    mutationFn: (id: number) => triggerFollowedGrab(id),
    onSuccess: (res, id) => {
      toast.info("Récupération mise en file…");
      markQueued(id);
      setTrackedRun(res.run_uid);
    },
    onError: (err: unknown, id: number) => {
      if (err instanceof ApiError && err.status === 409) {
        // Already running for this very item: the one permitted refusal. The
        // operator's intent is satisfied, so it reads as « déjà en cours ».
        toast.info("Récupération déjà en cours pour ce titre.");
        markQueued(id);
        return;
      }
      if (err instanceof ApiError && err.status === 404) {
        toast.error("Titre introuvable.");
        return;
      }
      toast.error(
        err instanceof ApiError
          ? err.detail
          : "Erreur lors du lancement de la récupération.",
      );
    },
  });

  // Edit-cadence dialog state
  const [editTarget, setEditTarget] = useState<FollowedSeriesItem | null>(null);
  const [editInterval, setEditInterval] = useState("");

  // X3: name the action in the success toast; error toasts are owned by the
  // useUnfollow / useUpdateFollow hooks (backend detail included there).
  const handleUnfollow = (id: number): void => {
    unfollowMutation.mutate(id, {
      onSuccess: () => {
        toast.success("Suivi retiré.");
      },
    });
  };

  // Toggle active/paused in place (C16) — the update hook invalidates the
  // acquisition views, so the status badge follows without leaving the card.
  const handleToggleActive = (id: number, active: boolean): void => {
    updateMutation.mutate(
      { id, body: { active } },
      {
        onSuccess: () => {
          toast.success(active ? "Suivi réactivé." : "Suivi mis en pause.");
        },
      },
    );
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
          // X3: the dialog closing alone did not say the save actually landed.
          toast.success("Cadence mise à jour.");
          setEditTarget(null);
        },
      },
    );
  };

  return {
    grabSchedule,
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
    grabNow: (id: number) => {
      grabMutation.mutate(id);
    },
    grabPendingId: grabMutation.isPending ? grabMutation.variables : null,
    isGrabQueued: (id: number) => queuedGrabs.has(id),
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
