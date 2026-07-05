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

import { StatPanel } from "@/components/ds/StatPanel";
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
  const { data } = useVersion();
  const { buildCommit: liveCommit } = useEventStreamContext();

  const version = data?.version ?? "—";
  const restCommit = data?.build_commit;

  // A live build_commit that differs from the REST one means the server has
  // moved on since load — the seam the phase-7 auto-update toast will hook into.
  const hasMismatch =
    liveCommit !== null &&
    restCommit !== undefined &&
    liveCommit !== restCommit;

  return (
    <div className="flex flex-col gap-2">
      <StatPanel label="Version" value={version} />
      <p className="font-mono text-xs text-muted-foreground">
        commit {short(restCommit)}
      </p>
      {hasMismatch && (
        <p className="text-xs text-warning">
          Nouvelle version côté serveur : {short(liveCommit)}
        </p>
      )}
    </div>
  );
}
