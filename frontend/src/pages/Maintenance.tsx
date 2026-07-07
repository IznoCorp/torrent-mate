/**
 * Maintenance dashboard page (TorrentMateUI S3 — maint-dash).
 *
 * Replaces the former {@link ComingSoon} stub at ``/maintenance``. The page
 * renders a responsive grid of monitoring panels: disks, locks, index health,
 * and run history, plus the {@link ActionCatalog} of maintenance commands with
 * generated run forms.
 */

import { useState, type ReactElement } from "react";

import { ActionCatalog } from "@/components/maintenance/ActionCatalog";
import { DisksPanel } from "@/components/maintenance/DisksPanel";
import { IndexHealthPanel } from "@/components/maintenance/IndexHealthPanel";
import { LocksPanel } from "@/components/maintenance/LocksPanel";
import { RunDetail } from "@/components/pipeline/RunDetail";
import { RunHistoryTable } from "@/components/pipeline/RunHistoryTable";

/**
 * Maintenance — the authenticated maintenance dashboard route (``/maintenance``).
 *
 * Lays out four monitoring panels in a responsive grid (1 col mobile, 2 tablet,
 * 4 desktop) plus the {@link ActionCatalog} of maintenance commands with
 * generated, dry-run-first run forms.
 *
 * Returns:
 *   The maintenance page element.
 */
export default function Maintenance(): ReactElement {
  const [selectedRun, setSelectedRun] = useState<string | null>(null);

  return (
    <section className="mx-auto flex max-w-5xl flex-col gap-4">
      <h1 className="text-xl font-semibold tracking-tight">Maintenance</h1>

      {/* Monitoring panels: 1 col mobile → 2 tablet → 4 desktop */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <DisksPanel />
        <LocksPanel />
        <IndexHealthPanel />
      </div>

      {/* Run-history panel (reuses S2 RunHistoryTable; kind filter chips → 5.2) */}
      <RunHistoryTable onSelect={setSelectedRun} />

      {/* Inline detail view when a history row is selected */}
      {selectedRun !== null && (
        <RunDetail
          runUid={selectedRun}
          onClose={() => {
            setSelectedRun(null);
          }}
        />
      )}

      {/* Action catalog + generated forms (5.2) */}
      <ActionCatalog />
    </section>
  );
}
