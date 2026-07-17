/**
 * MaintenanceRunRedirect — conditional redirect from /maintenance?run=<uid>.
 *
 * When the URL carries a ``?run=<uid>`` query parameter, this component replaces
 * the current history entry with ``/pipeline?run=<uid>`` so the pipeline-run
 * detail opens at its canonical address (V3 contract).  The ``replace``
 * navigation prevents the redirecting URL from appearing in the back-button
 * history, preserving DOIT-10.
 *
 * When ``?run=`` is absent or empty, the request redirects (replace) to
 * ``/systeme`` — the bare canonical route for the unified system hub
 * (systeme-hub feature).  The default État tab renders there; maintenance
 * panels (actions, history, journal) live under sibling tabs.  This clean
 * redirect replaces the old ``/maintenance`` bookmark with a single canonical
 * entry point.
 *
 * Only the ``run`` parameter is forwarded to the pipeline route.  Any other
 * search params on ``/maintenance`` (e.g. a future ``?tab=``) are intentionally
 * dropped — they belong to Maintenance, not Pipeline.
 */
import { Navigate, useSearchParams } from "react-router-dom";
import type { ReactElement } from "react";

export function MaintenanceRunRedirect(): ReactElement {
  const [searchParams] = useSearchParams();
  const runUid = searchParams.get("run");
  if (runUid !== null && runUid !== "") {
    return (
      <Navigate to={`/pipeline?run=${encodeURIComponent(runUid)}`} replace />
    );
  }
  return <Navigate to="/systeme" replace />;
}
