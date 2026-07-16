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
import { type ReactElement } from "react";

import { getDestructiveLog } from "@/api/client";
import type { components } from "@/api/schema";
import { formatDatetime } from "@/components/acquisition/meta";
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

/** French label + tone for each destructive operation kind. */
const OP_LABEL: Record<string, string> = {
  overwrite: "Écrasé",
  delete: "Supprimé",
};

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
        <span className="rounded bg-[var(--danger)]/15 px-1.5 py-0.5 text-xs font-medium text-[var(--danger)]">
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
 *   empty, error-soft note on failure).
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
          pourquoi). Les plus récents en premier.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {query.isLoading ? (
          <div className="flex flex-col gap-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : query.isError ? (
          <p className="text-xs text-muted-foreground">
            Journal momentanément indisponible.
          </p>
        ) : entries.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            Aucune suppression enregistrée.
          </p>
        ) : (
          <ul className="flex flex-col">
            {entries.map((op, i) => (
              <LogRow key={`${String(op.ts)}-${op.path}-${String(i)}`} op={op} />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
