/**
 * Version card for the dashboard (tm-shell §5.3).
 *
 * A {@link StatPanel} tile showing the deployed package version and its short
 * build commit (from ``GET /api/version``). It also compares that commit against
 * the **live** ``build_commit`` the WebSocket handshake reports: a mismatch means
 * the server has been redeployed since this tab loaded — surfaced here as a hint
 * and the groundwork for the phase-7 update toast.
 */

import type { ReactElement } from "react";

import { ErrorState } from "@/components/ds/ErrorState";
import { StatPanel } from "@/components/ds/StatPanel";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useEventStreamContext } from "@/hooks/useEventStreamContext";
import { useVersion } from "@/hooks/useHealth";

/** Length of the short commit hash rendered on the card. */
const SHORT_COMMIT_LEN = 7;

/** Shorten a commit SHA to {@link SHORT_COMMIT_LEN}, tolerating a missing value. */
function short(commit: string | undefined): string {
  if (commit === undefined || commit === "") {
    return "—";
  }
  return commit.slice(0, SHORT_COMMIT_LEN);
}

/**
 * VersionCard — deployed version + build commit, with a live-mismatch hint.
 *
 * Returns:
 *   The version card element.
 */
export function VersionCard(): ReactElement {
  const { data, isPending, isError } = useVersion();
  const { buildCommit: liveCommit } = useEventStreamContext();

  // X2 — a down /api/version must never collapse to a "—" placeholder
  // indistinguishable from loading (data-illusion class).
  if (isPending) {
    return (
      <div className="flex flex-col gap-2" aria-busy="true">
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-3 w-24" />
      </div>
    );
  }
  if (isError) {
    return (
      <ErrorState
        title="Version indisponible"
        message="La version déployée n'a pas pu être lue."
      />
    );
  }

  // Past the isPending/isError guards the query narrowed to success — data is
  // guaranteed (TanStack v5 discriminated union).
  const version = data.version;
  const restCommit = data.build_commit;

  // A live build_commit that differs from the REST one means the server has
  // moved on since load — the seam the phase-7 auto-update toast will hook into.
  const hasMismatch = liveCommit !== null && liveCommit !== restCommit;

  return (
    <div className="flex flex-col gap-2">
      <StatPanel label="Version" value={version} />
      <p className="font-mono text-xs text-muted-foreground">
        commit {short(restCommit)}
      </p>
      {/* DASHBOARD-4 (ticket 250): DS warning Badge, not an ad-hoc coloured
          paragraph — the commit stays a mono machine token. */}
      {hasMismatch && (
        <Badge tone="warning" dot className="self-start">
          Nouvelle version côté serveur :{" "}
          <span className="font-mono">{short(liveCommit)}</span>
        </Badge>
      )}
    </div>
  );
}
