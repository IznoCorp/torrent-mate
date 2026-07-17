/**
 * IgnoreDiscardButton — « Ignorer / nettoyer » pour les artefacts non-média (§7).
 *
 * Bouton danger-outline dans le détail d'un item staging dont le type est
 * ``"other"`` (ni film ni série identifiable).  Ouvre une Dialog de confirmation
 * explicite en français, puis appelle la mutation :func:`discardMedia`.  En cas
 * de succès le toast affiche le ``detail`` serveur tel quel (inclut le préfixe
 * ATTENTION quand l'écriture du journal a échoué).
 */

import { useState, type ReactElement } from "react";
import { toast } from "sonner";

import { useDiscardMedia } from "@/hooks/useDiscardMedia";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

/** Props for {@link IgnoreDiscardButton}. */
export interface IgnoreDiscardButtonProps {
  /** The staged media id to discard (``POST /api/staging/media/{id}/discard``). */
  readonly mediaId: string;
  /** Invoked after a successful discard so the parent can close the sheet etc. */
  readonly onSuccess?: () => void;
}

/**
 * Render a danger-outline button that, after explicit confirmation, discards a
 * non-media staging artifact.
 *
 * Args:
 *   mediaId: The staging media id.
 *   onSuccess: Optional callback invoked on successful discard.
 *
 * Returns:
 *   The button + confirmation dialog element.
 */
export function IgnoreDiscardButton({
  mediaId,
  onSuccess,
}: IgnoreDiscardButtonProps): ReactElement {
  const [open, setOpen] = useState(false);
  const discardMut = useDiscardMedia();

  return (
    <>
      <Button
        type="button"
        variant="outline"
        className="border-danger text-danger hover:bg-danger/10"
        onClick={() => {
          setOpen(true);
        }}
      >
        Ignorer / nettoyer
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Ignorer cet élément&nbsp;?</DialogTitle>
            <DialogDescription>
              Ce dossier ne contient pas un média identifiable. Il sera déplacé
              vers la quarantaine et une entrée sera écrite dans le journal des
              opérations destructives. Cette action est irréversible.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              type="button"
              onClick={() => {
                setOpen(false);
              }}
            >
              Annuler
            </Button>
            <Button
              type="button"
              variant="destructive"
              disabled={discardMut.isPending}
              onClick={() => {
                discardMut.mutate(mediaId, {
                  onSuccess: (data) => {
                    // §7 — render the server detail verbatim.  When journaled is
                    // false the destructive-op row could not be written — surface
                    // it as a warning (danger-tinted) so the operator can inspect
                    // the filesystem.
                    if (!data.journaled) {
                      toast.warning(data.detail);
                    } else {
                      toast.success(data.detail);
                    }
                    setOpen(false);
                    onSuccess?.();
                  },
                  onError: (err: unknown) => {
                    toast.error(
                      err instanceof Error ? err.message : "Échec du nettoyage",
                    );
                  },
                });
              }}
            >
              {discardMut.isPending ? "Nettoyage…" : "Confirmer le nettoyage"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
