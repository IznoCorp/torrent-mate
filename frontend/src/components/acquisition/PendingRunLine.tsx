/**
 * PendingRunLine — what the watcher is waiting for, in one sentence (§8/DOIT-2).
 *
 * The watcher is a separate process: without this line the screen looks the
 * same whether it is biding its time or dead, and a silent wait reads as an
 * outage — the founding post-mortem's original sin. Two situations, two
 * sentences, and NOTHING when the daemon has published nothing: we do not
 * narrate a wait we do not know.
 *
 * Extracted unchanged from the dissolved « Vue d'ensemble »; its home is now
 * « Maintenant », above the sections, where a wait is part of « what is
 * happening right now ».
 */

import { useEffect, useState, type ReactElement } from "react";

/** Props for {@link PendingRunLine}. */
export interface PendingRunLineProps {
  readonly pending:
    | {
        fires_at?: number | null;
        active_downloads?: number;
        updated_at: number;
      }
    | null
    | undefined;
}

/**
 * Render the watcher-wait line, or nothing when no wait is published.
 *
 * Args:
 *   props: See {@link PendingRunLineProps}.
 *
 * Returns:
 *   The explanation line, or null.
 */
export function PendingRunLine({ pending }: PendingRunLineProps): ReactElement | null {
  // The countdown must LIVE: a deadline frozen at render time would age in
  // silence until the next query refresh.
  const [now, setNow] = useState(() => Date.now() / 1000);
  useEffect(() => {
    const id = setInterval(() => {
      setNow(Date.now() / 1000);
    }, 1000);
    return () => {
      clearInterval(id);
    };
  }, []);

  if (pending == null) return null;
  const actifs = pending.active_downloads ?? 0;
  if (actifs > 0) {
    return (
      <p data-testid="pending-run-line" className="text-xs text-muted-foreground">
        {actifs} téléchargement{actifs > 1 ? "s" : ""} en cours · l&apos;ingestion
        démarrera une fois le dernier terminé
      </p>
    );
  }
  if (pending.fires_at != null) {
    const restant = Math.max(0, Math.round(pending.fires_at - now));
    return (
      <p data-testid="pending-run-line" className="text-xs text-muted-foreground">
        Ingestion dans {restant} s · toute nouvelle arrivée relance le délai
      </p>
    );
  }
  return null;
}
