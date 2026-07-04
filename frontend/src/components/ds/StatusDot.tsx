import * as React from "react";

import "./StatusDot.css";

/** Lifecycle state of a pipeline step / job / tracker. */
export type PipelineStatus =
  | "idle"
  | "queued"
  | "running"
  | "done"
  | "error"
  | "skipped";

/**
 * Props for {@link StatusDot} (mirrors the DS `StatusDot.d.ts` contract).
 */
export interface StatusDotProps extends React.HTMLAttributes<HTMLSpanElement> {
  /** @default "idle" */
  status?: PipelineStatus;
  /** Override the default status text. */
  label?: React.ReactNode;
  /** Hide the text, dot only. @default true */
  showLabel?: boolean;
  className?: string;
}

const LABELS: Record<PipelineStatus, string> = {
  idle: "Idle",
  queued: "Queued",
  running: "Running",
  done: "Done",
  error: "Failed",
  skipped: "Skipped",
};

/**
 * StatusDot — a coloured pulse + label for any pipeline / job state.
 *
 * `running` animates a ping; every state maps to the DS signal palette. Ported
 * from the design-system `StatusDot.jsx` reference (CSS moved to a co-located
 * stylesheet; token references preserved).
 *
 * @returns The status indicator element.
 */
export function StatusDot({
  status = "idle",
  label,
  showLabel = true,
  className = "",
  ...rest
}: StatusDotProps): React.JSX.Element {
  const text = label ?? LABELS[status];
  return (
    <span className={`ps-dot ps-dot--${status} ${className}`} {...rest}>
      <span className="ps-dot__d" />
      {showLabel && <span className="ps-dot__label">{text}</span>}
    </span>
  );
}
