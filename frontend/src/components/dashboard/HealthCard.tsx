/**
 * Backend health card for the dashboard (tm-shell §5.3).
 *
 * A {@link StatPanel} tile surfacing the two liveness booleans from
 * ``GET /api/health`` — Redis (the event-stream transport) and the library DB —
 * each as a green/red {@link StatusDot}. When the probe itself errors, or Redis
 * is reported down, a degraded banner appears: a Redis outage means the live feed
 * is running blind, so the operator must see it (DESIGN §9 risk row). While the
 * first probe is still in flight the card shows a neutral « vérification » state
 * rather than flashing the red alert on absent-yet data.
 */

import type { ReactElement } from "react";

import { StatPanel } from "@/components/ds/StatPanel";
import { StatusDot } from "@/components/ds/StatusDot";
import { useHealth } from "@/hooks/useHealth";

/** Read a loosely-typed health field as a strict boolean (``true`` only). */
function isOk(value: unknown): boolean {
  return value === true;
}

/**
 * HealthCard — Redis + DB reachability with a degraded banner.
 *
 * Returns:
 *   The health card element.
 */
export function HealthCard(): ReactElement {
  const { data, isError } = useHealth();

  // First probe still in flight (no data, no error): a neutral "checking" state,
  // NOT degraded — degraded is reserved for an explicit failure so the red alert
  // never flashes on absent-yet data (audit B8).
  const isChecking = data === undefined && !isError;
  const redisOk = isOk(data?.redis);
  const dbOk = isOk(data?.db);
  const degraded = isError || (data !== undefined && !redisOk);

  const bannerMessage = isError
    ? "Service dégradé — état de santé indisponible."
    : "Redis injoignable — le flux temps réel est dégradé.";

  return (
    <div className="flex flex-col gap-2">
      <StatPanel
        label="Santé système"
        value={
          <div className="flex flex-col gap-1 text-sm font-normal">
            <StatusDot
              status={isChecking ? "idle" : redisOk ? "done" : "error"}
              label={
                isChecking
                  ? "Redis — vérification…"
                  : redisOk
                    ? "Redis en ligne"
                    : "Redis hors ligne"
              }
            />
            <StatusDot
              status={isChecking ? "idle" : dbOk ? "done" : "error"}
              label={
                isChecking
                  ? "Base — vérification…"
                  : dbOk
                    ? "Base indexée"
                    : "Base injoignable"
              }
            />
          </div>
        }
      />
      {degraded && (
        <p
          role="alert"
          className="rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger"
        >
          {bannerMessage}
        </p>
      )}
    </div>
  );
}
