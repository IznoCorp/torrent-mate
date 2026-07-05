/* eslint-disable no-restricted-syntax --
 * DS-adherence exception (deliberate): StagingBanner is a theme-independent OPS
 * overlay, not product UI. Its cyan staging accent and fixed pixel dimensions
 * must render identically regardless of the active DS theme/tokens — precisely
 * so "you are on staging" is unmistakable and never blends into the product
 * chrome. Mirrors KanbanMate's StagingBanner, which hardcodes the same way.
 */
/**
 * Visual staging indicator.
 *
 * On the staging instance (host contains "staging", e.g.
 * `tm-staging.iznogoudatall.xyz`, or the loopback staging port `8711`) this
 * renders an unmissable cyan frame around the whole viewport plus a top badge —
 * so you know AT A GLANCE you are on staging (which runs against the REAL config
 * and data). It is a fixed, `pointer-events: none` overlay: it never intercepts
 * clicks and causes NO layout reflow. In prod it renders `null`, so the prod UI
 * is byte-for-byte unchanged. Mirrors KanbanMate's `StagingBanner`.
 */
import type { JSX } from "react";

import { isStaging } from "@/lib/env";

/** Staging accent — cyan, deliberately distinct from the amber production brand. */
const STAGING_ACCENT = "#22D3EE";

/**
 * StagingBanner — a fixed cyan frame + badge shown only on the staging host.
 *
 * @returns The overlay element on staging, or `null` in production.
 */
export function StagingBanner(): JSX.Element | null {
  if (!isStaging()) {
    return null;
  }
  return (
    <div
      aria-hidden="true"
      style={{ position: "fixed", inset: 0, zIndex: 99999, pointerEvents: "none" }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          border: `3px solid ${STAGING_ACCENT}`,
          boxSizing: "border-box",
        }}
      />
      <div
        style={{
          position: "absolute",
          top: 0,
          left: "50%",
          transform: "translateX(-50%)",
          background: STAGING_ACCENT,
          color: "#0a1416",
          fontFamily: "var(--font-mono, ui-monospace, monospace)",
          fontWeight: 700,
          fontSize: 12,
          letterSpacing: ".08em",
          padding: "3px 14px",
          borderRadius: "0 0 8px 8px",
          boxShadow: "0 1px 8px rgba(0,0,0,.35)",
          whiteSpace: "nowrap",
        }}
      >
        ● STAGING — DONNÉES RÉELLES
      </div>
    </div>
  );
}
