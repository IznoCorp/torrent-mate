// Self-documentation primitives (DESIGN §13 operator feedback): every page carries a PageIntro
// explaining what it is and what it's for; every input carries a Hint describing it. The interface
// is its own documentation.
import React from "react";
import { Info, ChevronDown, ChevronRight } from "lucide-react";
import { useT } from "../i18n/index.jsx";

// A compact, collapsible explanatory header at the top of a panel. Collapsed by default (just the
// title + scope on one line) so it stays out of the way; the operator expands it for the full
// description. The open/closed choice is remembered across panels and reloads (#47 polish).
export function PageIntro({ title, scope, children }) {
  const { t } = useT();
  const daemon = scope === "daemon";
  const accent = daemon
    ? "var(--health-waiting-fg, #b45309)"
    : "var(--muted-foreground)";
  const [open, setOpen] = React.useState(() => {
    try {
      return localStorage.getItem("bridge.intro.open") === "1";
    } catch (_) {
      return false;
    }
  });
  const toggle = () =>
    setOpen((v) => {
      const next = !v;
      try {
        localStorage.setItem("bridge.intro.open", next ? "1" : "0");
      } catch (_) {
        /* storage may be unavailable */
      }
      return next;
    });
  return (
    <div
      style={{
        marginBottom: 14,
        borderRadius: "var(--radius-md)",
        background: "var(--card)",
        border: "1px solid var(--border)",
      }}
    >
      <button
        onClick={toggle}
        aria-expanded={open}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          width: "100%",
          textAlign: "left",
          border: "none",
          background: "transparent",
          cursor: "pointer",
          padding: "8px 12px",
          color: "var(--foreground)",
        }}
      >
        <Info
          size={14}
          strokeWidth={1.9}
          style={{ color: accent, flex: "none" }}
        />
        <span
          style={{
            fontFamily: "var(--font-display)",
            fontWeight: 600,
            fontSize: "var(--text-sm)",
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
            color: accent,
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-sm)",
            padding: "1px 6px",
          }}
        >
          {daemon ? t("common.daemon_scope") : t("common.per_project")}
        </span>
        <span
          style={{
            marginLeft: "auto",
            display: "flex",
            color: "var(--muted-foreground)",
          }}
        >
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </span>
      </button>
      {open && (
        <div
          style={{
            fontSize: 12.5,
            color: "var(--muted-foreground)",
            lineHeight: 1.5,
            padding: "0 12px 10px 34px",
          }}
        >
          {children}
        </div>
      )}
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
