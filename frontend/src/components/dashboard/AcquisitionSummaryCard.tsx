/**
 * AcquisitionSummaryCard — the dashboard's acquisitions glance (A3, §5).
 *
 * One {@link StatPanel} tile: pending wanted episodes, live downloads in
 * progress, and torrents the watcher currently defers (transient ingest
 * skips) — each with a link into the Acquisition page. Read-only + fail-soft:
 * a probe error degrades to em-dashes, never blocks the dashboard.
 */

import type { ReactElement } from "react";
import { Link } from "react-router-dom";

import { StatPanel } from "@/components/ds/StatPanel";
import {
  useAcquisitionStatus,
  useDownloads,
  useWanted,
} from "@/hooks/useAcquisition";

/** Format a count cell, degrading to an em-dash on absent data. */
function cell(value: number | undefined): string {
  return value === undefined ? "—" : String(value);
}

/**
 * AcquisitionSummaryCard — pending / downloading / deferred counters.
 *
 * Returns:
 *   The acquisitions summary card element.
 */
export function AcquisitionSummaryCard(): ReactElement {
  const wanted = useWanted({ status: "pending", page_size: 1 });
  const downloads = useDownloads();
  const status = useAcquisitionStatus();

  // Runtime-total guards: an auth-expiry or degraded payload can momentarily
  // put a non-contract body in the cache (router B4 flow) — a dashboard tile
  // must degrade to em-dashes, never crash the route.
  const rawDownloads: unknown = downloads.data?.downloads;
  const rawDeferred: unknown = status.data?.deferred;

  const pendingCount =
    typeof wanted.data?.total === "number" ? wanted.data.total : undefined;
  const activeDownloads = Array.isArray(rawDownloads)
    ? (rawDownloads as { state: string; progress: number }[]).filter(
        (d) => d.state !== "missing" && d.progress < 1,
      ).length
    : undefined;
  const deferredCount = Array.isArray(rawDeferred)
    ? rawDeferred.length
    : undefined;

  return (
    <StatPanel
      label="Acquisitions"
      value={
        <div className="flex flex-col gap-1 text-sm font-normal">
          <span>
            {cell(pendingCount)} épisode{(pendingCount ?? 0) > 1 ? "s" : ""} en
            attente
          </span>
          <span>
            {cell(activeDownloads)} téléchargement
            {(activeDownloads ?? 0) > 1 ? "s" : ""} en cours
          </span>
          {(deferredCount ?? 0) > 0 && (
            <span className="text-warning">
              {cell(deferredCount)} torrent{(deferredCount ?? 0) > 1 ? "s" : ""}{" "}
              différé{(deferredCount ?? 0) > 1 ? "s" : ""}
            </span>
          )}
          <Link
            to="/acquisition"
            className="text-xs text-muted-foreground underline-offset-2 hover:underline"
          >
            Ouvrir les acquisitions →
          </Link>
        </div>
      }
    />
  );
}
