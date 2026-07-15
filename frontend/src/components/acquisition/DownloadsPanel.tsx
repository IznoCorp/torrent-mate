/**
 * DownloadsPanel — live progress of grabbed torrents (Phase 5 A4).
 *
 * Polls ``GET /api/acquisition/downloads`` (every 3 s via {@link useDownloads})
 * and renders one row per grabbed torrent: title (+ SxxEyy for episodes), a
 * progress bar, a state badge, and the size. Surfaces the fail-soft
 * ``client_available=false`` as a soft note rather than an empty "no downloads"
 * (which would read as "nothing grabbed").
 */

import { Download } from "lucide-react";
import { type ReactElement } from "react";

import type { AcquisitionDownload } from "@/api/acquisition";
import { EmptyState } from "@/components/ds/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useDownloads } from "@/hooks/useAcquisition";

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

/** One download row: title, progress bar, state badge, size. */
function DownloadRow({ d }: { d: AcquisitionDownload }): ReactElement {
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
            d.state === "missing"
              ? "h-full bg-[var(--danger)]"
              : d.progress >= 1
                ? "h-full bg-[var(--success)]"
                : "h-full bg-[var(--info)]"
          }
          style={{ width: `${String(d.state === "missing" ? 100 : pct)}%` }}
        />
      </div>
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>{d.state === "missing" ? "—" : `${String(pct)} %`}</span>
        {size !== "" && <span>{size}</span>}
      </div>
    </div>
  );
}

/**
 * DownloadsPanel — the acquisition "Téléchargements" card.
 *
 * Returns:
 *   The panel element (skeleton while loading, empty-state when idle).
 */
export function DownloadsPanel(): ReactElement {
  const query = useDownloads();
  const data = query.data;
  const downloads = data?.downloads ?? [];

  // No own Card wrapper: the page already frames the active tab in a Card —
  // nesting a second one read as « des cards dans des cards » (revue mobile
  // 2026-07-15).
  return (
    <div className="flex flex-col gap-4">
      <h3 className="text-sm font-semibold">Téléchargements</h3>
      <div className="flex flex-col gap-4">
        {query.isLoading ? (
          <div className="flex flex-col gap-4" aria-busy="true">
            {Array.from({ length: 2 }).map((_, i) => (
              <Skeleton key={`dl-sk-${String(i)}`} className="h-12 w-full" />
            ))}
          </div>
        ) : downloads.length === 0 ? (
          <EmptyState
            icon={Download}
            title="Aucun téléchargement en cours"
            description="Les torrents récupérés s'affichent ici jusqu'à leur rangement en médiathèque."
          />
        ) : (
          <>
            {data?.client_available === false && (
              <p className="text-xs text-[var(--warning)]">
                Client torrent injoignable — progression indisponible, les
                éléments récupérés restent listés.
              </p>
            )}
            {downloads.map((d) => (
              <DownloadRow key={d.info_hash || downloadTitle(d)} d={d} />
            ))}
          </>
        )}
      </div>
    </div>
  );
}
