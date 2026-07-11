import type { ReactElement } from "react";

import type { StagingMediaItem } from "@/api/client";
import { MediaPoster } from "@/components/ds/MediaPoster";
import { StatusBadge } from "@/components/ds/StatusBadge";
import { MediaTimeline } from "@/components/staging/MediaTimeline";
import {
  dispatchLabel,
  formatSize,
  kindLabel,
  matchBadge,
  posterKind,
} from "@/components/staging/meta";
import { Button } from "@/components/ui/button";

/** Props for {@link StagingMediaDetail}. */
export interface StagingMediaDetailProps {
  /** The staged media to detail. */
  readonly item: StagingMediaItem;
  /** Invoked when the operator asks to resolve an ambiguous match (opens the deck). */
  readonly onResolve?: () => void;
}

/** One labelled provider-id chip (tvdb / tmdb / imdb). */
function IdChip({ family, id }: { family: string; id: string }): ReactElement {
  return (
    <span className="inline-flex items-center gap-1 rounded border border-border px-1.5 py-0.5 text-xs">
      <span className="uppercase text-muted-foreground">{family}</span>
      <span className="font-mono tabular-nums">{id}</span>
    </span>
  );
}

/** One labelled meta cell (label over value). */
function MetaCell({ label, value }: { label: string; value: string }): ReactElement {
  return (
    <div className="flex flex-col">
      <span className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      <span className="text-sm">{value}</span>
    </div>
  );
}

/**
 * StagingMediaDetail — the drawer body for one staged media.
 *
 * Poster + title/year, matching verdict, provider ids, overview, season
 * breakdown, on-disk facts, the optional dispatch-target preview, and the
 * per-media pipeline {@link MediaTimeline}. When the media is awaiting a
 * matching decision it offers a jump to the resolution deck.
 *
 * Args:
 *   item: The staged media read-model item.
 *   onResolve: Optional handler to open the resolution deck for an ambiguous item.
 *
 * Returns:
 *   The detail element.
 */
export function StagingMediaDetail({
  item,
  onResolve,
}: StagingMediaDetailProps): ReactElement {
  const badge = matchBadge(item.match);
  const kind = posterKind(item.media_kind);
  const dispatch = item.dispatch_target;

  return (
    <div className="flex flex-col gap-4">
      {/* Hero: poster + identity. */}
      <div className="flex gap-4">
        <div className="w-28 shrink-0">
          <MediaPoster
            title={item.title}
            src={item.poster_url ?? null}
            {...(kind !== undefined ? { kind } : {})}
          />
        </div>
        <div className="flex min-w-0 flex-col gap-2">
          <div className="flex items-baseline gap-2">
            <h3 className="text-lg font-semibold leading-tight">{item.title}</h3>
            {item.year != null && (
              <span className="shrink-0 font-mono text-sm tabular-nums text-muted-foreground">
                {item.year}
              </span>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge tone={badge.tone} label={badge.label} />
            <span className="text-xs text-muted-foreground">{kindLabel(item.media_kind)}</span>
          </div>
          {Object.keys(item.provider_ids).length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(item.provider_ids).map(([family, id]) => (
                <IdChip key={family} family={family} id={id} />
              ))}
            </div>
          )}
        </div>
      </div>

      {item.overview != null && item.overview !== "" && (
        <p className="text-sm text-muted-foreground">{item.overview}</p>
      )}

      {/* On-disk facts. */}
      <div className="grid grid-cols-3 gap-3">
        <MetaCell label="Catégorie" value={item.category} />
        <MetaCell label="Taille" value={formatSize(item.size_bytes)} />
        <MetaCell
          label="Vidéos"
          value={item.video_count > 0 ? String(item.video_count) : "—"}
        />
      </div>

      {/* Seasons (TV shows only). */}
      {item.seasons != null && item.seasons.length > 0 && (
        <div className="flex flex-col gap-1">
          <span className="text-xs uppercase tracking-wide text-muted-foreground">
            Saisons
          </span>
          <ul className="flex flex-col gap-0.5 text-sm">
            {item.seasons.map((s) => (
              <li key={s.season} className="flex justify-between gap-2">
                <span>{s.label}</span>
                <span className="text-muted-foreground">
                  {s.episode_count} épisode{s.episode_count > 1 ? "s" : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Dispatch-target preview (only present when requested). */}
      {dispatch != null && (
        <div className="rounded-md border border-border p-3 text-sm">
          <div className="flex items-center justify-between gap-2">
            <span className="font-medium">Dispatch prévu</span>
            <span className="text-muted-foreground">
              {dispatchLabel(dispatch.mode)}
              {dispatch.disk != null ? ` → ${dispatch.disk}` : ""}
            </span>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">{dispatch.reason}</p>
        </div>
      )}

      {/* Per-media pipeline timeline. */}
      <div className="flex flex-col gap-2">
        <span className="text-xs uppercase tracking-wide text-muted-foreground">
          Parcours pipeline
        </span>
        <MediaTimeline stages={item.stages} />
      </div>

      {/* Resolution jump for an ambiguous match. */}
      {item.match === "ambiguous" && onResolve !== undefined && (
        <Button type="button" onClick={onResolve}>
          Résoudre le matching
        </Button>
      )}
    </div>
  );
}
