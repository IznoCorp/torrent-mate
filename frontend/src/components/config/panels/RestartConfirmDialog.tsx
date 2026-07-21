/**
 * RestartConfirmDialog — confirmation dialog before triggering a web restart.
 */

import { type ReactElement } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

/** Props for {@link RestartConfirmDialog}. */
interface RestartConfirmDialogProps {
  /** Dialog visibility. */
  readonly open: boolean;
  /** Dismiss the dialog without restarting. */
  readonly onClose: () => void;
  /** Confirm the restart. */
  readonly onConfirm: () => void;
}

/**
 * RestartConfirmDialog — confirms the destructive PM2 restart (the connection
 * drops then re-establishes).
 *
 * Args:
 *   props: {@link RestartConfirmDialogProps}.
 *
 * Returns:
 *   The dialog element.
 */
export function RestartConfirmDialog({
  open,
  onClose,
  onConfirm,
}: RestartConfirmDialogProps): ReactElement {
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Redémarrer le daemon ?</DialogTitle>
          <DialogDescription>
            Cette action va redémarrer le processus web via PM2. La connexion
            va se couper puis se rétablir.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>
            Annuler
          </Button>
          <Button type="button" variant="destructive" onClick={onConfirm}>
            Redémarrer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
