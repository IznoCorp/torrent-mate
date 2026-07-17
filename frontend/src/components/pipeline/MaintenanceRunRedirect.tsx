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
 * ``/systeme?tab=journal``.  The old ``/maintenance`` page carried the
 * destructive-operations journal inline (now ``DestructiveLogPanel`` on the
 * Journal tab); the operator's bookmark must land where the journal is
 * (arbitrated sub-phase 5.4, 2026-07-17).
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
  return <Navigate to="/systeme?tab=journal" replace />;
}
