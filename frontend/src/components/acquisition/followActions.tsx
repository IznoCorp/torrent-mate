/**
 * followActions — the ONE source of a follow's management actions.
 *
 * Swipe (A10), the desktop « ··· » (A11/A12) and the detail sheet all offer the
 * same verbs; §13 makes them read one builder so the three surfaces cannot
 * drift. The verbs come from {@link actionWords} — film and série do not
 * suspend or leave with the same words (§9).
 *
 * Removal is CONFIRMED here (§9): swiping past a destructive action must never
 * BE the action, so both swipe and menu route through one dialog whose wording
 * says what removal means for the nature — a série is deactivated and
 * reactivable, a film leaves the list.
 */

import { useState, type ReactElement } from "react";

import { toast } from "sonner";
import { useNavigate } from "react-router-dom";

import type { FollowedSeriesItem } from "@/api/acquisition";
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
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useGrabNow, useUnfollow, useUpdateFollow } from "@/hooks/useAcquisition";

import type { SwipeAction } from "./SwipeActions";
import { actionWords, asMediaKind, followMediaRef } from "./meta";

/* Maquette icon set `I` — verbatim SVG paths (down/pause/trash), sized 17 px
 * by the `.act svg` rule. */
const ICON_DOWN = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
    <path d="M12 4v12M6 12l6 6 6-6" />
  </svg>
);
const ICON_PAUSE = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
    <path d="M10 5v14M14 5v14" />
  </svg>
);
const ICON_TRASH = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
    <path d="M4 7h16M9 7V5h6v2M7 7l1 13h8l1-13" />
  </svg>
);

/** Both sides of a follow card's swipe — spread onto {@link SwipeActions}. */
export interface FollowSwipe {
  /** The affirmative action (rightward drag) — present only when one exists. */
  readonly left?: SwipeAction;
  /** Suspend/resume then remove (§9's 84 px pair), on a leftward drag. */
  readonly right: readonly SwipeAction[];
}

/** What {@link useFollowActions} hands a panel. */
export interface FollowActions {
  /** Swipe actions for one follow — « Récupérer » on the left when takeable,
   *  suspend/resume + remove on the right. */
  readonly swipeFor: (
    item: FollowedSeriesItem,
    opts?: { readonly remove?: boolean },
  ) => FollowSwipe;
  /** The « ··· » kebab for one follow — rendered by the card on fine pointers only (A11). */
  readonly menuFor: (item: FollowedSeriesItem) => ReactElement;
  /** The shared removal-confirmation dialog — render ONCE per panel. */
  readonly dialog: ReactElement;
  /** Open the cadence editor for one follow — the sheet's « Cadence de
   *  recherche » routes here so the dialog stays single-sourced (§13). */
  readonly openCadence: (item: FollowedSeriesItem) => void;
}

/**
 * Build the follow-management actions for a panel.
 *
 * Returns:
 *   The action builders plus the confirmation dialog element.
 */
export function useFollowActions(): FollowActions {
  const navigate = useNavigate();
  const updateFollow = useUpdateFollow();
  const unfollow = useUnfollow();
  const grabNow = useGrabNow();
  const [removing, setRemoving] = useState<FollowedSeriesItem | null>(null);
  // The per-series search cadence editor, re-homed from the dissolved list
  // panel: an operator-set cadence with no surface left to set it is a
  // feature silently withdrawn.
  const [cadenceTarget, setCadenceTarget] = useState<FollowedSeriesItem | null>(null);
  const [cadenceInterval, setCadenceInterval] = useState("");

  const words = (item: FollowedSeriesItem) =>
    actionWords(asMediaKind(item.kind) === "movie" ? "movie" : "show");

  const suspendOrResume = (item: FollowedSeriesItem): void => {
    // "disabled" is the server's derivation of active=0 — read, not re-derived.
    updateFollow.mutate({
      id: item.id,
      body: { active: item.status === "disabled" },
    });
  };

  const swipeFor = (
    item: FollowedSeriesItem,
    opts?: { readonly remove?: boolean },
  ): FollowSwipe => {
    const w = words(item);
    const paused = item.status === "disabled";
    const right: readonly SwipeAction[] = [
      {
        key: "suspend",
        label: paused ? w.resumeShort : w.pauseShort,
        icon: ICON_PAUSE,
        actClass: "pause",
        onRun: () => {
          suspendOrResume(item);
        },
      },
      // The maquette pares « Maintenant »'s takeable cards down to the two
      // verbs of the moment — removal stays one tap away in the sheet.
      ...(opts?.remove === false
        ? []
        : [
            {
              key: "remove",
              label: "Retirer",
              icon: ICON_TRASH,
              actClass: "remove" as const,
              onRun: () => {
                setRemoving(item);
              },
            },
          ]),
    ];
    // The affirmative side exists only when the server says the item is
    // takeable — a « Récupérer » that fires a search on a complete série
    // would be a dead promise wearing a primary tone.
    if (item.status !== "a_recuperer") return { right };
    return {
      left: {
        key: "grab",
        label: "Récupérer",
        icon: ICON_DOWN,
        actClass: "grab",
        onRun: () => {
          grabNow.mutate(item.id);
        },
      },
      right,
    };
  };

  const menuFor = (item: FollowedSeriesItem): ReactElement => {
    const w = words(item);
    const paused = item.status === "disabled";
    const href = followMediaRef(item);
    return (
      <DropdownMenu>
        <DropdownMenuTrigger
          aria-label={`Actions pour ${item.title}`}
          className="rounded px-2 py-1 text-muted-foreground hover:bg-accent hover:text-foreground"
        >
          ···
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          {/* A12 — the kebab always offers the sheet when one exists. */}
          {href != null && (
            <DropdownMenuItem
              onSelect={() => {
                void navigate(href);
              }}
            >
              Voir la fiche
            </DropdownMenuItem>
          )}
          <DropdownMenuItem
            onSelect={() => {
              suspendOrResume(item);
            }}
          >
            {paused ? w.resume : w.pause}
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={() => {
              setCadenceTarget(item);
              setCadenceInterval("");
            }}
          >
            Modifier la cadence
          </DropdownMenuItem>
          <DropdownMenuItem
            variant="destructive"
            onSelect={() => {
              setRemoving(item);
            }}
          >
            {w.remove}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    );
  };

  const dialog = (
    <Dialog
      open={removing != null}
      onOpenChange={(open) => {
        if (!open) setRemoving(null);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {removing != null ? words(removing).removeConfirmTitle : ""}
          </DialogTitle>
          <DialogDescription>
            {removing != null ? words(removing).removeConfirmBody : ""}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <button
            type="button"
            className="rounded-md border border-border px-3 py-2 text-sm hover:bg-accent"
            onClick={() => {
              setRemoving(null);
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
              if (removing != null) unfollow.mutate(removing.id);
              setRemoving(null);
            }}
          >
            {removing != null ? words(removing).remove : ""}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );

  const cadenceDialog = (
    <Dialog
      open={cadenceTarget != null}
      onOpenChange={(open) => {
        if (!open) setCadenceTarget(null);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Modifier la cadence</DialogTitle>
          <DialogDescription>
            {cadenceTarget?.title ?? ""} — définissez l&apos;intervalle en
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
              value={cadenceInterval}
              onChange={(e) => {
                setCadenceInterval(e.target.value);
              }}
            />
          </div>
        </div>
        <DialogFooter>
          <button
            type="button"
            className="rounded-md border border-border px-3 py-2 text-sm hover:bg-accent"
            onClick={() => {
              setCadenceTarget(null);
            }}
          >
            Annuler
          </button>
          <button
            data-testid="enregistrer-la-cadence"
            type="button"
            disabled={updateFollow.isPending}
            className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            onClick={() => {
              if (cadenceTarget == null) return;
              const interval = Number(cadenceInterval);
              if (!Number.isFinite(interval) || interval < 0) return;
              updateFollow.mutate(
                {
                  id: cadenceTarget.id,
                  body: { cadence: { interval_minutes: interval } },
                },
                {
                  onSuccess: () => {
                    // The dialog closing alone does not say the save landed.
                    toast.success("Cadence mise à jour.");
                  },
                },
              );
              setCadenceTarget(null);
            }}
          >
            Enregistrer
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );

  return {
    swipeFor,
    menuFor,
    openCadence: (item: FollowedSeriesItem) => {
      setCadenceTarget(item);
      setCadenceInterval("");
    },
    dialog: (
      <>
        {dialog}
        {cadenceDialog}
      </>
    ),
  };
}
