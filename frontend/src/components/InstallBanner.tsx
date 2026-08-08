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

import { aboveBottomBar } from "@/components/layout/bottom-bar-metrics";
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
      className="fixed inset-x-0 z-50 flex justify-center p-4"
      // Above the bottom navigation bar: anchored at bottom-0 the close
      // button sat UNDER the fixed bar — unreachable on both platforms
      // (operator report: « impossible de fermer »).
      style={{ bottom: aboveBottomBar("0rem") }}
    >
      <div className="flex w-full max-w-md items-start gap-3 rounded-lg border border-border bg-card p-4 shadow-lg">
        <div className="flex flex-1 flex-col gap-1">
          <p className="text-sm font-medium text-foreground">
            Installer l’application
          </p>
          {canInstall ? (
            <p className="text-xs text-muted-foreground">
              Ajoutez TorrentMate à votre écran d’accueil pour un accès direct.
            </p>
          ) : (
            // iOS has no install prompt — the banner IS the guide, so it
            // walks the actual steps (operator ask), not a one-liner.
            <ol className="flex list-decimal flex-col gap-1 pl-4 text-xs text-muted-foreground">
              <li>Ouvrez cette page dans Safari.</li>
              <li className="flex-wrap">
                Touchez{" "}
                <span className="inline-flex items-center gap-1 font-medium text-foreground">
                  <Share className="size-3.5 shrink-0" aria-hidden="true" />
                  Partager
                </span>{" "}
                dans la barre du bas.
              </li>
              <li>
                Choisissez «&nbsp;Sur l’écran d’accueil&nbsp;», puis
                «&nbsp;Ajouter&nbsp;».
              </li>
            </ol>
          )}

          {canInstall && (
            <Button
              size="sm"
              className="mt-2 self-start"
              onClick={() => void promptInstall()}
            >
              <Download aria-hidden="true" />
              Installer TorrentMate
            </Button>
          )}
        </div>

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
