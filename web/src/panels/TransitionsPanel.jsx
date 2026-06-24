// Transitions panel — master-detail (DESIGN §13.3, no modal). Left: the order-sensitive
// (from_col → to_col) whitelist as a compact selectable list. Right: the selected transition's
// editor (inline, not a Dialog) with the markdown Write/Preview prompt editor. Real model fields:
// from_col / to_col / profile / prompt / script / advance / on_fail / permission_mode.
import React from "react";
import RichPromptEditor from "../components/RichPromptEditor.jsx";
import ConfigSaveBar from "../components/ConfigSaveBar.jsx";
import FilePicker from "../components/FilePicker.jsx";
import { MobileBack } from "../components/MobileMasterDetail.jsx";
import { PageIntro, Hint } from "../components/Help.jsx";
import { useT } from "../i18n/index.jsx";
import useIsMobile from "../useIsMobile.js";

const KMT = window.KanbanMateDesignSystem_2463ad;

const ADVANCE_OPTIONS = [
  "stop",
  "auto:Spec",
  "auto:Plan",
  "auto:Planned",
  "auto:PRCI",
  "auto:Review",
  "auto:Done",
];
const PERM_OPTIONS = ["auto", "default", "plan", "acceptEdits"];
const PROFILE_OPTIONS = ["", "docs", "prepare", "dev", "check"];

function fmtCol(v) {
  return Array.isArray(v) ? v.join(" · ") : v;
}

export default function TransitionsPanel({
  draft,
  update,
  findings = [],
  project,
  onSave,
  onValidate,
  saving = false,
  dirty = false,
}) {
  const { t } = useT();
  const isMobile = useIsMobile();
  const rows = draft.definition.transitions;
  const colKeys = draft.definition.columns.map((c) => c.key);
  // Desktop pre-selects the first row (unchanged); mobile starts on the list (no detail).
  const [sel, setSel] = React.useState(() =>
    typeof window !== "undefined" &&
    window.matchMedia?.("(max-width: 768px)").matches
      ? null
      : 0,
  );
  const [pickFile, setPickFile] = React.useState(false);
  const { Select, Input, Button, IconButton, KeyChip, Banner, ProfileTag } =
    KMT;

  const invalidIdx = new Set(
    findings
      .filter((f) => f.severity === "error")
      .map((f) => {
        const m = /transitions\[(\d+)\]/.exec(f.field || "");
        return m ? Number(m[1]) : -1;
      }),
  );

  const edit = sel != null && sel < rows.length ? rows[sel] : null;
  const val = (e) => (e && e.target ? e.target.value : e);
  const setField = (key, value) =>
    update((d) => {
      d.definition.transitions[sel][key] = value;
      return d;
    });

  const addRow = () =>
    update((d) => {
      d.definition.transitions.push({
        from_col: colKeys[0] || "",
        to_col: colKeys[0] || "",
        profile: "",
        prompt: null,
        script: null,
        advance: "stop",
        on_fail: "",
        permission_mode: "auto",
      });
      return d;
    });
  const removeRow = (i) =>
    update((d) => {
      d.definition.transitions.splice(i, 1);
      return d;
    });

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto" }}>
      <PageIntro title={t("transitions.intro_title")} scope="board">
        {t("transitions.intro_body")}
      </PageIntro>
      <Banner tone="neutral" style={{ marginBottom: 12 }}>
        <span>{t("transitions.banner")}</span>
      </Banner>

      {/* Legend for the per-row status dots. */}
      <div
        style={{
          display: "flex",
          gap: 18,
          marginBottom: 14,
          fontSize: 12,
          color: "var(--muted-foreground)",
        }}
      >
        <LegendDot
          color="var(--col-agent-solid, var(--primary))"
          label={t("transitions.tip_launch")}
        />
        <LegendDot
          color="var(--col-reactive-solid, var(--border))"
          label={t("transitions.tip_script")}
        />
        <LegendDot color="var(--border)" label={t("transitions.tip_noop")} />
      </div>

      <div
        style={{
          display: isMobile ? "block" : "grid",
          gridTemplateColumns: isMobile ? undefined : "320px 1fr",
          gap: 16,
          alignItems: "start",
        }}
      >
        {isMobile && sel != null && (
          <MobileBack
            onClick={() => setSel(null)}
            label={
              edit ? `${fmtCol(edit.from_col)} → ${fmtCol(edit.to_col)}` : ""
            }
          />
        )}
        {(!isMobile || sel == null) && (
          /* master: transition list */
          <div
            style={{
              background: "var(--card)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-lg)",
              overflow: "hidden",
              boxShadow: "var(--shadow-xs)",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "10px 12px",
                borderBottom: "1px solid var(--border)",
                background: "var(--muted)",
              }}
            >
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                  letterSpacing: ".06em",
                  textTransform: "uppercase",
                  color: "var(--muted-foreground)",
                  flex: 1,
                }}
              >
                {t("transitions.rows", { n: rows.length })}
              </span>
              <Button variant="secondary" size="sm" onClick={addRow}>
                {t("common.add")}
              </Button>
            </div>
            <div style={{ maxHeight: "65vh", overflow: "auto" }}>
              {rows.map((r, i) => {
                const on = sel === i;
                const bad = invalidIdx.has(i);
                return (
                  <button
                    key={i}
                    onClick={() => setSel(i)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      width: "100%",
                      textAlign: "left",
                      border: "none",
                      borderLeft: `3px solid ${bad ? "var(--destructive)" : on ? "var(--primary)" : "transparent"}`,
                      borderBottom: "1px solid var(--border)",
                      background: on ? "var(--muted)" : "transparent",
                      cursor: "pointer",
                      padding: "9px 12px",
                    }}
                  >
                    <KMT.Tooltip
                      style={{ flex: "none" }}
                      label={
                        r.prompt
                          ? t("transitions.tip_launch")
                          : r.script
                            ? t("transitions.tip_script")
                            : t("transitions.tip_noop")
                      }
                    >
                      <span
                        style={{
                          width: 6,
                          height: 6,
                          borderRadius: "50%",
                          flex: "none",
                          background: r.prompt
                            ? "var(--col-agent-solid, var(--primary))"
                            : r.script
                              ? "var(--col-reactive-solid, var(--border))"
                              : "var(--border)",
                        }}
                      />
                    </KMT.Tooltip>
                    <span
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: 12,
                        color: "var(--foreground)",
                        flex: 1,
                        minWidth: 0,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {fmtCol(r.from_col)} → {fmtCol(r.to_col)}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        )}
        {(!isMobile || sel != null) && (
          <div
            style={{
              background: "var(--card)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-lg)",
              boxShadow: "var(--shadow-xs)",
              padding: 18,
            }}
          >
            {!edit ? (
              <div
                style={{
                  color: "var(--muted-foreground)",
                  padding: "40px 0",
                  textAlign: "center",
                }}
              >
                {t("transitions.select_hint")}
              </div>
            ) : (
              <div
                style={{ display: "flex", flexDirection: "column", gap: 16 }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span
                    style={{
                      fontFamily: "var(--font-display)",
                      fontWeight: 600,
                      fontSize: "var(--text-md)",
                    }}
                  >
                    {fmtCol(edit.from_col)} → {fmtCol(edit.to_col)}
                  </span>
                  {edit.profile ? <ProfileTag profile={edit.profile} /> : null}
                  <span style={{ flex: 1 }} />
                  <KMT.Tooltip label={t("common.remove")}>
                    <IconButton
                      aria-label={t("common.remove")}
                      size="sm"
                      onClick={() => removeRow(sel)}
                    >
                      ✕
                    </IconButton>
                  </KMT.Tooltip>
                </div>

                {invalidIdx.has(sel) && (
                  <Banner tone="error" title={t("transitions.row_blocks_save")}>
                    {
                      findings.find((f) =>
                        (f.field || "").startsWith(`transitions[${sel}]`),
                      )?.message
                    }
                  </Banner>
                )}

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: isMobile ? "1fr" : "1fr auto 1fr",
                    gap: 12,
                    alignItems: "start",
                  }}
                >
                  <DField
                    label={t("transitions.labels.from_col")}
                    tech="from_col"
                    hint={t("transitions.fields.from_col")}
                    required
                  >
                    <Select
                      options={["*", ...colKeys]}
                      value={Array.isArray(edit.from_col) ? "*" : edit.from_col}
                      onChange={(e) => setField("from_col", val(e))}
                      style={{ width: "100%" }}
                    />
                  </DField>
                  {/* Arrow aligned with the SELECT row (pushed past the label line) — the
                    differing hint heights no longer shift the selects (alignItems:start).
                    Hidden on mobile, where the field grid collapses to a single column. */}
                  {!isMobile && (
                    <span
                      style={{
                        paddingTop: 28,
                        color: "var(--col-agent-fg)",
                        fontFamily: "var(--font-mono)",
                        fontWeight: 600,
                        fontSize: 16,
                      }}
                    >
                      →
                    </span>
                  )}
                  <DField
                    label={t("transitions.labels.to_col")}
                    tech="to_col"
                    hint={t("transitions.fields.to_col")}
                    required
                  >
                    <Select
                      options={colKeys}
                      value={
                        Array.isArray(edit.to_col) ? colKeys[0] : edit.to_col
                      }
                      onChange={(e) => setField("to_col", val(e))}
                      style={{ width: "100%" }}
                    />
                  </DField>
                </div>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr 1fr",
                    gap: 12,
                    alignItems: "start",
                  }}
                >
                  <DField
                    label={t("transitions.labels.profile")}
                    tech="profile"
                    hint={t("transitions.fields.profile")}
                  >
                    <Select
                      options={PROFILE_OPTIONS}
                      value={edit.profile || ""}
                      onChange={(e) => setField("profile", val(e))}
                      style={{ width: "100%" }}
                    />
                  </DField>
                  <DField
                    label={t("transitions.labels.permission_mode")}
                    tech="permission_mode"
                    hint={t("transitions.fields.permission_mode")}
                  >
                    <Select
                      options={PERM_OPTIONS}
                      value={edit.permission_mode}
                      onChange={(e) => setField("permission_mode", val(e))}
                      invalid={invalidIdx.has(sel)}
                      style={{ width: "100%" }}
                    />
                  </DField>
                  <DField
                    label={t("transitions.labels.advance")}
                    tech="advance"
                    hint={t("transitions.fields.advance")}
                  >
                    <Select
                      options={ADVANCE_OPTIONS}
                      value={edit.advance}
                      onChange={(e) => setField("advance", val(e))}
                      style={{ width: "100%" }}
                    />
                  </DField>
                </div>

                <DField
                  label={t("transitions.labels.on_fail")}
                  tech="on_fail"
                  hint={t("transitions.fields.on_fail")}
                >
                  <Select
                    options={["", "move:Blocked", "rollback"]}
                    value={edit.on_fail || ""}
                    onChange={(e) => setField("on_fail", val(e))}
                    style={{ width: 200 }}
                  />
                </DField>

                <DField
                  label={t("transitions.labels.script")}
                  tech="script"
                  hint={t("transitions.fields.script")}
                >
                  <div
                    style={{ display: "flex", gap: 8, alignItems: "center" }}
                  >
                    <Input
                      value={edit.script || ""}
                      onChange={(e) =>
                        setField("script", e.target.value || null)
                      }
                      placeholder={t("transitions.script_placeholder")}
                      style={{ flex: 1 }}
                    />
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => setPickFile(true)}
                    >
                      {t("transitions.browse")}
                    </Button>
                  </div>
                </DField>

                <DField
                  label={t("transitions.prompt_label")}
                  tech="prompt"
                  hint={t("transitions.prompt_hint")}
                >
                  <RichPromptEditor
                    value={edit.prompt || ""}
                    onChange={(v) => setField("prompt", v || null)}
                  />
                </DField>

                <div
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 11,
                    color: "var(--muted-foreground)",
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                  }}
                >
                  {t("transitions.launch_label")}{" "}
                  {edit.prompt ? (
                    <span
                      style={{ color: "var(--col-agent-fg)", fontWeight: 600 }}
                    >
                      {t("transitions.launch_fires")}
                    </span>
                  ) : (
                    <span>{t("transitions.launch_noop")}</span>
                  )}{" "}
                  ·{" "}
                  <span style={{ color: "var(--health-blocked-fg)" }}>
                    {t("transitions.bypass_never")}
                  </span>
                </div>

                {/* Explicit save/validate — shared component; fixed to the screen bottom on mobile
                    so it stays under the thumb. Saves the whole config draft (shared dirty flag). */}
                <ConfigSaveBar
                  onSave={onSave}
                  onValidate={onValidate}
                  saving={saving}
                  dirty={dirty}
                />
              </div>
            )}
          </div>
        )}
      </div>

      <FilePicker
        open={pickFile}
        project={project}
        onClose={() => setPickFile(false)}
        onPick={(rel) => setField("script", rel)}
      />
    </div>
  );
}

function LegendDot({ color, label }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: color,
          flex: "none",
        }}
      />
      {label}
    </span>
  );
}

function DField({ label, tech, hint, required = false, children }) {
  const { t } = useT();
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <span
        style={{
          display: "flex",
          alignItems: "baseline",
          gap: 6,
          flexWrap: "wrap",
        }}
      >
        <span
          style={{ fontSize: 12, fontWeight: 600, color: "var(--foreground)" }}
        >
          {label}
          {required && (
            <KMT.Tooltip label={t("common.required")}>
              <span
                aria-label={t("common.required")}
                style={{ color: "var(--destructive)", marginLeft: 3 }}
              >
                *
              </span>
            </KMT.Tooltip>
          )}
        </span>
        {tech && (
          <code
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 10,
              color: "var(--muted-foreground)",
            }}
          >
            {tech}
          </code>
        )}
      </span>
      {children}
      {hint && <Hint>{hint}</Hint>}
    </label>
  );
}
