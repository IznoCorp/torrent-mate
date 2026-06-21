// Visual staging indicator.
//
// On the staging instance (host contains "staging", e.g. km-staging.iznogoudatall.xyz,
// or the loopback staging port 8797) this renders an unmissable orange frame around
// the whole viewport plus a top badge — so you know AT A GLANCE you are on staging,
// which acts on the REAL prod board. It is a fixed, pointer-events:none overlay: it
// never intercepts clicks and causes NO layout reflow. In prod it renders null, so
// the prod UI is byte-for-byte unchanged.
import React from "react";

function onStaging() {
  if (typeof window === "undefined") return false;
  const host = window.location.hostname || "";
  return /staging/i.test(host) || window.location.port === "8797";
}

export default function StagingBanner() {
  if (!onStaging()) return null;
  const accent = "#f59e0b"; // amber — distinct from the brand green
  return (
    <div
      aria-hidden="true"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 99999,
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          border: `3px solid ${accent}`,
          boxSizing: "border-box",
        }}
      />
      <div
        style={{
          position: "absolute",
          top: 0,
          left: "50%",
          transform: "translateX(-50%)",
          background: accent,
          color: "#1a1a1a",
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
        ● STAGING — BOARD RÉEL
      </div>
    </div>
  );
}
