/**
 * FileDAcquisitionPanel — merged "File d'acquisition" tab (Phase 03).
 *
 * One stacked flow: grouped wanted searches (§9) followed by live downloads.
 * Stub for sub-phase 3.1 — full implementation in 3.2.
 */

import { type ReactElement } from "react";

/**
 * FileDAcquisitionPanel — the acquisition "File d'acquisition" card.
 *
 * Returns:
 *   The panel element.
 */
export function FileDAcquisitionPanel(): ReactElement {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h3 className="text-sm font-semibold">Recherches</h3>
        <p className="text-xs text-muted-foreground">
          File d&apos;acquisition — merged panel (3.2).
        </p>
      </div>
      <div>
        <h3 className="text-sm font-semibold">Téléchargements</h3>
        <p className="text-xs text-muted-foreground">
          Téléchargements en cours.
        </p>
      </div>
    </div>
  );
}
