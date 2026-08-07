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
import { useUnfollow, useUpdateFollow } from "@/hooks/useAcquisition";

import type { SwipeAction } from "./SwipeActions";
import { actionWords, asMediaKind, followMediaRef } from "./meta";

/** What {@link useFollowActions} hands a panel. */
export interface FollowActions {
  /** Swipe actions for one follow — suspend/resume then remove (§9's 84 px pair). */
  readonly swipeFor: (item: FollowedSeriesItem) => readonly SwipeAction[];
  /** The « ··· » kebab for one follow — rendered by the card on fine pointers only (A11). */
  readonly menuFor: (item: FollowedSeriesItem) => ReactElement;
  /** The shared removal-confirmation dialog — render ONCE per panel. */
  readonly dialog: ReactElement;
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

  const swipeFor = (item: FollowedSeriesItem): readonly SwipeAction[] => {
    const w = words(item);
    const paused = item.status === "disabled";
    return [
      {
        key: "suspend",
        label: paused ? w.resumeShort : w.pauseShort,
        icon: null,
        tone: "neutral",
        onRun: () => {
          suspendOrResume(item);
        },
      },
      {
        key: "remove",
        label: "Retirer",
        icon: null,
        tone: "danger",
        onRun: () => {
          setRemoving(item);
        },
      },
    ];
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
    dialog: (
      <>
        {dialog}
        {cadenceDialog}
      </>
    ),
  };
}
