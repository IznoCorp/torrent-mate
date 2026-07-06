/**
 * Pipeline supervision page (TorrentMateUI S2 — pipe-control).
 *
 * Replaces the former {@link ComingSoon} stub at ``/pipeline``. The page polls
 * ``GET /api/pipeline/status`` every 5 seconds via TanStack Query and passes
 * the live status down to {@link PipelineControls}, {@link PipelineStepper},
 * and {@link RunLogFeed}.
 */

import { useQuery } from "@tanstack/react-query";
import type { ReactElement } from "react";

import { getPipelineStatus } from "@/api/client";
import type { components } from "@/api/schema";
import { PipelineControls } from "@/components/pipeline/PipelineControls";

/** The status shape from GET /api/pipeline/status. */
type StatusResponse = components["schemas"]["StatusResponse"];

/** Default status used while the first query is in flight. */
const DEFAULT_STATUS: StatusResponse = {
  state: "idle",
  paused: false,
  watcher_enabled: false,
};

/**
 * Pipeline — the authenticated pipeline supervision route (``/pipeline``).
 *
 * Returns:
 *   The pipeline page element.
 */
export default function Pipeline(): ReactElement {
  const { data: status } = useQuery({
    queryKey: ["pipeline", "status"],
    queryFn: getPipelineStatus,
    refetchInterval: 5_000,
  });

  const liveStatus = status ?? DEFAULT_STATUS;

  return (
    <section className="mx-auto flex max-w-5xl flex-col gap-4">
      <h1 className="text-xl font-semibold tracking-tight">Pipeline</h1>

      <PipelineControls status={liveStatus} />

      {/*
       * Placeholder — sub-phase 4.2 replaces this with PipelineStepper + RunLogFeed
       * so the page compiles now while the feed components are still being built.
       */}
      <section
        aria-label="État du pipeline"
        className="flex flex-col gap-4 rounded-lg border border-border p-6"
      >
        <p className="text-sm text-muted-foreground">
          PipelineStepper + RunLogFeed — livré en sous-phase 4.2.
        </p>
      </section>
    </section>
  );
}
