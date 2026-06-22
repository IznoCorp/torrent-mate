import React from "react";

// Minimal self-contained loading spinner.
//
// The design-system bundle (window.KanbanMateDesignSystem_*) exports NO `Spinner` primitive — it
// never has (verified against origin/main). bosun's AdminPanel/WizardPanel destructured a
// non-existent `Spinner` from the DS global, so at render `<Spinner/>` was `undefined` →
// React error #130 ("element type is undefined") → blank page. This local component replaces it.
//
// SVG + <animateTransform> so it is fully self-contained (no global CSS keyframe dependency) and
// inherits the surrounding text colour via `currentColor`.
export default function Spinner({ size = 16 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      role="status"
      aria-label="loading"
      style={{ display: "inline-block", verticalAlign: "middle" }}
    >
      <circle
        cx="12"
        cy="12"
        r="9"
        fill="none"
        stroke="currentColor"
        strokeWidth="3"
        strokeOpacity="0.25"
      />
      <path
        d="M12 3 a9 9 0 0 1 9 9"
        fill="none"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
      >
        <animateTransform
          attributeName="transform"
          type="rotate"
          from="0 12 12"
          to="360 12 12"
          dur="0.8s"
          repeatCount="indefinite"
        />
      </path>
    </svg>
  );
}
