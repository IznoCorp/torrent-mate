// Mobile master-detail support (DESIGN §4.2). Panels render their desktop side-by-side grid as a
// single column on mobile and show EITHER the list OR the detail (with this back button), driven by
// their existing selection state — so on a phone the detail is full-screen and ← returns to the list.
import React from "react";
import { useT } from "../i18n/index.jsx";

export function MobileBack({ onClick, label }) {
  const { t } = useT();
  return (
    <button
      onClick={onClick}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        border: "none",
        background: "transparent",
        cursor: "pointer",
        color: "var(--foreground)",
        fontSize: 14,
        padding: "2px 0 12px",
      }}
    >
      ← {label || t("common.back")}
    </button>
  );
}
