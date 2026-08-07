/**
 * DownloadRow — one live download: title (+ SxxEyy), progress, state, size.
 *
 * Extracted from the superseded downloads panel so the row — the part the
 * mounted « En vol » section needs — no longer lives inside dead code. A
 * broken torrent names its reason in French: a stalled download that only says
 * « en cours » is the silence §8 exists to end.
 */

import { type ReactElement } from "react";

import type { AcquisitionDownload } from "@/api/acquisition";
import { Badge } from "@/components/ui/badge";

import { DOWNLOAD_STATE_LABEL, DOWNLOAD_STATE_TONE } from "./meta";

/** Zero-pad a season/episode number to two digits. */
function pad2(n: number): string {
  return n.toString().padStart(2, "0");
}

/** Human title for a download row: film title, or "Title SxxEyy" for episodes. */
function downloadTitle(d: AcquisitionDownload): string {
  if (d.kind === "episode" && d.season != null && d.episode != null) {
    return `${d.title} S${pad2(d.season)}E${pad2(d.episode)}`;
  }
  return d.title || d.name || d.info_hash.slice(0, 12);
}

/** Format a byte count as a compact GB/MB string. */
function formatSize(bytes: number): string {
  if (bytes <= 0) return "";
  const gb = bytes / 1e9;
  if (gb >= 1) return `${gb.toFixed(1)} Go`;
  return `${String(Math.round(bytes / 1e6))} Mo`;
}

/**
 * One download row: title, progress bar, state badge, size.
 *
 * Exported for reuse by FileDAcquisitionPanel (the superseding merged panel).
 */
export function DownloadRow({ d }: { d: AcquisitionDownload }): ReactElement {
  const pct = Math.round(d.progress * 100);
  const tone = DOWNLOAD_STATE_TONE[d.state] ?? "neutral";
  const label = DOWNLOAD_STATE_LABEL[d.state] ?? d.state;
  const size = formatSize(d.size_bytes);
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-sm font-medium" title={downloadTitle(d)}>
          {downloadTitle(d)}
        </span>
        <Badge tone={tone} className="shrink-0">
          {label}
        </Badge>
      </div>
      <div
        className="h-2 w-full overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${downloadTitle(d)} — ${String(pct)}%`}
      >
        <div
          className={
            d.state === "missing" || d.state === "errored"
              ? "h-full bg-danger"
              : d.progress >= 1
                ? "h-full bg-success"
                : "h-full bg-info"
          }
          style={{
            width: `${String(d.state === "missing" || d.state === "errored" ? 100 : pct)}%`,
          }}
        />
      </div>
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>
          {d.state === "missing" || d.state === "errored"
            ? "—"
            : `${String(pct)} %`}
        </span>
        {size !== "" && <span>{size}</span>}
      </div>
      {/* §8 — a broken torrent shows WHY, not a bare state. */}
      {d.state === "errored" &&
        d.error_reason != null &&
        d.error_reason !== "" && (
          <p className="text-xs text-danger">{d.error_reason}</p>
        )}
    </div>
  );
}
