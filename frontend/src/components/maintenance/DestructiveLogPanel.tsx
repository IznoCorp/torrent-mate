/**
 * DestructiveLogPanel — the append-only destructive-operations journal (§7).
 *
 * Renders the forensic trail whose absence turned the « Star City » incident
 * into a from-scratch reconstruction: every overwrite / deletion of library
 * content the app performs (who / what / when / why). Read-only, newest first;
 * polls ``GET /api/maintenance/destructive-log`` so a fresh op appears without
 * a manual reload.
 */

import { useQuery } from "@tanstack/react-query";
import { ScrollText } from "lucide-react";
import { type ReactElement } from "react";

import { getDestructiveLog } from "@/api/maintenance";
import type { components } from "@/api/schema";
import { formatDatetime } from "@/components/acquisition/meta";
import { EmptyState } from "@/components/ds/EmptyState";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { maintenanceKeys } from "@/hooks/useMaintenanceKeys";

type DestructiveOp = components["schemas"]["DestructiveOp"];

/** French label for each journaled operation kind. */
const OP_LABEL: Record<string, string> = {
  overwrite: "Écrasé",
  delete: "Supprimé",
  "metadata-refresh": "Métadonnées",
};

/**
 * Badge tone per operation kind.
 *
 * Only the kinds that DESTROY library content wear the alarming tone. A
 * `metadata-refresh` (regenerated NFO / artwork) is traced for completeness but
 * loses nothing, so it must not read as a deletion — that conflation is exactly
 * what made the journal unreadable.
 */
const OP_TONE: Record<string, string> = {
  overwrite: "bg-danger/15 text-danger",
  delete: "bg-danger/15 text-danger",
  "metadata-refresh": "bg-muted text-muted-foreground",
};

/** Fallback tone for an unknown op kind — neutral, never alarming. */
const DEFAULT_OP_TONE = "bg-muted text-muted-foreground";

/** French label for each actor (what performed the op). */
const ACTOR_LABEL: Record<string, string> = {
  dispatch: "Rangement",
  "disk-clean": "Nettoyage disque",
};

/** One journal row: op badge, path, actor, date, reason. */
function LogRow({ op }: { op: DestructiveOp }): ReactElement {
  return (
    <li className="flex flex-col gap-0.5 border-b border-border/60 py-2 last:border-b-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span
          className={`rounded px-1.5 py-0.5 text-xs font-medium ${OP_TONE[op.op] ?? DEFAULT_OP_TONE}`}
        >
          {OP_LABEL[op.op] ?? op.op}
        </span>
        <span className="text-xs text-muted-foreground">
          {ACTOR_LABEL[op.actor] ?? op.actor} · {formatDatetime(op.ts)}
        </span>
      </div>
      <span className="break-all font-mono text-xs" title={op.path}>
        {op.path}
      </span>
      {op.detail != null && op.detail !== "" && (
        <span className="text-xs text-muted-foreground">{op.detail}</span>
      )}
    </li>
  );
}

/**
 * DestructiveLogPanel — the « Journal des suppressions » maintenance card.
 *
 * Returns:
 *   The panel element (skeleton while loading, empty-state when the trail is
 *   empty, loud error alert on failure).
 */
export function DestructiveLogPanel(): ReactElement {
  const query = useQuery({
    queryKey: maintenanceKeys.destructiveLog,
    queryFn: getDestructiveLog,
    refetchInterval: 30_000,
  });
  const entries = query.data?.entries ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Journal des suppressions</CardTitle>
        <CardDescription>
          Trace de chaque fichier supprimé ou remplacé (qui, quoi, quand,
          pourquoi). Les plus récents en premier. Les lignes «&nbsp;Métadonnées
          &nbsp;» signalent une simple régénération des NFO et visuels&nbsp;:
          aucun média n'a été perdu.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {query.isLoading ? (
          <div className="flex flex-col gap-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : query.isError ? (
          <p className="text-sm text-danger" role="alert">
            Impossible de lire le journal des suppressions.
            {query.error instanceof Error ? ` (${query.error.message})` : ""}
          </p>
        ) : entries.length === 0 ? (
          <EmptyState
            icon={ScrollText}
            title="Aucune opération destructive"
            description="Le journal des suppressions et remplacements apparaîtra ici."
          />
        ) : (
          <ul className="flex flex-col">
            {entries.map((op, i) => (
              <LogRow
                key={`${String(op.ts)}-${op.path}-${String(i)}`}
                op={op}
              />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
