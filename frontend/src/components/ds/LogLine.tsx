import * as React from "react";

import "./LogLine.css";

/** Severity of a structured console row. */
export type LogLevel = "debug" | "info" | "success" | "warn" | "error";

/**
 * Props for {@link LogLine} (mirrors the DS `LogLine.d.ts` contract).
 */
export interface LogLineProps extends React.HTMLAttributes<HTMLDivElement> {
  /** @default "info" */
  level?: LogLevel;
  /** Timestamp text (kept tabular). */
  time?: React.ReactNode;
  className?: string;
  children?: React.ReactNode;
}

const SHORT: Record<LogLevel, string> = {
  debug: "DBG",
  info: "INF",
  success: "OK",
  warn: "WRN",
  error: "ERR",
};

/**
 * LogLine — a single structured (structlog-style) console row.
 *
 * Monospace, tabular timestamp, colour-coded level. Wrap key values in `<b>`
 * within `children` to highlight them in the primary colour. Ported from the
 * design-system `LogLine.jsx` reference.
 *
 * @returns The console row element.
 */
export function LogLine({
  level = "info",
  time,
  children,
  className = "",
  ...rest
}: LogLineProps): React.JSX.Element {
  return (
    <div className={`ps-log ps-log--${level} ${className}`} {...rest}>
      {time != null && <span className="ps-log__ts">{time}</span>}
      <span className="ps-log__lvl">{SHORT[level]}</span>
      <span className="ps-log__msg">{children}</span>
    </div>
  );
}
