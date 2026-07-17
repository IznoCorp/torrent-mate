/**
 * MaintenanceRunRedirect — conditional redirect from /maintenance?run=<uid>.
 *
 * When the URL carries a ``?run=<uid>`` query parameter, this component replaces
 * the current history entry with ``/pipeline?run=<uid>`` so the pipeline-run
 * detail opens at its canonical address.  The ``replace`` navigation prevents the
 * redirecting URL from appearing in the back-button history, preserving the
 * contract of
 * {@link https://github.com/IznoCorp/torrent-mate/blob/main/docs/reference/product-intent.md | DOIT-10}
 * (« Retrouvable. Chaque détail a son URL ; Retour ferme ce qu'il doit fermer. »).
 *
 * When ``?run=`` is absent, the standard ``<Maintenance />`` page renders
 * unchanged (this wrapper adds zero extra DOM nodes in that case).
 *
 * Only the ``run`` parameter is forwarded to the pipeline route.  Any other
 * search params on ``/maintenance`` (e.g. a future ``?tab=``) are intentionally
 * dropped — they belong to Maintenance, not Pipeline.
 */
import { Navigate, useSearchParams } from "react-router-dom";
import type { ReactElement } from "react";
import Maintenance from "@/pages/Maintenance";

export function MaintenanceRunRedirect(): ReactElement {
  const [searchParams] = useSearchParams();
  const runUid = searchParams.get("run");
  if (runUid !== null && runUid !== "") {
    return <Navigate to={`/pipeline?run=${runUid}`} replace />;
  }
  return <Maintenance />;
}
