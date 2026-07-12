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
  /** Errored item count at this stage — surfaced as a danger pastille. */
  readonly blocked?: number;
  /** Optional temporal caption (e.g. "dernier run" / "en attente"). */
  readonly timeframe?: string;
  /** Optional stage icon. */
  readonly icon?: LucideIcon;
  /** Optional sub-counts (e.g. matché / ambigu / sans-match). */
  readonly split?: readonly StageSplit[];
  /** When given, the station becomes a button opening the stage drawer. */
  readonly onClick?: () => void;
}

/** state → container classes: attention/blocked get a lavis wash + full border
 *  so the eye lands on them first; active/ok/idle stay calm. Token utilities only. */
const STATE_CONTAINER: Record<StageState, string> = {
  idle: "border-border",
  ok: "border-success/40",
  active: "border-info/70",
  attention: "border-warning bg-warning/5 ring-1 ring-warning/25",
  blocked: "border-danger bg-danger/5 ring-1 ring-danger/25",
};

/** state → hero-count colour (attention/blocked draw the eye). */
const STATE_COUNT: Record<StageState, string> = {
  idle: "",
  ok: "",
  active: "",
  attention: "text-warning",
  blocked: "text-danger",
};

/** state → dot colour class. */
const STATE_DOT: Record<StageState, string> = {
  idle: "bg-muted-foreground",
  ok: "bg-success",
  active: "bg-info",
  attention: "bg-warning",
  blocked: "bg-danger",
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
  blocked = 0,
  timeframe,
  icon: Icon,
  split,
  onClick,
}: StageStationProps): ReactElement {
  const isActive = state === "active";
  const body = (
    <>
      {/* Running stage: an ambre progress shimmer swept along the top edge. */}
      {isActive && (
        <span
          className="ps-shimmer pointer-events-none absolute inset-x-0 top-0 h-0.5"
          aria-hidden="true"
        />
      )}
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
            STATE_DOT[state],
            isActive && "ps-pulse",
          )}
          aria-hidden="true"
        />
      </div>
      <div className="flex items-baseline gap-2">
        {/* key={count} replays the pop keyframe whenever the value changes. */}
        <span
          key={count}
          className={cn(
            "ps-count-pop origin-left font-mono text-2xl font-semibold tabular-nums",
            STATE_COUNT[state],
          )}
        >
          {count}
        </span>
        {state === "blocked" && blocked > 0 && (
          <span className="rounded-full bg-danger/15 px-1.5 py-0.5 font-mono text-[length:var(--text-2xs)] font-semibold tabular-nums text-danger">
            {blocked} erreur{blocked > 1 ? "s" : ""}
          </span>
        )}
      </div>
      {timeframe !== undefined && (
        <span className="text-[length:var(--text-2xs)] uppercase tracking-wide text-muted-foreground/80">
          {timeframe}
        </span>
      )}
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
  // min-width on sm+ where the board is a horizontal scroll row. `relative
  // overflow-hidden` clips the active shimmer to the rounded card.
  const cls = cn(
    "relative flex w-full flex-col gap-1.5 overflow-hidden rounded-lg border bg-card p-3 transition-colors sm:w-auto sm:min-w-36",
    STATE_CONTAINER[state],
  );

  // Full a11y label so a screen reader announces the stage + its live figures.
  const ariaLabel = `Étape ${label}, ${String(count)}, ${STATE_HINT[state]}`;

  return onClick !== undefined ? (
    <button
      type="button"
      onClick={onClick}
      aria-haspopup="dialog"
      aria-label={ariaLabel}
      className={cn(
        cls,
        "text-left hover:bg-accent/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
      )}
    >
      {body}
    </button>
  ) : (
    <div className={cls}>{body}</div>
  );
}
