/**
 * WantedPanel — the "Recherches" tab: the wanted-search queue with a status
 * filter, a paginated table and per-row status badges.
 *
 * Extracted from `AcquisitionPage.tsx` (C12). Superseded — kept in the tree
 * but no longer mounted. Replaced by FileDAcquisitionPanel (Phase 03).
 */

import { useState, type ReactElement } from "react";

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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useWanted } from "@/hooks/useAcquisition";

import {
  relativeTime,
  STATUS_LABEL,
  STATUS_TONE,
  WANTED_STATUS_OPTIONS,
  type WantedFilter,
} from "./meta";

/**
 * WantedPanel — the paginated wanted-search queue.
 *
 * Returns:
 *   The wanted panel element.
 */
export function WantedPanel(): ReactElement {
  const [status, setStatus] = useState<WantedFilter>("all");
  const [page, setPage] = useState(1);
  const pageSize = 50;

  const { data, isLoading, isError, error } = useWanted({
    ...(status !== "all" ? { status } : {}),
    page,
    page_size: pageSize,
  });

  const items = data?.items ?? [];
  const totalItems = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));

  // ── Loading ────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, idx) => (
          <Skeleton key={`sk-w-${String(idx)}`} className="h-10 w-full" />
        ))}
      </div>
    );
  }

  // ── Error ──────────────────────────────────────────────────────────────
  if (isError) {
    return (
      <p className="py-4 text-muted-foreground">
        Erreur de chargement :{" "}
        {error instanceof Error ? error.message : "Inconnue"}
      </p>
    );
  }

  // ── Normal ─────────────────────────────────────────────────────────────
  // The status filter stays visible even when the current filter is empty, so
  // the operator can always switch filters (UX: no dead-end empty view).
  return (
    <div className="space-y-3">
      {/* Status filter + pagination info */}
      <div className="flex flex-wrap items-center justify-between gap-2">
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

      {items.length === 0 ? (
        <div className="py-8 text-center">
          <p className="text-muted-foreground">
            {status === "all"
              ? "Aucune recherche en file. Suivez des séries pour remplir cette liste."
              : `Aucune recherche avec le statut « ${STATUS_LABEL[status] ?? status} ».`}
          </p>
        </div>
      ) : (
        <>
          {/* Table */}
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Titre</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Saison</TableHead>
                <TableHead>Épisode</TableHead>
                <TableHead>Statut</TableHead>
                <TableHead>Tentatives</TableHead>
                <TableHead>Ajouté</TableHead>
                <TableHead>Dernière recherche</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow key={`w-${String(item.id)}`}>
                  <TableCell className="font-medium">{item.title}</TableCell>
                  <TableCell className="text-xs">{item.kind}</TableCell>
                  <TableCell className="font-mono text-xs">
                    {item.season ?? "—"}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {item.episode ?? "—"}
                  </TableCell>
                  <TableCell>
                    <Badge tone={STATUS_TONE[item.status] ?? "neutral"}>
                      {STATUS_LABEL[item.status] ?? item.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {item.attempts}
                  </TableCell>
                  <TableCell className="text-xs">
                    {relativeTime(item.enqueued_at)}
                  </TableCell>
                  <TableCell className="text-xs">
                    {relativeTime(item.last_search_at)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          {/* Pagination */}
          <div className="flex items-center justify-between">
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
    </div>
  );
}
