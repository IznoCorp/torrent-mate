import * as React from "react";

import "./StatPanel.css";

/**
 * Props for {@link StatPanel} (mirrors the DS `StatPanel.d.ts` contract).
 */
export interface StatPanelProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Small uppercase caption. */
  label?: React.ReactNode;
  /** Leading icon for the label. */
  icon?: React.ReactNode;
  /** The headline figure. */
  value?: React.ReactNode;
  /** Short trailing unit rendered inline next to the value (e.g. "TB", "items"). */
  unit?: React.ReactNode;
  /**
   * Optional secondary line rendered BELOW the value — for a full descriptor
   * such as "12 films / 5 séries". Wraps and never collides with the headline
   * figure (unlike {@link StatPanelProps.unit}, which is inline).
   */
  secondary?: React.ReactNode;
  /** Optional trend text (e.g. "+12 / 24h"). */
  delta?: React.ReactNode;
  /** Trend colour. @default "flat" */
  deltaDir?: "up" | "down" | "flat";
  className?: string;
}

/**
 * StatPanel — a labelled KPI tile (library size, free space, queue depth…).
 *
 * Ported from the design-system `StatPanel.jsx` reference. Optional trend delta
 * is colour-coded via `deltaDir`.
 *
 * @returns The KPI tile element.
 */
export function StatPanel({
  label,
  icon,
  value,
  unit,
  secondary,
  delta,
  deltaDir = "flat",
  className = "",
  ...rest
}: StatPanelProps): React.JSX.Element {
  return (
    <div className={`ps-stat ${className}`} {...rest}>
      <span className="ps-stat__label">
        {icon}
        {label}
      </span>
      <span className="ps-stat__value">
        {value}
        {unit != null && <span className="ps-stat__unit">{unit}</span>}
      </span>
      {secondary != null && <span className="ps-stat__sub">{secondary}</span>}
      {delta != null && (
        <span className={`ps-stat__delta ps-stat__delta--${deltaDir}`}>
          {delta}
        </span>
      )}
    </div>
  );
}
