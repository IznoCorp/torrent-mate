/**
 * Recent-events table for the dashboard (tm-shell §5.3).
 *
 * A sortable **TanStack Table** over the last {@link RECENT_LIMIT} events —
 * proving the typed-columns/sort foundation the later waves build richer tables
 * on. Columns: heure (derived from the stream cursor), type, résumé (payload
 * preview). Newest first by default; every column header toggles its sort.
 */

import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import { useMemo, useState, type ReactElement } from "react";

import type { EventMessage } from "@/api/events";
import {
  eventSummary,
  eventTypeLabel,
  formatEventTime,
  severityForEventType,
  type Severity,
} from "@/components/dashboard/eventRow.utils";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

/** How many of the most-recent events the table shows. */
export const RECENT_LIMIT = 50;
/** Max characters of the payload summary before it is ellipsized. */
const SUMMARY_MAX_CHARS = 80;

/** Maps a severity bucket to its DS Badge tone + log level for the "Niveau" column. */
const SEVERITY_BADGE: Record<
  Severity,
  { readonly tone: BadgeProps["tone"]; readonly level: string }
> = {
  danger: { tone: "danger", level: "error" },
  warning: { tone: "warning", level: "warn" },
  neutral: { tone: "neutral", level: "info" },
};

/** A flattened, table-friendly projection of one event. */
interface EventRowData {
  readonly id: string;
  /** Millisecond epoch parsed from the stream cursor (sort key for "heure"). */
  readonly time: number;
  /** Raw event class name — sort key + tooltip; the cell shows a French label. */
  readonly type: string;
  /** Condensed, human-readable payload summary (never raw JSON, F4). */
  readonly summary: string;
  /** Full JSON payload, surfaced only as the summary cell's tooltip. */
  readonly rawJson: string;
  /** Severity bucket driving the "Niveau" badge (and its sort). */
  readonly severity: Severity;
}

/** Project an {@link EventMessage} into its sortable table-row shape. */
function toRowData(event: EventMessage): EventRowData {
  const [msPart] = event.id.split("-");
  const ms = Number(msPart);
  const json = JSON.stringify(event.data);
  return {
    id: event.id,
    time: Number.isFinite(ms) ? ms : 0,
    type: event.type,
    summary: eventSummary(event.data),
    rawJson: json.length <= SUMMARY_MAX_CHARS ? json : `${json.slice(0, SUMMARY_MAX_CHARS)}…`,
    severity: severityForEventType(event.type),
  };
}

/** The column definitions, typed against {@link EventRowData}. */
const columns: ColumnDef<EventRowData>[] = [
  {
    accessorKey: "time",
    header: "Heure",
    cell: ({ row }) => (
      <span className="font-mono tabular-nums">
        {formatEventTime(row.original.id)}
      </span>
    ),
  },
  {
    accessorKey: "type",
    header: "Événement",
    cell: ({ row }) => (
      <span title={row.original.type}>{eventTypeLabel(row.original.type)}</span>
    ),
  },
  {
    accessorKey: "summary",
    header: "Détail",
    cell: ({ row }) => (
      <span
        className="text-xs text-muted-foreground"
        title={row.original.rawJson}
      >
        {row.original.summary}
      </span>
    ),
  },
  {
    accessorKey: "severity",
    header: "Niveau",
    cell: ({ row }) => {
      const { tone, level } = SEVERITY_BADGE[row.original.severity];
      return (
        <Badge tone={tone} dot>
          {level}
        </Badge>
      );
    },
  },
];

/** Props for {@link RecentEventsTable}. */
export interface RecentEventsTableProps {
  /** The event ring (oldest first); the table takes the newest slice. */
  readonly events: readonly EventMessage[];
}

/**
 * RecentEventsTable — a sortable table of the {@link RECENT_LIMIT} newest events.
 *
 * Args:
 *   events: The event ring to project; the last {@link RECENT_LIMIT} entries are
 *     shown, newest first by default.
 *
 * Returns:
 *   The recent-events table element.
 */
export function RecentEventsTable({
  events,
}: RecentEventsTableProps): ReactElement {
  const [sorting, setSorting] = useState<SortingState>([
    { id: "time", desc: true },
  ]);

  // Newest-first slice of the ring, memoized so sorting/re-renders stay cheap.
  const data = useMemo<EventRowData[]>(
    () =>
      events
        .slice(Math.max(0, events.length - RECENT_LIMIT))
        .reverse()
        .map(toRowData),
    [events],
  );

  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold tracking-tight">
        Événements récents
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
            {table.getRowModel().rows.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="text-center text-xs text-muted-foreground"
                >
                  Aucun événement pour l’instant.
                </TableCell>
              </TableRow>
            ) : (
              table.getRowModel().rows.map((row) => (
                <TableRow key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </section>
  );
}
