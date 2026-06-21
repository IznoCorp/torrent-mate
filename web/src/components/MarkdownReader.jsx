// Full-screen markdown reader sheet (helm PR 2-bis follow-up). Used by the Monitoring ticket detail
// to read a ticket's artifacts — brainstorming (issue body section), design, and plan files — as
// rendered markdown. Read-only; an overlay closed with ✕ / Escape / overlay click. The content is
// supplied by the caller (already fetched), so this component is purely presentational.
import React from "react";
import { renderMarkdown } from "../lib/markdown.js";
import { useT } from "../i18n/index.jsx";

const { Banner } = window.KanbanMateDesignSystem_2463ad;

export default function MarkdownReader({
  open,
  title,
  subtitle,
  content,
  loading = false,
  error = null,
  onClose,
}) {
  const { t } = useT();

  // Escape closes the sheet (keyboard parity with the ✕ button).
  React.useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const html = React.useMemo(
    () => (content ? renderMarkdown(content) : ""),
    [content],
  );

  if (!open) return null;

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 500,
        display: "grid",
        placeItems: "center",
        padding: "min(4vw, 28px)",
        background:
          "color-mix(in oklch, var(--gray-950, #000) 52%, transparent)",
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "100%",
          maxWidth: 860,
          maxHeight: "92vh",
          display: "flex",
          flexDirection: "column",
          background: "var(--card)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-lg)",
          boxShadow: "var(--shadow-lg)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: 12,
            padding: "12px 16px",
            borderBottom: "1px solid var(--border)",
          }}
        >
          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                fontFamily: "var(--font-display)",
                fontWeight: 600,
                fontSize: "var(--text-md)",
                color: "var(--foreground)",
              }}
            >
              {title}
            </div>
            {subtitle && (
              <div
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                  color: "var(--muted-foreground)",
                  marginTop: 2,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {subtitle}
              </div>
            )}
          </div>
          <button
            aria-label={t("common.close")}
            onClick={onClose}
            style={{
              border: "none",
              background: "transparent",
              cursor: "pointer",
              fontSize: 20,
              lineHeight: 1,
              color: "var(--muted-foreground)",
              padding: 2,
            }}
          >
            ✕
          </button>
        </div>
        <div
          style={{
            overflow: "auto",
            padding: "18px 20px 26px",
          }}
        >
          {loading ? (
            <div style={{ color: "var(--muted-foreground)" }}>
              {t("common.loading")}
            </div>
          ) : error ? (
            <Banner tone="error" title={t("monitor.file_error")}>
              {error}
            </Banner>
          ) : (
            <div
              className="km-markdown"
              style={{
                fontSize: 14,
                lineHeight: 1.6,
                color: "var(--foreground)",
                wordBreak: "break-word",
              }}
              dangerouslySetInnerHTML={{ __html: html }}
            />
          )}
        </div>
      </div>
    </div>
  );
}
