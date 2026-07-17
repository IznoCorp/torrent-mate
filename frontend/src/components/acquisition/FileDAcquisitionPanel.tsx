/**
 * FileDAcquisitionPanel — merged "File d'acquisition" tab (Phase 03).
 *
 * One stacked flow (§9 — wanted → grabbed → ingest): grouped wanted searches
 * (status filter + accordion per series/season, DOIT-2 FR reasons) followed by
 * live downloads with the fail-soft « client torrent injoignable » notice
 * (NE-DOIT-PAS-1/5).
 *
 * WantedPanel + DownloadsPanel are kept in the tree (not deleted); this panel
 * replaces both on the page. DownloadRow is imported from DownloadsPanel.
 */

import { useMemo, useState, type ReactElement } from "react";

import type { WantedItem } from "@/api/acquisition";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useDownloads, useWanted } from "@/hooks/useAcquisition";

import { DownloadRow } from "./DownloadsPanel";
import {
  STATUS_LABEL,
  STATUS_TONE,
  WANTED_STATUS_OPTIONS,
  type WantedFilter,
} from "./meta";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** A series-season grouping keyed by title then season number. */
interface SeriesGroup {
  title: string;
  seasons: SeasonGroup[];
}

interface SeasonGroup {
  season: number | null;
  episodes: WantedItem[];
}

/** Group a flat wanted-item list by title → season. */
function groupByTitleSeason(items: WantedItem[]): SeriesGroup[] {
  const byTitle = new Map<string, Map<number | null, WantedItem[]>>();
  for (const item of items) {
    if (!byTitle.has(item.title)) {
      byTitle.set(item.title, new Map());
    }
    const bySeason = byTitle.get(item.title)!;
    const key = item.season ?? null;
    if (!bySeason.has(key)) {
      bySeason.set(key, []);
    }
    bySeason.get(key)!.push(item);
  }

  const result: SeriesGroup[] = [];
  for (const [title, seasonMap] of byTitle) {
    const seasons: SeasonGroup[] = [];
    // Sort seasons numerically (null/"specials" last).
    const sortedKeys = [...seasonMap.keys()].sort((a, b) => {
      if (a === null) return 1;
      if (b === null) return -1;
      return a - b;
    });
    for (const season of sortedKeys) {
      seasons.push({ season, episodes: seasonMap.get(season) ?? [] });
    }
    result.push({ title, seasons });
  }
  // Sort series by title.
  result.sort((a, b) => a.title.localeCompare(b.title, "fr"));
  return result;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * FileDAcquisitionPanel — the acquisition "File d'acquisition" card.
 *
 * Returns:
 *   The panel element.
 */
export function FileDAcquisitionPanel(): ReactElement {
  // ---- Wanted (Recherches) section state -----------------------------------
  const [status, setStatus] = useState<WantedFilter>("all");
  const [page, setPage] = useState(1);
  const pageSize = 50;

  const wantedQuery = useWanted({
    ...(status !== "all" ? { status } : {}),
    page,
    page_size: pageSize,
  });

  const wantedItems = wantedQuery.data?.items ?? [];
  const totalItems = wantedQuery.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
  const grouped = useMemo(
    () => groupByTitleSeason(wantedQuery.data?.items ?? []),
    [wantedQuery.data?.items],
  );

  // ---- Downloads section state ---------------------------------------------
  const downloadsQuery = useDownloads();
  const downloadsData = downloadsQuery.data;
  const downloads = downloadsData?.downloads ?? [];
  const clientAvailable = downloadsData?.client_available ?? true;

  return (
    <div className="flex flex-col gap-8">
      {/* ================================================================ */}
      {/* Recherches section                                               */}
      {/* ================================================================ */}
      <section>
        <h3 className="mb-3 text-sm font-semibold">Recherches</h3>

        {/* Status filter + pagination header */}
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Label className="text-xs">Statut :</Label>
            <Select
              value={status}
              onValueChange={(v) => {
                setStatus(v as WantedFilter);
                setPage(1);
              }}
            >
              <SelectTrigger className="w-36">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {WANTED_STATUS_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <span className="text-xs text-muted-foreground">
            Page {String(page)} / {String(totalPages)} ({String(totalItems)}{" "}
            résultats)
          </span>
        </div>

        {/* ---- Wanted loading ------------------------------------------ */}
        {wantedQuery.isLoading && (
          <div className="space-y-3" aria-busy="true">
            {Array.from({ length: 5 }).map((_, idx) => (
              <Skeleton key={`sk-w-${String(idx)}`} className="h-10 w-full" />
            ))}
          </div>
        )}

        {/* ---- Wanted error -------------------------------------------- */}
        {wantedQuery.isError && (
          <p className="py-4 text-muted-foreground">
            Erreur de chargement :{" "}
            {wantedQuery.error instanceof Error
              ? wantedQuery.error.message
              : "Inconnue"}
          </p>
        )}

        {/* ---- Wanted empty -------------------------------------------- */}
        {!wantedQuery.isLoading &&
          !wantedQuery.isError &&
          wantedItems.length === 0 && (
            <div className="py-8 text-center">
              <p className="text-muted-foreground">
                {status === "all"
                  ? "Aucune recherche en file. Suivez des séries pour remplir cette liste."
                  : `Aucune recherche avec le statut « ${STATUS_LABEL[status] ?? status} ».`}
              </p>
            </div>
          )}

        {/* ---- Grouped series accordion --------------------------------- */}
        {!wantedQuery.isLoading &&
          !wantedQuery.isError &&
          wantedItems.length > 0 && (
            <>
              <Accordion className="rounded-md border">
                {grouped.map((series) => {
                  const episodeCount = series.seasons.reduce(
                    (s, sg) => s + sg.episodes.length,
                    0,
                  );
                  const seasonCount = series.seasons.length;

                  return (
                    <AccordionItem key={series.title} className="border-border">
                      <AccordionTrigger>
                        <span className="flex items-center gap-2">
                          <span className="font-medium">{series.title}</span>
                          <span className="text-xs text-muted-foreground">
                            ({String(seasonCount)} saison
                            {seasonCount > 1 ? "s" : ""}, {String(episodeCount)}{" "}
                            épisode
                            {episodeCount > 1 ? "s" : ""})
                          </span>
                        </span>
                      </AccordionTrigger>
                      <AccordionContent>
                        <div className="space-y-3 px-1">
                          {series.seasons.map((sg) => (
                            <div
                              key={`${series.title}-S${String(sg.season ?? "?")}`}
                            >
                              <h4 className="mb-1 text-xs font-semibold text-muted-foreground">
                                Saison{" "}
                                {sg.season != null
                                  ? String(sg.season).padStart(2, "0")
                                  : "?"}{" "}
                                ({String(sg.episodes.length)} épisode
                                {sg.episodes.length > 1 ? "s" : ""})
                              </h4>
                              <div className="space-y-1">
                                {sg.episodes.map((ep) => (
                                  <div
                                    key={`ep-${String(ep.id)}`}
                                    className="flex items-center justify-between gap-2 rounded px-2 py-1 text-sm hover:bg-muted/50"
                                  >
                                    <span className="min-w-0 truncate">
                                      {ep.episode != null
                                        ? `S${String(ep.season ?? "?").padStart(2, "0")}E${String(ep.episode).padStart(2, "0")}`
                                        : ep.kind}
                                    </span>
                                    <span className="flex shrink-0 items-center gap-2">
                                      <span className="text-xs text-muted-foreground">
                                        {ep.attempts > 0
                                          ? `${String(ep.attempts)} tentative${ep.attempts > 1 ? "s" : ""}`
                                          : ""}
                                      </span>
                                      <Badge
                                        tone={
                                          STATUS_TONE[ep.status] ?? "neutral"
                                        }
                                      >
                                        {STATUS_LABEL[ep.status] ?? ep.status}
                                      </Badge>
                                    </span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>
                      </AccordionContent>
                    </AccordionItem>
                  );
                })}
              </Accordion>

              {/* Pagination */}
              <div className="mt-3 flex items-center justify-between">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => {
                    setPage((p) => Math.max(1, p - 1));
                  }}
                >
                  ← Précédent
                </Button>
                <span className="text-xs text-muted-foreground">
                  Page {String(page)} / {String(totalPages)}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => {
                    setPage((p) => p + 1);
                  }}
                >
                  Suivant →
                </Button>
              </div>
            </>
          )}
      </section>

      {/* ================================================================ */}
      {/* Téléchargements section                                          */}
      {/* ================================================================ */}
      <section>
        <h3 className="mb-3 text-sm font-semibold">Téléchargements</h3>

        {downloadsQuery.isLoading && (
          <div className="flex flex-col gap-4" aria-busy="true">
            {Array.from({ length: 2 }).map((_, i) => (
              <Skeleton key={`dl-sk-${String(i)}`} className="h-12 w-full" />
            ))}
          </div>
        )}

        {!downloadsQuery.isLoading && downloads.length === 0 && (
          <div className="py-8 text-center">
            <p className="text-muted-foreground">
              Aucun téléchargement en cours. Les torrents récupérés
              s&apos;affichent ici jusqu&apos;à leur rangement en médiathèque.
            </p>
          </div>
        )}

        {!downloadsQuery.isLoading && downloads.length > 0 && (
          <>
            {/* Fail-soft notice — never a calm empty lie
                (NE-DOIT-PAS-1/5) */}
            {!clientAvailable && (
              <p className="mb-3 text-xs text-[var(--warning)]">
                Client torrent injoignable — progression indisponible, les
                éléments récupérés restent listés.
              </p>
            )}
            <div className="flex flex-col gap-4">
              {downloads.map((d) => (
                <DownloadRow key={d.info_hash || d.name} d={d} />
              ))}
            </div>
          </>
        )}
      </section>
    </div>
  );
}
