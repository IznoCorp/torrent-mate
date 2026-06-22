// MarkdownField — a GitHub-PR-style markdown editor reused for every description / prompt input.
// Write / Preview tabs, a compact formatting toolbar, and a tall, resizable textarea. The preview is
// sanitised (DOMPurify via renderMarkdown). Mobile-optimised: 16px font (no iOS zoom-on-focus) and a
// viewport-relative height so it fills the screen.
import React from "react";
import { renderMarkdown } from "../lib/markdown.js";
import { useT } from "../i18n/index.jsx";
import useIsMobile from "../useIsMobile.js";

const { SegmentedControl } = window.KanbanMateDesignSystem_2463ad;

// Wrap/insert markdown around the textarea's current selection, then restore a useful selection.
function applyFormat(textarea, value, onChange, kind) {
  if (!textarea) return;
  const start = textarea.selectionStart ?? value.length;
  const end = textarea.selectionEnd ?? value.length;
  const sel = value.slice(start, end);
  let before = "";
  let after = "";
  let placeholder = sel;
  switch (kind) {
    case "bold":
      before = "**";
      after = "**";
      placeholder = sel || "bold";
      break;
    case "italic":
      before = "_";
      after = "_";
      placeholder = sel || "italic";
      break;
    case "code":
      before = "`";
      after = "`";
      placeholder = sel || "code";
      break;
    case "heading":
      before = "### ";
      placeholder = sel || "Heading";
      break;
    case "list":
      before = "- ";
      placeholder = sel || "item";
      break;
    case "link":
      before = "[";
      after = "](url)";
      placeholder = sel || "text";
      break;
    default:
      break;
  }
  const next =
    value.slice(0, start) + before + placeholder + after + value.slice(end);
  onChange(next);
  // Re-select the placeholder so the operator can immediately type over it (after React re-renders).
  requestAnimationFrame(() => {
    textarea.focus();
    const s = start + before.length;
    textarea.setSelectionRange(s, s + placeholder.length);
  });
}

const TOOLBAR = [
  ["heading", "H", {}],
  ["bold", "B", { fontWeight: 700 }],
  ["italic", "I", { fontStyle: "italic" }],
  ["list", "•", {}],
  ["link", "↗", {}],
  ["code", "</>", { fontFamily: "var(--font-mono)", fontSize: 11 }],
];

/**
 * @param {{
 *   value: string, onChange: (v: string) => void, placeholder?: string,
 *   minRows?: number, autoFocus?: boolean, mono?: boolean,
 * }} props
 */
export default function MarkdownField({
  value,
  onChange,
  placeholder,
  minRows = 10,
  autoFocus = false,
  mono = false,
}) {
  const { t } = useT();
  const isMobile = useIsMobile();
  const [tab, setTab] = React.useState("write");
  const taRef = React.useRef(null);
  const text = value || "";

  const previewHtml = React.useMemo(
    () =>
      tab === "preview"
        ? renderMarkdown(text || `*${t("md.nothing", "Nothing to preview")}*`)
        : "",
    [tab, text, t],
  );

  // Fill the screen on mobile; a generous fixed-ish band on desktop (still resizable by the handle).
  const minHeight = isMobile ? "44vh" : `${Math.round(minRows * 1.55 + 1)}em`;
  const maxHeight = isMobile ? "72vh" : "62vh";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          flexWrap: "wrap",
        }}
      >
        <SegmentedControl
          options={[
            { value: "write", label: t("md.write", "Write") },
            { value: "preview", label: t("md.preview", "Preview") },
          ]}
          value={tab}
          onChange={setTab}
          style={{ alignSelf: "flex-start" }}
        />
        {tab === "write" && (
          <div style={{ display: "flex", gap: 3 }}>
            {TOOLBAR.map(([kind, label, st]) => (
              <button
                key={kind}
                type="button"
                title={kind}
                onMouseDown={(e) => e.preventDefault()} // keep the textarea selection
                onClick={() => applyFormat(taRef.current, text, onChange, kind)}
                style={{
                  minWidth: 30,
                  height: 30,
                  padding: "0 7px",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius-sm)",
                  background: "var(--card)",
                  color: "var(--muted-foreground)",
                  cursor: "pointer",
                  fontSize: 13,
                  lineHeight: 1,
                }}
              >
                <span style={st}>{label}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {tab === "write" ? (
        <textarea
          ref={taRef}
          value={text}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          autoFocus={autoFocus}
          spellCheck
          style={{
            width: "100%",
            minHeight,
            maxHeight,
            resize: "vertical",
            boxSizing: "border-box",
            padding: "10px 12px",
            fontFamily: mono ? "var(--font-mono)" : "var(--font-sans)",
            // 16px on mobile prevents iOS Safari from zooming the viewport when the field focuses.
            fontSize: isMobile ? 16 : 13.5,
            lineHeight: 1.55,
            color: "var(--foreground)",
            background: "var(--card)",
            border: "1px solid var(--input)",
            borderRadius: "var(--radius-md)",
            outline: "none",
          }}
        />
      ) : (
        <div
          className="km-timeline-md"
          style={{
            minHeight,
            maxHeight,
            overflow: "auto",
            padding: "10px 14px",
            fontSize: 13.5,
            lineHeight: 1.6,
            color: "var(--foreground)",
            background: "var(--card)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-md)",
          }}
          dangerouslySetInnerHTML={{ __html: previewHtml }}
        />
      )}
    </div>
  );
}
