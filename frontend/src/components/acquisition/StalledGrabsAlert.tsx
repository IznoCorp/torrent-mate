/**
 * StalledGrabsAlert — acquisitions parked at « récupéré » that never landed.
 *
 * Extracted unchanged from the old « Vue d'ensemble » when that tab was
 * dissolved. Its home is now « Maintenant », above the sections: it is an alert
 * about work that has STOPPED, not one more list to scan, and losing it would
 * make a whole class of stall silent again — which is exactly what it was built
 * to end.
 */

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { type ReactElement } from "react";

import { acqKeys, getStalledGrabs } from "@/api/acquisition";

/**
 * StalledGrabsAlert — acquisitions parked at « récupéré » (§14.1).
 *
 * §14.1 recognises only TWO legitimate rest states: « not aired yet » and
 * « searched, nothing found ». « Récupéré » is transitory and must advance on
 * its own; a row stagnating there is non-conformant and above all MUTE — the
 * search pass only resumes pending/searching/available, so the media stays
 * wanted with nobody looking for it. Such a row once stayed invisible until
 * the operator asked the question themselves.
 *
 * A banner, not a tile: §8 wants what is NOT moving to be seen, with its
 * reason. Nothing renders when nothing is parked — a permanent alert no
 * longer alerts.
 *
 * @param count - The count reported by the overview.
 * @returns The banner, or null when nothing is parked.
 */
export function StalledGrabsAlert({ count }: { count: number }): ReactElement | null {
  // The list is fetched ONLY when the count is non-zero: the detail exists to
  // NAME the items and must not weigh on the normal render.
  const { data, isError } = useQuery({
    queryKey: acqKeys.stalledGrabs(),
    queryFn: getStalledGrabs,
    enabled: count > 0,
  });
  if (count === 0) return null;
  const items = data?.items ?? [];
  return (
    <div
      role="alert"
      className="flex flex-col gap-2 rounded-lg border border-[color-mix(in_oklch,var(--warning)_32%,transparent)] bg-[color-mix(in_oklch,var(--warning)_12%,transparent)] p-3"
    >
      <div className="flex items-center gap-2">
        <AlertTriangle className="size-4 shrink-0 text-[var(--warning)]" />
        <p className="text-sm font-medium">
          {count === 1
            ? "1 acquisition récupérée n'est jamais arrivée en médiathèque"
            : `${String(count)} acquisitions récupérées ne sont jamais arrivées en médiathèque`}
        </p>
      </div>
      {isError && (
        <p className="text-xs text-muted-foreground">
          La liste des acquisitions concernées n&apos;a pas pu être chargée.
        </p>
      )}
      <ul className="flex flex-col gap-1.5">
        {items.map((it) => (
          <li key={it.wanted_id} className="min-w-0 text-xs">
            <span className="font-medium">{it.title}</span>
            <span className="text-muted-foreground"> — {it.reason}</span>
            {/* §13 — name the release ACTUALLY grabbed: what tells a FLAC
                soundtrack apart from the film of the same name. Admit the
                unknown; never a media title standing in for it. */}
            <span className="block truncate font-mono text-muted-foreground" title={it.release_name ?? undefined}>
              {it.release_name ?? "Nom de release non enregistré"}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
