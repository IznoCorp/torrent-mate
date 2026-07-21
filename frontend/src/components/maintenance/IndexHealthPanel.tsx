/**
 * IndexHealthPanel — aggregate health snapshot of the indexer database.
 *
 * Polls ``GET /api/maintenance/index-health`` every 60 s and renders a
 * headline KPI row (items, files, total size) followed by per-check rows
 * with {@link StatusDot} indicators: NFO coverage, repair queue backlog,
 * outbox drain, last scan status, soft-deleted rows, and canonical-provider
 * gaps.
 */

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import type { ReactElement } from "react";

import { getIndexHealth, type IndexHealthResponse } from "@/api/maintenance";
import type { components } from "@/api/schema";
import { StatPanel } from "@/components/ds/StatPanel";
import { StatusDot } from "@/components/ds/StatusDot";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { maintenanceKeys } from "@/hooks/useMaintenanceKeys";
import { formatGb } from "@/lib/format";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type NfoStats = components["schemas"]["NfoStats"];

/** Per-check health verdict. */
interface CheckVerdict {
  readonly status: "done" | "warning" | "error";
  readonly label: string;
  readonly detail?: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Classify NFO coverage from valid / invalid / missing counts.
 *
 * Args:
 *   nfo: The NFO stats object from the API.
 *
 * Returns:
 *   A verdict: ``done`` when ≥ 90 % valid, ``warning`` when ≥ 70 %, ``error``
 *   otherwise.  When there are zero items the verdict is neutral (``done``).
 */
function nfoVerdict(nfo: NfoStats): CheckVerdict {
  const total = nfo.valid + nfo.invalid + nfo.missing;
  if (total === 0)
    return { status: "done", label: "NFO", detail: "Aucun item" };
  const ratio = nfo.valid / total;
  const pct = `${String(Math.round(ratio * 100))} %`;
  if (ratio > 0.9)
    return { status: "done", label: "NFO", detail: `${pct} valides` };
  if (ratio > 0.7)
    return { status: "warning", label: "NFO", detail: `${pct} valides` };
  return { status: "error", label: "NFO", detail: `${pct} valides` };
}

/** Format a duration in seconds as a French relative age. */
function humanAge(ageS: number | null | undefined): string {
  if (ageS == null) return "—";
  const s = Math.round(ageS);
  if (s < 60) return `${String(s)} s`;
  if (s < 3600) return `${String(Math.floor(s / 60))} min`;
  if (s < 86400) {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    return `${String(h)} h ${String(m).padStart(2, "0")} min`;
  }
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  return `${String(d)} j ${String(h)} h`;
}

/**
 * Classify the most recent scan run status.
 *
 * The backend lifecycle values are ``'running' | 'ok' | 'failed' | 'aborted'``
 * (``scan_run.status``, indexer/schema.py). ``'ok'`` — not ``'done'`` — is the
 * success terminal state; matching the wrong literal here painted a red dot
 * next to a healthy "ok" scan (U1, operator-reported).
 *
 * Args:
 *   status: The last_scan_status string, or null.
 *   stuck: Whether the scan is considered stuck.
 *
 * Returns:
 *   A verdict: ``done`` on success, ``warning`` when stuck/running, ``error``
 *   on failure, ``done`` with no-scan label when null.
 */
function scanVerdict(
  status: string | null | undefined,
  stuck: boolean,
): CheckVerdict {
  if (status == null)
    return { status: "done", label: "Dernier scan", detail: "Aucun" };
  if (stuck)
    return { status: "warning", label: "Dernier scan", detail: "Bloqué ?" };
  if (status === "ok")
    return { status: "done", label: "Dernier scan", detail: "OK" };
  if (status === "running")
    return { status: "warning", label: "Dernier scan", detail: "En cours" };
  // failed / aborted / unknown → error with the raw status as detail.
  return { status: "error", label: "Dernier scan", detail: status };
}

/**
 * Build a simple verdict: ``done`` when zero, ``warning`` otherwise.
 *
 * Args:
 *   label: The check label.
 *   count: The value to check.
 *   okWhenZero: Whether zero is healthy (default true).
 *
 * Returns:
 *   A verdict.
 */
function zeroOk(label: string, count: number): CheckVerdict {
  if (count === 0) return { status: "done", label, detail: "0" };
  return { status: "warning", label, detail: String(count) };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * IndexHealthPanel — a card displaying aggregate library.db health with
 * headline stats and per-check status indicators.
 *
 * Polls ``GET /api/maintenance/index-health`` every 60 s.
 *
 * Returns:
 *   The index-health card element.
 */
export function IndexHealthPanel(): ReactElement {
  const { data, isLoading, isError }: UseQueryResult<IndexHealthResponse> =
    useQuery({
      queryKey: maintenanceKeys.indexHealth,
      queryFn: getIndexHealth,
      refetchInterval: 60_000,
      refetchOnWindowFocus: true,
    });

  const nfo = data?.nfo;
  const nfoCheck: CheckVerdict | null = nfo != null ? nfoVerdict(nfo) : null;

  const scanCheck: CheckVerdict = scanVerdict(
    data?.last_scan_status,
    data?.last_scan_stuck ?? false,
  );

  const repairCheck: CheckVerdict = (() => {
    const pending = data?.repair_queue_pending ?? 0;
    if (pending === 0)
      return { status: "done", label: "File de réparation", detail: "Vide" };
    const age =
      data?.repair_queue_oldest_age_s != null
        ? humanAge(data.repair_queue_oldest_age_s)
        : "";
    return {
      status: "warning",
      label: "File de réparation",
      detail: `${String(pending)} en attente${age !== "" ? ` — + ancien : ${age}` : ""}`,
    };
  })();

  const outboxCheck: CheckVerdict = (() => {
    const pending = data?.outbox_pending ?? 0;
    if (pending === 0)
      return { status: "done", label: "Outbox", detail: "Vide" };
    const age =
      data?.outbox_oldest_age_s != null
        ? humanAge(data.outbox_oldest_age_s)
        : "";
    return {
      status: "warning",
      label: "Outbox",
      detail: `${String(pending)} en attente${age !== "" ? ` — + ancien : ${age}` : ""}`,
    };
  })();

  // « soft-deleted » is jargon (operator asked what it meant, 2026-07-15):
  // these are files the scanner no longer finds on disk, kept as tombstones
  // until a purge — say exactly that.
  const softDelCheck = zeroOk(
    "Fichiers disparus du disque (en attente de purge)",
    data?.soft_deleted ?? 0,
  );
  const canonNullCheck = zeroOk(
    "Sans fournisseur canonique",
    data?.canonical_null ?? 0,
  );

  /** Render a single check row with its StatusDot. */
  function renderCheck(v: CheckVerdict): ReactElement {
    return (
      <div key={v.label} className="flex items-center justify-between gap-2">
        <StatusDot status={v.status} label={v.label} />
        {v.detail != null && (
          <span className="text-xs text-muted-foreground">{v.detail}</span>
        )}
      </div>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Santé de l'index</CardTitle>
        <CardDescription>Base library.db</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {isLoading && (
          <p className="text-sm text-muted-foreground">
            Chargement de l'index…
          </p>
        )}
        {isError && (
          <p className="text-sm text-danger" role="alert">
            Erreur lors du chargement.
          </p>
        )}

        {!isLoading && !isError && data != null && data.degraded && (
          <div
            className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive"
            role="alert"
          >
            Lecture de l'index dégradée — les compteurs ci-dessous peuvent être
            incomplets ou nuls.
            {data.error != null && (
              <span className="block text-muted-foreground">{data.error}</span>
            )}
          </div>
        )}

        {!isLoading && !isError && data != null && (
          <>
            {/* Headline stats — stacked. The index-health card is a narrow
                grid track (~200px), too tight for a 5-digit figure in a 2-col
                split (the value clipped: "97605" → "9760…"). Stacking gives each
                stat the full card width; the descriptor stays on its own
                wrapping `secondary` line below the figure. */}
            <div className="grid grid-cols-1 gap-2">
              <StatPanel
                label="Items"
                value={data.items}
                secondary={`${String(data.movies)} films / ${String(data.shows)} séries`}
              />
              <StatPanel
                label="Fichiers"
                value={data.files}
                secondary={formatGb(data.size_gb)}
              />
            </div>

            {/* Per-check rows */}
            <div className="flex flex-col gap-1.5 border-t border-border pt-3">
              {nfoCheck != null && renderCheck(nfoCheck)}
              {renderCheck(repairCheck)}
              {renderCheck(outboxCheck)}
              {renderCheck(scanCheck)}
              {renderCheck(softDelCheck)}
              {renderCheck(canonNullCheck)}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
