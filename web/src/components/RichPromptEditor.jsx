// Rich prompt editor (DESIGN §13.4) — a GitHub-style Write / Preview field over ONE box.
// Write: markdown source + known-placeholder chips + {{placeholder}} validation. Preview: the
// markdown rendered (via `marked`) in the SAME box, with {{placeholders}} still highlighted
// (known vs unknown) so the operator sees both formatting and binding. The known-placeholder set
// is fetched from the server (GET /api/placeholders) so it never drifts from the engine.
import React from "react";
import { renderMarkdown } from "../lib/markdown.js";
import CodeMirror from "@uiw/react-codemirror";
import { markdown, markdownLanguage } from "@codemirror/lang-markdown";
import { languages } from "@codemirror/language-data";
import { EditorView } from "@codemirror/view";
import * as api from "../api.js";
import { useT } from "../i18n/index.jsx";
import useIsMobile from "../useIsMobile.js";

const { KeyChip, Banner, SegmentedControl, Tooltip } =
  window.KanbanMateDesignSystem_2463ad;
const TOKEN = /\{\{\s*([\w.]+)\s*\}\}/g;

function editDistance(a, b) {
  const m = Array.from({ length: a.length + 1 }, (_, i) => [
    i,
    ...Array(b.length).fill(0),
  ]);
  for (let j = 0; j <= b.length; j++) m[0][j] = j;
  for (let i = 1; i <= a.length; i++) {
    for (let j = 1; j <= b.length; j++) {
      m[i][j] = Math.min(
        m[i - 1][j] + 1,
        m[i][j - 1] + 1,
        m[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1),
      );
    }
  }
  return m[a.length][b.length];
}

function suggest(name, known) {
  let best = null;
  let bd = 99;
  for (const k of known) {
    const d = editDistance(name, k);
    if (d < bd) {
      bd = d;
      best = k;
    }
  }
  return bd <= 3 ? best : null;
}

// Wrap every {{placeholder}} in the (already markdown-rendered) HTML with a highlight span.
// {{ }} are literal text — they survive markdown rendering — so a post-pass is safe.
function highlightPlaceholders(html, known, knownNames) {
  return html.replace(TOKEN, (full, key) => {
    const head = key.split(".")[0];
    const bad = knownNames.length && !known[head];
    return `<span class="ph${bad ? " bad" : ""}">${full}</span>`;
  });
}

// CodeMirror extensions: markdown highlighting + soft line wrapping. Built once (module scope).
const CM_EXTENSIONS = [
  markdown({ base: markdownLanguage, codeLanguages: languages }),
  EditorView.lineWrapping,
];

export default function RichPromptEditor({ value, onChange }) {
  const { t } = useT();
  const isMobile = useIsMobile();
  const [known, setKnown] = React.useState({});
  const [tab, setTab] = React.useState("write");
  const cmRef = React.useRef(null);
  // Desktop: a generous band. Mobile: CAP the height at half the screen so the placeholder chips
  // (rendered BELOW the editor) stay reachable — a long prompt scrolls inside the editor instead of
  // pushing the chips off-screen.
  const minH = isMobile ? "26vh" : "320px";
  const maxH = isMobile ? "50vh" : "62vh";

  React.useEffect(() => {
    api
      .getPlaceholders()
      .then((r) => {
        const map = {};
        (r.placeholders || []).forEach((p) => (map[p.name] = p.description));
        setKnown(map);
      })
      .catch(() => setKnown({}));
  }, []);

  const text = value || "";
  const knownNames = Object.keys(known);

  const unknowns = [];
  if (knownNames.length) {
    let m;
    TOKEN.lastIndex = 0;
    while ((m = TOKEN.exec(text))) {
      const head = m[1].split(".")[0];
      if (!known[head] && !unknowns.includes(head)) unknowns.push(head);
    }
  }

  // Insert a placeholder at the caret (CodeMirror), or append as a fallback.
  const insert = (chip) => {
    const view = cmRef.current?.view;
    if (view) {
      const { from, to } = view.state.selection.main;
      view.dispatch({
        changes: { from, to, insert: chip },
        selection: { anchor: from + chip.length },
      });
      view.focus();
    } else {
      onChange((text || "") + chip);
    }
  };

  const previewHtml = React.useMemo(() => {
    if (tab !== "preview") return "";
    const rendered = renderMarkdown(text || t("prompt.no_prompt_md"));
    return highlightPlaceholders(rendered, known, knownNames);
  }, [tab, text, known]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <SegmentedControl
        options={[
          { value: "write", label: t("prompt.write") },
          { value: "preview", label: t("prompt.preview") },
        ]}
        value={tab}
        onChange={setTab}
        style={{ alignSelf: "flex-start" }}
      />

      {tab === "write" ? (
        <div
          className="cm-prompt"
          style={{
            border: "1px solid var(--input)",
            borderRadius: "var(--radius-md)",
            overflow: "hidden",
          }}
        >
          <CodeMirror
            ref={cmRef}
            value={text}
            onChange={(v) => onChange(v)}
            extensions={CM_EXTENSIONS}
            placeholder={t("prompt.placeholder")}
            minHeight={minH}
            maxHeight={maxH}
            basicSetup={{
              lineNumbers: true,
              foldGutter: false,
              highlightActiveLine: true,
              autocompletion: false,
            }}
          />
        </div>
      ) : (
        <div
          className="md-preview"
          style={{
            fontSize: 13.5,
            lineHeight: 1.6,
            padding: 14,
            background: "var(--card)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-md)",
            color: "var(--foreground)",
            minHeight: minH,
            maxHeight: maxH,
            overflow: "auto",
          }}
          dangerouslySetInnerHTML={{ __html: previewHtml }}
        />
      )}

      {/* Placeholder cloud — BELOW the editor (operator). Each unit is a full tap target that
          inserts the token at the caret; the description is always visible (no hover needed), so it
          works on mobile where chips wrap to full-width rows. */}
      {tab === "write" && knownNames.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 10,
              letterSpacing: ".06em",
              textTransform: "uppercase",
              color: "var(--muted-foreground)",
            }}
          >
            {t("prompt.placeholders_label")}
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {knownNames.map((n) => (
              <Tooltip
                key={n}
                label={t("prompt.insert")}
                style={{
                  flex: isMobile ? "1 1 100%" : "0 1 auto",
                  maxWidth: "100%",
                }}
              >
                <button
                  type="button"
                  onClick={() => insert(`{{${n}}}`)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 7,
                    width: "100%",
                    maxWidth: "100%",
                    textAlign: "left",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--radius-md)",
                    background: "var(--card)",
                    padding: "7px 10px",
                    cursor: "pointer",
                    minHeight: 40,
                  }}
                >
                  <KeyChip>{`{{${n}}}`}</KeyChip>
                  <span
                    style={{
                      fontSize: 12,
                      color: "var(--muted-foreground)",
                      lineHeight: 1.4,
                      minWidth: 0,
                    }}
                  >
                    {known[n]}
                  </span>
                </button>
              </Tooltip>
            ))}
          </div>
        </div>
      )}

      {unknowns.length > 0 && (
        <Banner
          tone="error"
          title={t("prompt.unknown_count", { n: unknowns.length })}
        >
          {unknowns.map((u) => {
            const dym = suggest(u, knownNames);
            return (
              <div key={u}>
                <code>{`{{${u}}}`}</code>
                {dym
                  ? t("prompt.did_you_mean", { name: dym })
                  : t("prompt.not_known")}
              </div>
            );
          })}
        </Banner>
      )}
    </div>
  );
}
