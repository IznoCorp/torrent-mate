// Self-documentation primitives (DESIGN §13 operator feedback): every page carries a PageIntro
// explaining what it is and what it's for; every input carries a Hint describing it. The interface
// is its own documentation.
import React from "react";
import { useT } from "../i18n/index.jsx";

// A short explanatory block at the top of a panel. `scope` tags whether the page is per-board or
// daemon-wide so the operator sees it immediately.
export function PageIntro({ title, scope, children }) {
  const { t } = useT();
  const daemon = scope === "daemon";
  return (
    <div
      style={{
        marginBottom: 18,
        padding: "12px 14px",
        borderRadius: "var(--radius-md)",
        background: "var(--muted)",
        border: "1px solid var(--border)",
        borderLeft: `3px solid ${daemon ? "var(--health-waiting-fg, #b45309)" : "var(--primary)"}`,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 4,
        }}
      >
        <span
          style={{
            fontFamily: "var(--font-display)",
            fontWeight: 600,
            fontSize: "var(--text-md)",
          }}
        >
          {title}
        </span>
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 10,
            letterSpacing: ".04em",
            textTransform: "uppercase",
            color: daemon
              ? "var(--health-waiting-fg, #b45309)"
              : "var(--muted-foreground)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-sm)",
            padding: "1px 6px",
          }}
        >
          {daemon ? t("common.daemon_scope") : t("common.per_project")}
        </span>
      </div>
      <div
        style={{
          fontSize: 13,
          color: "var(--muted-foreground)",
          lineHeight: 1.55,
        }}
      >
        {children}
      </div>
    </div>
  );
}

// A small description shown directly under an input.
export function Hint({ children }) {
  return (
    <span
      style={{
        fontSize: 11.5,
        color: "var(--muted-foreground)",
        lineHeight: 1.45,
      }}
    >
      {children}
    </span>
  );
}
