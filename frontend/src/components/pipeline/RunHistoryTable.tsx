/**
 * RunHistoryTable — sortable, paginated table of past pipeline runs.
 *
 * Part of TorrentMateUI pipe-control Phase 5 (run-history). Fetches pages of
 * {@link RunSummary} rows from ``GET /api/pipeline/history`` via TanStack Query
 * and renders them with a TanStack Table whose columns mirror the
 * {@link RecentEventsTable} pattern: sortable headers with DS icons, mono/tabular
 * values, and semantic Badge tones.
 *
 * Columns: Date (started_at via ``Intl.DateTimeFormat``), Déclencheur (trigger),
 * Issue (outcome → Badge tone), Durée (duration_s → ``Xm Ys`` or ``Ys``).
 * Sortable: Date (default desc), Durée. Server-side sort via the ``sort`` query
 * param. Pagination via ``limit``/``offset`` with prev/next buttons and a total
 * count. Row click calls ``onSelect(run_uid)``.
 */

import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { useQuery } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import { useCallback, useMemo, useState, type ReactElement } from "react";

import { getPipelineHistory, type HistoryParams } from "@/api/client";
import type { components } from "@/api/schema";
import { triggerLabel } from "@/components/pipeline/triggers";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** One row from the history list endpoint. */
type RunSummary = components["schemas"]["RunSummary"];

/** Page size for the history table. */
const PAGE_SIZE = 20;

/** Maps an outcome string to a DS Badge tone (design-system signal palette). */
const OUTCOME_BADGE: Record<
  string,
  { readonly tone: BadgeProps["tone"]; readonly label: string }
> = {
  success: { tone: "success", label: "Succès" },
  error: { tone: "danger", label: "Erreur" },
  killed: { tone: "warning", label: "Arrêté" },
  running: { tone: "info", label: "En cours" },
  paused: { tone: "info", label: "En pause" },
};

/** Default outcome info for null/unknown outcomes. */
const DEFAULT_OUTCOME = { tone: "neutral" as BadgeProps["tone"], label: "—" };

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

/**
 * Format an ISO 8601 UTC timestamp into a French-localised date string.
 *
 * Args:
 *   iso: The ISO 8601 UTC timestamp.
 *
 * Returns:
 *   A short date+time string formatted for the ``fr`` locale.
 */
function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("fr", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

/**
 * Format a duration in seconds to a compact ``Xm Ys`` or ``Ys`` string.
 *
 * Args:
 *   seconds: Duration in seconds, or null/undefined.
 *
 * Returns:
 *   A human-readable duration string, or ``"—"`` if null.
 */
function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return "—";
  const s = Math.round(seconds);
  if (s < 60) return `${String(s)}s`;
  const mins = Math.floor(s / 60);
  const secs = s % 60;
  return `${String(mins)}m ${String(secs).padStart(2, "0")}s`;
}

// ---------------------------------------------------------------------------
// Column definitions
// ---------------------------------------------------------------------------

/**
 * Outcome-info lookup.
 *
 * Args:
 *   outcome: The pipeline outcome string, or null.
 *
 * Returns:
 *   A ``{tone, label}`` pair for the Badge.
 */
function outcomeInfo(outcome: string | null | undefined): {
  readonly tone: BadgeProps["tone"];
  readonly label: string;
} {
  if (outcome == null) return DEFAULT_OUTCOME;
  return OUTCOME_BADGE[outcome] ?? DEFAULT_OUTCOME;
}

/** Column definitions typed against {@link RunSummary}. */
const COLUMNS: ColumnDef<RunSummary>[] = [
  {
    accessorKey: "started_at",
    header: "Date",
    cell: ({ row }) => (
      <span className="font-mono tabular-nums text-xs">
        {formatDate(row.original.started_at)}
      </span>
    ),
  },
  {
    accessorKey: "trigger",
    header: "Déclencheur",
    cell: ({ row }) => (
      <span className="text-xs">{triggerLabel(row.original.trigger)}</span>
    ),
  },
  {
    id: "outcome",
    accessorKey: "outcome",
    header: "Issue",
    cell: ({ row }) => {
      const { tone, label } = outcomeInfo(row.original.outcome);
      return (
        <Badge tone={tone} dot>
          {label}
        </Badge>
      );
    },
  },
  {
    id: "duration_s",
    accessorKey: "duration_s",
    header: "Durée",
    cell: ({ row }) => (
      <span className="font-mono tabular-nums text-xs">
        {formatDuration(row.original.duration_s)}
      </span>
    ),
  },
];

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

/** Props for {@link RunHistoryTable}. */
export interface RunHistoryTableProps {
  /** Called with the selected run UID when a row is clicked. */
  readonly onSelect: (runUid: string) => void;
  /**
   * Optional run-kind filter forwarded to the backend.
   *
   * When set to ``"maintenance"`` only maintenance runs appear; ``"pipeline"``
   * restricts to pipeline runs.  Omitted or undefined → all run kinds.
   */
  readonly kind?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * RunHistoryTable — a sortable, paginated table of past pipeline runs.
 *
 * Fetches pages from ``GET /api/pipeline/history`` with server-side sorting
 * and offset pagination. Each row is clickable; the selected ``run_uid`` is
 * forwarded to ``onSelect`` so the page can open a detail view.
 *
 * Args:
 *   onSelect: Callback invoked with the selected run UID.
 *   kind: Optional run-kind filter (``"maintenance"`` or ``"pipeline"``).
 *
 * Returns:
 *   The history table element.
 */
export function RunHistoryTable({
  onSelect,
  kind,
}: RunHistoryTableProps): ReactElement {
  // Server-side pagination + sorting state.
  const [offset, setOffset] = useState(0);
  const [sorting, setSorting] = useState<SortingState>([
    { id: "started_at", desc: true },
  ]);

  // Derive the server `sort` param from TanStack sorting state.
  const sortParam = useMemo<string>(() => {
    const s = sorting[0];
    if (s === undefined) return "-started_at";
    const col = s.id === "duration_s" ? "duration" : "started_at";
    return s.desc ? `-${col}` : col;
  }, [sorting]);

  const queryParams: HistoryParams = useMemo(
    () => ({
      limit: PAGE_SIZE,
      offset,
      sort: sortParam,
      ...(kind !== undefined ? { kind } : {}),
    }),
    [offset, sortParam, kind],
  );

  const { data, isLoading, isError } = useQuery({
    queryKey: ["pipeline", "history", queryParams] as const,
    queryFn: () => getPipelineHistory(queryParams),
  });

  const runs = data?.runs ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  // Build the TanStack Table (client-side sort is a no-op since we push sort
  // to the server — the rows arrive pre-sorted).
  const table = useReactTable({
    data: runs,
    columns: COLUMNS,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    manualSorting: true,
  });

  // Pagination handlers.
  const goPrev = useCallback(() => {
    setOffset((prev) => Math.max(0, prev - PAGE_SIZE));
  }, []);
  const goNext = useCallback(() => {
    setOffset((prev) => {
      const next = prev + PAGE_SIZE;
      return next < total ? next : prev;
    });
  }, [total]);

  const hasPrev = offset > 0;
  const hasNext = offset + PAGE_SIZE < total;

  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold tracking-tight">
        Historique des exécutions
      </h2>

      <div className="rounded-lg border border-border bg-card">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => {
                  const sorted = header.column.getIsSorted();
                  return (
                    <TableHead key={header.id}>
                      <button
                        type="button"
                        onClick={header.column.getToggleSortingHandler()}
                        className="flex items-center gap-1 text-xs font-medium uppercase tracking-wide text-muted-foreground transition-colors hover:text-foreground"
                      >
                        {flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )}
                        {sorted === "asc" ? (
                          <ArrowUp className="size-3" aria-hidden="true" />
                        ) : sorted === "desc" ? (
                          <ArrowDown className="size-3" aria-hidden="true" />
                        ) : (
                          <ChevronsUpDown
                            className="size-3 opacity-50"
                            aria-hidden="true"
                          />
                        )}
                      </button>
                    </TableHead>
                  );
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell
                  colSpan={COLUMNS.length}
                  className="text-center text-xs text-muted-foreground"
                >
                  Chargement…
                </TableCell>
              </TableRow>
            ) : isError ? (
              <TableRow>
                <TableCell
                  colSpan={COLUMNS.length}
                  className="text-center text-xs text-muted-foreground"
                >
                  Erreur lors du chargement.
                </TableCell>
              </TableRow>
            ) : runs.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={COLUMNS.length}
                  className="text-center text-xs text-muted-foreground"
                >
                  Aucune exécution enregistrée.
                </TableCell>
              </TableRow>
            ) : (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  className="cursor-pointer"
                  onClick={() => {
                    onSelect(row.original.run_uid);
                  }}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext(),
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination bar */}
      {total > 0 && (
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>
            {total} exécution{total !== 1 ? "s" : ""} — page {currentPage}/
            {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={!hasPrev}
              onClick={goPrev}
              className="rounded-md border border-border px-2 py-1 text-xs transition-colors hover:bg-muted disabled:opacity-40"
            >
              Précédent
            </button>
            <button
              type="button"
              disabled={!hasNext}
              onClick={goNext}
              className="rounded-md border border-border px-2 py-1 text-xs transition-colors hover:bg-muted disabled:opacity-40"
            >
              Suivant
            </button>
          </div>
        </div>
      )}

    </section>
  );
}
