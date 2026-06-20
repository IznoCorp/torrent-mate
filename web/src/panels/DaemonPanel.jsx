// Daemon scope (DESIGN §13.2) — master-detail of the boards the daemon manages. The registry
// (projects.json) is daemon-wide, NOT per-board; this section is visually distinct from the board
// tabs. Only the two daemon-scoped toggles are editable: enabled + ingress (PATCH /api/projects).
import React from "react";
import * as api from "../api.js";
import { PageIntro } from "../components/Help.jsx";
import { MobileBack } from "../components/MobileMasterDetail.jsx";
import useIsMobile from "../useIsMobile.js";
import { useT } from "../i18n/index.jsx";

const { Banner, Button, Select, Switch, KeyChip, Badge } =
  window.KanbanMateDesignSystem_2463ad;

export default function DaemonPanel({ projects, selected, onChanged }) {
  const { t } = useT();
  const isMobile = useIsMobile();
  // Mobile starts on the list (no detail); desktop pre-selects a board so the detail is never blank.
  const [pick, setPick] = React.useState(() =>
    typeof window !== "undefined" &&
    window.matchMedia?.("(max-width: 768px)").matches
      ? null
      : selected || (projects[0] && projects[0].project_id),
  );
  const current = projects.find((p) => p.project_id === pick) || projects[0];

  // Local draft of the editable toggles for the selected project.
  const [enabled, setEnabled] = React.useState(current.enabled);
  const [ingress, setIngress] = React.useState(current.ingress);
  const [busy, setBusy] = React.useState(false);
  const [msg, setMsg] = React.useState(null);
  const [err, setErr] = React.useState(null);

  // Reset the local draft when the selection changes.
  React.useEffect(() => {
    setEnabled(current.enabled);
    setIngress(current.ingress);
    setMsg(null);
    setErr(null);
  }, [pick]); // eslint-disable-line react-hooks/exhaustive-deps

  const dirty = enabled !== current.enabled || ingress !== current.ingress;

  const save = async () => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      await api.patchProject(current.project_id, { enabled, ingress });
      setMsg(t("daemon.saved_msg"));
      if (onChanged) onChanged();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ maxWidth: 900, margin: "0 auto" }}>
      <PageIntro title={t("daemon.intro_title")} scope="daemon">
        {t("daemon.intro_body")}
      </PageIntro>
      <Banner
        tone="amber"
        title={t("daemon.banner_title")}
        style={{ marginBottom: 16 }}
      >
        {t("daemon.banner_body")}
      </Banner>

      {isMobile && pick != null && (
        <MobileBack onClick={() => setPick(null)} label={current.repo} />
      )}
      <div
        style={{
          display: isMobile ? "block" : "grid",
          gridTemplateColumns: isMobile ? undefined : "240px 1fr",
          gap: 16,
        }}
      >
        {/* master: project list */}
        {(!isMobile || pick == null) && (
          <div
            style={{
              background: "var(--card)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-lg)",
              overflow: "hidden",
              boxShadow: "var(--shadow-xs)",
              alignSelf: "start",
            }}
          >
            {projects.map((p) => {
              const on = p.project_id === pick;
              return (
                <button
                  key={p.project_id}
                  onClick={() => setPick(p.project_id)}
                  style={{
                    display: "block",
                    width: "100%",
                    textAlign: "left",
                    border: "none",
                    borderLeft: `3px solid ${on ? "var(--primary)" : "transparent"}`,
                    borderBottom: "1px solid var(--border)",
                    background: on ? "var(--muted)" : "transparent",
                    cursor: "pointer",
                    padding: "11px 13px",
                  }}
                >
                  <div
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 12.5,
                      fontWeight: on ? 600 : 500,
                      color: "var(--foreground)",
                    }}
                  >
                    {p.repo}
                  </div>
                  <div
                    style={{
                      marginTop: 4,
                      display: "flex",
                      gap: 6,
                      alignItems: "center",
                    }}
                  >
                    <Badge tone={p.enabled ? "accent" : "neutral"} size="sm">
                      {p.enabled
                        ? t("daemon.enabled_chip")
                        : t("daemon.disabled_chip")}
                    </Badge>
                    <span
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: 10,
                        color: "var(--muted-foreground)",
                      }}
                    >
                      {p.ingress}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        )}

        {/* detail: editable toggles for the picked project */}
        {(!isMobile || pick != null) && (
          <div
            style={{
              background: "var(--card)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-lg)",
              boxShadow: "var(--shadow-xs)",
              padding: 18,
              display: "flex",
              flexDirection: "column",
              gap: 16,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
              <span
                style={{
                  fontFamily: "var(--font-display)",
                  fontWeight: 600,
                  fontSize: "var(--text-md)",
                }}
              >
                {current.repo}
              </span>
              <KeyChip>{current.project_id}</KeyChip>
            </div>

            <Field label={t("daemon.enabled")} hint={t("daemon.enabled_hint")}>
              <span
                style={{ display: "inline-flex", alignItems: "center", gap: 8 }}
              >
                <Switch checked={enabled} onChange={(v) => setEnabled(v)} />
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 12,
                    color: "var(--muted-foreground)",
                  }}
                >
                  {enabled
                    ? t("daemon.enabled_true")
                    : t("daemon.enabled_false")}
                </span>
              </span>
            </Field>

            <Field label={t("daemon.ingress")} hint={t("daemon.ingress_hint")}>
              <Select
                options={["webhook", "polling"]}
                value={ingress}
                onChange={(e) => setIngress(e && e.target ? e.target.value : e)}
                style={{ width: 160 }}
              />
            </Field>

            {err && (
              <Banner tone="error" title={t("daemon.save_failed")}>
                {err}
              </Banner>
            )}
            {msg && <Banner tone="success">{msg}</Banner>}

            <div
              style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}
            >
              <Button
                variant="primary"
                disabled={busy || !dirty}
                onClick={save}
              >
                {busy ? t("daemon.saving") : t("daemon.save_settings")}
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Field({ label, hint, children }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <span
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          color: "var(--muted-foreground)",
        }}
      >
        {label}
      </span>
      {children}
      {hint && (
        <span style={{ fontSize: 11.5, color: "var(--muted-foreground)" }}>
          {hint}
        </span>
      )}
    </div>
  );
}
