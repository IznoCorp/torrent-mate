/**
 * ObligationsPanel — the "Obligations" tab: seed-obligation rows (ratio, seed
 * time, HnR) with a server-side status filter.
 *
 * Extracted from `AcquisitionPage.tsx` (C12). Behaviour unchanged.
 */

import { useState, type ReactElement } from "react";

import { Badge } from "@/components/ui/badge";
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
import { useObligations } from "@/hooks/useAcquisition";

import {
  obligationStatus,
  OBLIGATION_STATUS_OPTIONS,
  STATUS_LABEL,
  STATUS_TONE,
  truncate,
  type ObligationFilter,
} from "./meta";

/**
 * ObligationsPanel — the seed-obligation table.
 *
 * Returns:
 *   The obligations panel element.
 */
export function ObligationsPanel(): ReactElement {
  const [status, setStatus] = useState<ObligationFilter>("all");

  const { data, isLoading, isError, error } = useObligations(
    status !== "all" ? { status } : {},
  );

  // Trust the SERVER filter (the route already filters by status) — do NOT
  // re-filter client-side: a row with both satisfied_at and breached_at set is
  // classified "breached" by the server but "satisfied" by obligationStatus(),
  // so a client re-filter would silently drop it (adversarial-review finding).
  // obligationStatus() stays in use only for the per-row status BADGE.
  const items = data?.items ?? [];

  // ── Loading ────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, idx) => (
          <Skeleton key={`sk-o-${String(idx)}`} className="h-10 w-full" />
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

  // ── Empty ──────────────────────────────────────────────────────────────
  if (items.length === 0) {
    return (
      <div className="py-8 text-center">
        <p className="text-muted-foreground">
          {status === "all"
            ? "Aucune obligation de seed enregistrée."
            : `Aucune obligation avec le statut « ${STATUS_LABEL[status] ?? status} ».`}
        </p>
      </div>
    );
  }

  // ── Normal ─────────────────────────────────────────────────────────────
  return (
    <div className="space-y-3">
      {/* Status filter */}
      <div className="flex items-center gap-2">
        <Label className="text-xs">Statut :</Label>
        <Select
          value={status}
          onValueChange={(v) => {
            setStatus(v as ObligationFilter);
          }}
        >
          <SelectTrigger className="w-36">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {OBLIGATION_STATUS_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Info Hash</TableHead>
            <TableHead>Tracker</TableHead>
            <TableHead>Ratio min</TableHead>
            <TableHead>Ratio obs.</TableHead>
            <TableHead>Seed min</TableHead>
            <TableHead>HnR</TableHead>
            <TableHead>Statut</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((item) => {
            const obs = obligationStatus(item);
            return (
              <TableRow key={`o-${item.info_hash}-${item.source_tracker}`}>
                <TableCell className="font-mono text-xs">
                  {truncate(item.info_hash, 12)}
                </TableCell>
                <TableCell className="text-xs">{item.source_tracker}</TableCell>
                <TableCell className="font-mono text-xs">
                  {item.min_ratio.toFixed(2)}
                </TableCell>
                <TableCell className="font-mono text-xs">
                  {item.observed_ratio != null
                    ? item.observed_ratio.toFixed(2)
                    : "—"}
                </TableCell>
                <TableCell className="font-mono text-xs">
                  {item.min_seed_time_s > 0
                    ? `${String(Math.round(item.min_seed_time_s / 3600))} h`
                    : "—"}
                </TableCell>
                <TableCell>
                  {item.hnr_count != null && item.hnr_count > 0 ? (
                    <Badge tone="danger">{String(item.hnr_count)}</Badge>
                  ) : (
                    "0"
                  )}
                </TableCell>
                <TableCell>
                  <Badge tone={STATUS_TONE[obs] ?? "neutral"}>
                    {STATUS_LABEL[obs] ?? obs}
                  </Badge>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
