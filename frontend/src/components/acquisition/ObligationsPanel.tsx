/**
 * ObligationsPanel — the "Obligations" tab: seed-obligation rows (ratio, seed
 * time, HnR) with a server-side status filter.
 *
 * Phase 02: title-led rows — the first column shows the resolved title
 * (item.title) or falls back to the truncated info_hash.  The hash is demoted
 * to a secondary mono column with a copy-to-clipboard button.
 *
 * Extracted from `AcquisitionPage.tsx` (C12).
 */

import { Check, Copy } from "lucide-react";
import { useCallback, useState, type ReactElement } from "react";
import { toast } from "sonner";

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
  // Track which hashes have been copied (→ check icon for ~1.5 s).
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  const { data, isLoading, isError, error } = useObligations(
    status !== "all" ? { status } : {},
  );

  // Trust the SERVER filter (the route already filters by status) — do NOT
  // re-filter client-side: a row with both satisfied_at and breached_at set is
  // classified "breached" by the server but "satisfied" by obligationStatus(),
  // so a client re-filter would silently drop it (adversarial-review finding).
  // obligationStatus() stays in use only for the per-row status BADGE.
  const items = data?.items ?? [];

  /**
   * Copy a hash to the clipboard and show the check icon for 1.5 s.
   *
   * Uses {@link navigator.clipboard.writeText} — no fallback for insecure
   * contexts (the app is served over HTTPS).
   */
  const handleCopyHash = useCallback((hash: string): void => {
    void navigator.clipboard
      .writeText(hash)
      .then(() => {
        setCopiedHash(hash);
        setTimeout(() => {
          setCopiedHash((prev) => (prev === hash ? null : prev));
        }, 1500);
      })
      .catch(() => {
        toast.error("Copie du hash impossible");
      });
  }, []);

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
            : `Aucune obligation avec le statut « ${STATUS_LABEL[status] ?? "statut inconnu"} ».`}
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

      {/* Table — ACQUISITION-4 (ticket 250): 8 columns overflow a 375px
          viewport; the low-priority machine columns (hash, tracker, minima)
          collapse below md. Titre / Ratio obs. / HnR / Statut stay. */}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Titre</TableHead>
            <TableHead className="hidden md:table-cell">Hash</TableHead>
            <TableHead className="hidden md:table-cell">Tracker</TableHead>
            <TableHead className="hidden md:table-cell">Ratio min</TableHead>
            <TableHead>Ratio obs.</TableHead>
            <TableHead className="hidden md:table-cell">Seed min</TableHead>
            <TableHead>HnR</TableHead>
            <TableHead>Statut</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((item) => {
            const obs = obligationStatus(item);
            const truncatedHash = truncate(item.info_hash, 12);
            const copied = copiedHash === item.info_hash;
            return (
              <TableRow key={`o-${item.info_hash}-${item.source_tracker}`}>
                {/* Primary: resolved title, or fallback to truncated hash.
                    ACQUISITION-5: the truncated cell carries the full value
                    in its title. */}
                <TableCell
                  className="max-w-[200px] truncate text-xs font-medium"
                  title={item.title ?? item.info_hash}
                >
                  {item.title ?? truncatedHash}
                </TableCell>
                {/* Hash — mono, truncated, with copy button. */}
                <TableCell className="hidden font-mono text-xs md:table-cell">
                  <span className="flex items-center gap-1">
                    <span title={item.info_hash}>{truncatedHash}</span>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-5"
                      aria-label={`Copier le hash ${item.info_hash}`}
                      onClick={() => {
                        handleCopyHash(item.info_hash);
                      }}
                    >
                      {copied ? (
                        <Check className="size-3 text-success" />
                      ) : (
                        <Copy className="size-3" />
                      )}
                    </Button>
                  </span>
                </TableCell>
                <TableCell className="hidden font-mono text-xs md:table-cell">
                  {item.source_tracker}
                </TableCell>
                <TableCell className="hidden font-mono text-xs md:table-cell">
                  {item.min_ratio.toFixed(2)}
                </TableCell>
                <TableCell className="font-mono text-xs">
                  {item.observed_ratio != null
                    ? item.observed_ratio.toFixed(2)
                    : "—"}
                </TableCell>
                <TableCell className="hidden font-mono text-xs md:table-cell">
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
                  {/* X7: French label, never the raw status token. */}
                  <Badge tone={STATUS_TONE[obs] ?? "neutral"}>
                    {STATUS_LABEL[obs] ?? "Statut inconnu"}
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
