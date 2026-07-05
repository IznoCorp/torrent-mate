/**
 * InstallBanner — proposes installing the PWA (tm-shell §5.4).
 *
 * A dismissible bottom banner, mobile-first, on the DS card surface. Two paths:
 *
 * - **Android / desktop** — when the native install prompt was captured
 *   ({@link PwaState.canInstall}), an « Installer TorrentMate » button triggers
 *   {@link PwaState.promptInstall}.
 * - **iOS Safari** — no `beforeinstallprompt` exists, so
 *   ({@link PwaState.isIosInstall}) the banner shows the manual
 *   *Partager → « Sur l'écran d'accueil »* instruction instead.
 *
 * The banner hides itself when the app is already installed or the user
 * dismissed it (both folded into `canInstall` / `isIosInstall` by `usePwa`), and
 * the close button remembers the dismissal via {@link PwaState.dismissInstall}.
 */

import { Download, Share, X } from "lucide-react";
import type { ReactElement } from "react";

import { Button } from "@/components/ui/button";
import type { PwaState } from "@/hooks/usePwa";

/**
 * Render the install proposal banner, or nothing when it does not apply.
 *
 * Args:
 *   state: The shared PWA state (install-related fields are read).
 *
 * Returns:
 *   The banner element, or ``null`` when neither install path is available.
 */
export function InstallBanner({
  state,
}: {
  state: PwaState;
}): ReactElement | null {
  const { canInstall, promptInstall, isIosInstall, dismissInstall } = state;

  if (!canInstall && !isIosInstall) {
    return null;
  }

  return (
    <div
      role="region"
      aria-label="Installer TorrentMate"
      className="fixed inset-x-0 bottom-0 z-50 flex justify-center p-4"
    >
      <div className="flex w-full max-w-md items-center gap-3 rounded-lg border border-border bg-card p-4 shadow-lg">
        <div className="flex flex-1 flex-col gap-1">
          <p className="text-sm font-medium text-foreground">
            Installer l’application
          </p>
          {canInstall ? (
            <p className="text-xs text-muted-foreground">
              Ajoutez TorrentMate à votre écran d’accueil pour un accès direct.
            </p>
          ) : (
            <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Share className="size-4 shrink-0" aria-hidden="true" />
              <span>
                Appuyez sur Partager, puis « Sur l’écran d’accueil ».
              </span>
            </p>
          )}
        </div>

        {canInstall && (
          <Button size="sm" onClick={() => void promptInstall()}>
            <Download aria-hidden="true" />
            Installer TorrentMate
          </Button>
        )}

        <Button
          variant="ghost"
          size="icon"
          aria-label="Ignorer"
          onClick={dismissInstall}
        >
          <X aria-hidden="true" />
        </Button>
      </div>
    </div>
  );
}
