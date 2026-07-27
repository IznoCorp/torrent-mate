/**
 * ConflictDialog — the 412 version-conflict dialog for the config editor.
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

/** Props for {@link ConflictDialog}. */
interface ConflictDialogProps {
  /** Dialog visibility. */
  readonly open: boolean;
  /** Dismiss the dialog without reloading. */
  readonly onClose: () => void;
  /** Discard local edits and reload the file at the latest SHA. */
  readonly onReload: () => void;
}

/**
 * ConflictDialog — prompts the operator to reload after a 412 (the file was
 * modified elsewhere since it was loaded).
 *
 * Args:
 *   props: {@link ConflictDialogProps}.
 *
 * Returns:
 *   The dialog element.
 */
export function ConflictDialog({
  open,
  onClose,
  onReload,
}: ConflictDialogProps): ReactElement {
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Conflit de version</DialogTitle>
          <DialogDescription>
            Le fichier a été modifié par ailleurs depuis son chargement.
            Voulez-vous recharger la version actuelle ? Vos modifications
            locales seront perdues.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>
            Annuler
          </Button>
          <Button type="button" onClick={onReload}>
            Recharger
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
