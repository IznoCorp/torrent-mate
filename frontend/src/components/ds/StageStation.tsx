import type { LucideIcon } from "lucide-react";
import type { ReactElement } from "react";

import type { StatusTone } from "@/components/ds/StatusBadge";
import { cn } from "@/lib/utils";

/** A stage's health state, driving its ring colour. */
export type StageState = "idle" | "ok" | "active" | "attention" | "blocked";

/** One sub-count shown inside a station (e.g. Matching → matché/ambigu). */
export interface StageSplit {
  readonly label: string;
  readonly count: number;
  readonly tone: StatusTone;
}

/** Props for {@link StageStation}. */
export interface StageStationProps {
  /** Stage label (French). */
  readonly label: string;
  /** Item count currently at this stage. */
  readonly count: number;
  /** Stage state (ring colour + a11y hint). */
  readonly state: StageState;
  /** Optional stage icon. */
  readonly icon?: LucideIcon;
  /** Optional sub-counts (e.g. matché / ambigu / sans-match). */
  readonly split?: readonly StageSplit[];
  /** When given, the station becomes a button opening the stage drawer. */
  readonly onClick?: () => void;
}

/** state → ring/border classes (token utilities only). */
const STATE_RING: Record<StageState, string> = {
  idle: "border-border",
  ok: "border-success/50",
  active: "border-info/60",
  attention: "border-warning/60",
  blocked: "border-danger/60",
};

/** StatusTone → dot colour class. */
const TONE_DOT: Record<StatusTone, string> = {
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
  info: "bg-info",
  neutral: "bg-muted-foreground",
};

/** state → French a11y hint for screen readers. */
const STATE_HINT: Record<StageState, string> = {
  idle: "au repos",
  ok: "à jour",
  active: "en cours",
  attention: "attention requise",
  blocked: "bloqué",
};

/**
 * StageStation — one station of the pipeline Flow Board: a stage label, a live
 * item count, a state ring, and optional sub-counts. Clicking opens that
 * stage's drawer.
 *
 * Args:
 *   label, count, state: The stage's identity + live figures.
 *   icon: Optional stage icon.
 *   split: Optional sub-counts.
 *   onClick: Optional open handler (makes the station a button).
 *
 * Returns:
 *   The station element.
 */
export function StageStation({
  label,
  count,
  state,
  icon: Icon,
  split,
  onClick,
}: StageStationProps): ReactElement {
  const body = (
    <>
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {Icon !== undefined && (
            <Icon className="size-3.5" aria-hidden="true" />
          )}
          {label}
        </span>
        <span
          className={cn(
            "size-2 shrink-0 rounded-full",
            state === "blocked"
              ? "bg-danger"
              : state === "attention"
                ? "bg-warning"
                : state === "active"
                  ? "bg-info"
                  : state === "ok"
                    ? "bg-success"
                    : "bg-muted-foreground",
          )}
          aria-hidden="true"
        />
      </div>
      <span className="font-mono text-2xl font-semibold tabular-nums">
        {count}
      </span>
      {split !== undefined && split.length > 0 && (
        <div className="flex flex-col gap-0.5">
          {split.map((s) => (
            <span
              key={s.label}
              className="flex items-center gap-1.5 text-xs text-muted-foreground"
            >
              <span
                className={cn("size-1.5 rounded-full", TONE_DOT[s.tone])}
                aria-hidden="true"
              />
              <span className="font-mono tabular-nums">{s.count}</span>
              {s.label}
            </span>
          ))}
        </div>
      )}
      <span className="sr-only">{STATE_HINT[state]}</span>
    </>
  );

  // Full-width on mobile (stations stack vertically in the Flow Board); a fixed
  // min-width on sm+ where the board is a horizontal scroll row.
  const cls = cn(
    "flex w-full flex-col gap-1.5 rounded-lg border bg-card p-3 sm:w-auto sm:min-w-36",
    STATE_RING[state],
  );

  return onClick !== undefined ? (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        cls,
        "text-left transition-colors hover:bg-accent/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
      )}
    >
      {body}
    </button>
  ) : (
    <div className={cls}>{body}</div>
  );
}
