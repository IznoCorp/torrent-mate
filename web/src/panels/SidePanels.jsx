// Defaults, Validation, and YAML-preview panels (ported from the kit ui_kit).
// Defaults binds to draft.definition.defaults; Validation renders the server findings;
// YAML preview reads the authoritative server-rendered output (GET /api/config/render).
import React from "react";
import * as api from "../api.js";
import { PageIntro } from "../components/Help.jsx";
import { useT } from "../i18n/index.jsx";

const KMS = window.KanbanMateDesignSystem_2463ad;

// ---- Defaults: board-wide concurrency_cap + move_rate_limit_per_hour ----
export function DefaultsPanel({ draft, update }) {
  const { t } = useT();
  const { Card, Input, Banner, KeyChip } = KMS;
  const d = draft.definition.defaults;
  const setNum = (key, raw) =>
    update((draftClone) => {
      const n = parseInt(raw, 10);
      draftClone.definition.defaults[key] = Number.isNaN(n) ? raw : n;
      return draftClone;
    });
  return (
    <div
      style={{
        maxWidth: 620,
        margin: "0 auto",
        display: "flex",
        flexDirection: "column",
        gap: 16,
      }}
    >
      <PageIntro title={t("defaults.intro_title")} scope="board">
        {t("defaults.intro_body")}
      </PageIntro>
      <Card padding="none">
        <SettingRow
          label={t("defaults.concurrency_cap")}
          hint={t("defaults.concurrency_cap_hint")}
        >
          <Input
            type="number"
            value={d.concurrency_cap}
            onChange={(e) => setNum("concurrency_cap", e.target.value)}
            mono
            style={{ width: 88 }}
          />
        </SettingRow>
        <div style={{ height: 1, background: "var(--border)" }} />
        <SettingRow
          label={t("defaults.rate_limit")}
          hint={t("defaults.rate_limit_hint")}
        >
          <Input
            type="number"
            value={d.move_rate_limit_per_hour}
            onChange={(e) => setNum("move_rate_limit_per_hour", e.target.value)}
            mono
            style={{ width: 88 }}
          />
        </SettingRow>
      </Card>
    </div>
  );
}

function SettingRow({ label, hint, children }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 16,
        padding: "14px 18px",
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "var(--text-sm)",
            fontWeight: 600,
            color: "var(--foreground)",
          }}
        >
          {label}
        </div>
        <div
          style={{
            fontSize: 12,
            color: "var(--muted-foreground)",
            marginTop: 3,
            lineHeight: 1.45,
          }}
        >
          {hint}
        </div>
      </div>
      {children}
    </div>
  );
}

// ---- Validation: V1–V11 findings; errors block save, warnings advisory ----
export function ValidationPanel({ findings = [], onGoto }) {
  const { t } = useT();
  const { FindingItem, Banner } = KMS;
  const errs = findings.filter((f) => f.severity === "error");
  const warns = findings.filter((f) => f.severity === "warning");
  return (
    <div
      style={{
        maxWidth: 760,
        margin: "0 auto",
        display: "flex",
        flexDirection: "column",
        gap: 14,
      }}
    >
      <PageIntro title={t("validation.intro_title")} scope="board">
        {t("validation.intro_body")}
      </PageIntro>
      {errs.length > 0 ? (
        <Banner
          tone="error"
          title={t("validation.errors_block", { n: errs.length })}
        >
          {t("validation.errors_block_body")}
        </Banner>
      ) : (
        // Compact integrated "valid" note — the full success Banner was too tall for one line.
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            fontSize: 12,
            color: "var(--muted-foreground)",
          }}
        >
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: "var(--health-active-fg, #1f9d54)",
              flexShrink: 0,
            }}
          />
          <span>
            <strong style={{ color: "var(--foreground)", fontWeight: 600 }}>
              {t("validation.valid_title")}
            </strong>{" "}
            — {t("validation.valid_body")}
          </span>
        </div>
      )}
      {warns.length > 0 && (
        <div
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 11,
            letterSpacing: ".06em",
            textTransform: "uppercase",
            color: "var(--muted-foreground)",
            marginTop: 4,
          }}
        >
          {t("validation.advisory", { n: warns.length })}
        </div>
      )}
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {findings.map((f, i) => (
          <FindingItem
            key={i}
            severity={f.severity}
            field={f.field}
            message={f.message}
            onClick={() => onGoto && onGoto(f.field)}
          />
        ))}
      </div>
    </div>
  );
}

// ---- YAML preview: read-only, server-rendered (authoritative) ----
export function YamlPanel({ project }) {
  const { t } = useT();
  const { SegmentedControl, Banner } = KMS;
  const [file, setFile] = React.useState("transitions.yml");
  const [rendered, setRendered] = React.useState(null);
  const [error, setError] = React.useState(null);

  React.useEffect(() => {
    api
      .renderConfig(project)
      .then(setRendered)
      .catch((e) => setError(e.message));
  }, [project]);

  if (error) {
    return (
      <div style={{ maxWidth: 760, margin: "0 auto" }}>
        <Banner tone="error" title={t("yaml.cannot_render")}>
          {error}
        </Banner>
      </div>
    );
  }
  if (!rendered)
    return (
      <div style={{ maxWidth: 760, margin: "0 auto" }}>
        {t("yaml.rendering")}
      </div>
    );

  const text =
    file === "transitions.yml" ? rendered.transitions : rendered.columns;
  const lines = text.split("\n");

  return (
    <div
      style={{
        maxWidth: 760,
        margin: "0 auto",
        display: "flex",
        flexDirection: "column",
        gap: 14,
      }}
    >
      <PageIntro title={t("yaml.intro_title")} scope="board">
        {t("yaml.intro_body")}
      </PageIntro>
      <SegmentedControl
        mono
        options={["transitions.yml", "columns.yml"]}
        value={file}
        onChange={setFile}
      />
      <div
        style={{
          background: "var(--surface-inverse)",
          borderRadius: "var(--radius-lg)",
          border: "1px solid var(--border)",
          overflow: "hidden",
          boxShadow: "var(--shadow-sm)",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 7,
            padding: "9px 14px",
            borderBottom: "1px solid rgba(255,255,255,0.08)",
          }}
        >
          <span
            style={{
              width: 9,
              height: 9,
              borderRadius: "50%",
              background: "#e0494e",
            }}
          />
          <span
            style={{
              width: 9,
              height: 9,
              borderRadius: "50%",
              background: "#d98e29",
            }}
          />
          <span
            style={{
              width: 9,
              height: 9,
              borderRadius: "50%",
              background: "#1f9d54",
            }}
          />
          <span
            style={{
              marginLeft: 8,
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "rgba(255,255,255,0.55)",
            }}
          >
            .claude/kanban/{file}
          </span>
        </div>
        <pre
          style={{
            margin: 0,
            padding: "14px 18px",
            fontFamily: "var(--font-mono)",
            fontSize: 12.5,
            lineHeight: 1.65,
            color: "#e2e2d6",
            overflow: "auto",
            maxHeight: 520,
            whiteSpace: "pre-wrap",
          }}
        >
          {lines.map((l, i) => (
            <div key={i}>
              <span
                style={{
                  display: "inline-block",
                  width: 30,
                  color: "rgba(255,255,255,0.28)",
                  userSelect: "none",
                }}
              >
                {l ? i + 1 : ""}
              </span>
              {l}
            </div>
          ))}
        </pre>
      </div>
    </div>
  );
}
