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
 * StalledGrabsAlert — les acquisitions parquées à « récupéré » (§14.1).
 *
 * §14.1 ne reconnaît que DEUX états de repos légitimes : « pas encore diffusé » et
 * « cherché, rien trouvé ». « Récupéré » est transitoire et doit avancer tout seul ; une
 * ligne qui y stagne est non conforme, et surtout MUETTE — la passe de recherche ne
 * reprend que pending/searching/available, donc le média reste voulu sans que personne
 * ne le cherche plus. Le 2026-08-05 une telle ligne est restée invisible jusqu'à ce que
 * l'opérateur pose la question.
 *
 * Une bannière, pas une tuile : §8 veut que ce qui n'avance pas se voie, avec sa raison.
 * Rien ne s'affiche quand il n'y a rien — une alerte permanente ne serait plus une alerte.
 *
 * @param count - Le nombre annoncé par la vue d'ensemble.
 * @returns La bannière, ou null quand rien n'est parqué.
 */
export function StalledGrabsAlert({ count }: { count: number }): ReactElement | null {
  // La liste n'est demandée QUE lorsque le compteur est non nul : le détail sert à
  // nommer les items, il n'a pas à peser sur le rendu normal.
  const { data } = useQuery({
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
      <ul className="flex flex-col gap-1.5">
        {items.map((it) => (
          <li key={it.wanted_id} className="min-w-0 text-xs">
            <span className="font-medium">{it.title}</span>
            <span className="text-muted-foreground"> — {it.reason}</span>
            {/* §13 — nommer la release RÉELLEMENT récupérée : c'est ce qui distingue
              une bande originale FLAC du film homonyme. « inconnue » quand elle
              ne peut pas être connue, jamais un titre de média à sa place. */}
            <span className="block truncate font-mono text-muted-foreground" title={it.release_name ?? undefined}>
              {it.release_name ?? "Nom de release non enregistré"}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
