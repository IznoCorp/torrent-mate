// Monitoring tab (helm PR 2-bis) — read-only live board + ticket detail + agent panel + pane tail.
// Two-speed polling: agents + pane ~3 s, board ~15 s, ticket detail on open. Pauses when the tab is
// hidden. Read-only — no actions; to interact with an agent the operator uses `tmux attach`.
import React from "react";
import * as api from "../api.js";
import { PageIntro } from "../components/Help.jsx";
import { useT } from "../i18n/index.jsx";

const { KeyChip, Badge, Banner } = window.KanbanMateDesignSystem_2463ad;

const STATE_TONE = { running: "accent", waiting: "amber", blocked: "red" };

// Poll `fn` every `ms` while the tab is visible; runs once immediately. `deps` re-arm the interval.
function usePoll(fn, ms, deps) {
  React.useEffect(() => {
    const tick = () => {
      if (document.visibilityState === "visible") fn();
    };
    tick();
    const id = setInterval(tick, ms);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}

export default function MonitoringPanel({ project }) {
  const { t } = useT();
  const [board, setBoard] = React.useState(null);
  const [agents, setAgents] = React.useState([]);
  const [sel, setSel] = React.useState(null);
  const [detail, setDetail] = React.useState(null);
  const [pane, setPane] = React.useState(null);
  const [error, setError] = React.useState(null);

  usePoll(
    () => api.monitorBoard(project).then(setBoard).catch((e) => setError(e.message)),
    15000,
    [project],
  );
  usePoll(
    () => api.monitorAgents(project).then((r) => setAgents(r.agents)).catch(() => {}),
    3000,
    [project],
  );

  React.useEffect(() => {
    if (sel == null) return;
    setDetail(null);
    api.monitorTicket(sel, project).then(setDetail).catch((e) => setError(e.message));
  }, [sel, project]);

  const selAgent = agents.find((a) => a.issue === sel);
  usePoll(
    () => {
      if (sel != null && selAgent) api.monitorPane(sel, project).then(setPane).catch(() => {});
      else setPane(null);
    },
    3000,
    [sel, project, !!selAgent],
  );

  if (error && !board)
    return (
      <Banner tone="error" title={t("monitor.intro_title")}>
        {error}
      </Banner>
    );
  if (!board) return <div style={{ padding: 24 }}>{t("common.loading")}</div>;

  const s = board.agents_summary;

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto" }}>
      <PageIntro title={t("monitor.intro_title")} scope="board">
        {t("monitor.intro_body")}
      </PageIntro>
      <div style={{ marginBottom: 12, fontSize: 12, color: "var(--muted-foreground)" }}>
        {t("monitor.summary", { running: s.running, waiting: s.waiting, blocked: s.blocked })}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "360px 1fr", gap: 16, alignItems: "start" }}>
        {/* board overview — columns as groups */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {board.columns.map((c) => {
            const tix = board.tickets.filter((tk) => tk.column_key === c.key);
            if (!tix.length) return null;
            return (
              <div
                key={c.key}
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
                    padding: "8px 12px",
                    background: "var(--muted)",
                    fontFamily: "var(--font-mono)",
                    fontSize: 11,
                    textTransform: "uppercase",
                    color: "var(--muted-foreground)",
                  }}
                >
                  {c.name} · {tix.length}
                </div>
                {tix.map((tk) => (
                  <button
                    key={tk.number}
                    onClick={() => setSel(tk.number)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      width: "100%",
                      textAlign: "left",
                      border: "none",
                      borderBottom: "1px solid var(--border)",
                      borderLeft: `3px solid ${sel === tk.number ? "var(--primary)" : "transparent"}`,
                      background: sel === tk.number ? "var(--muted)" : "transparent",
                      cursor: "pointer",
                      padding: "8px 12px",
                    }}
                  >
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--muted-foreground)" }}>
                      #{tk.number}
                    </span>
                    <span style={{ flex: 1, fontSize: 12.5, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {tk.title}
                    </span>
                    {tk.agent_state && (
                      <Badge tone={STATE_TONE[tk.agent_state] || "neutral"} size="sm">
                        {tk.agent_state}
                      </Badge>
                    )}
                  </button>
                ))}
              </div>
            );
          })}
        </div>

        {/* ticket detail */}
        <div
          style={{
            background: "var(--card)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-lg)",
            padding: 18,
            minHeight: 200,
          }}
        >
          {sel == null ? (
            <div style={{ color: "var(--muted-foreground)", textAlign: "center", padding: "40px 0" }}>
              {t("monitor.select_hint")}
            </div>
          ) : !detail ? (
            <div>{t("common.loading")}</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                <span style={{ fontFamily: "var(--font-mono)", color: "var(--muted-foreground)" }}>
                  #{detail.number}
                </span>
                <span style={{ fontFamily: "var(--font-display)", fontWeight: 600, fontSize: "var(--text-md)" }}>
                  {detail.title}
                </span>
                <KeyChip>{detail.column_key}</KeyChip>
              </div>

              {/* artifacts (markers) */}
              {Object.values(detail.markers).some(Boolean) && (
                <div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", color: "var(--muted-foreground)", marginBottom: 6 }}>
                    {t("monitor.artifacts")}
                  </div>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    {Object.entries(detail.markers)
                      .filter(([, v]) => v)
                      .map(([k, v]) => (
                        <span key={k} title={v}>
                          <KeyChip>{k}: {v}</KeyChip>
                        </span>
                      ))}
                  </div>
                </div>
              )}

              {/* agent panel + pane tail */}
              {selAgent ? (
                <div style={{ border: "1px solid var(--border)", borderRadius: "var(--radius-md)", padding: 12, background: "var(--muted)" }}>
                  <div style={{ display: "flex", gap: 14, fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--muted-foreground)", marginBottom: 8 }}>
                    <span>
                      {t("monitor.state")}: <b>{selAgent.state}</b>
                    </span>
                    <span>
                      {t("monitor.stage")}: {selAgent.stage}
                    </span>
                    <span>
                      {t("monitor.branch")}: {selAgent.branch}
                    </span>
                  </div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--muted-foreground)", marginBottom: 4 }}>
                    {t("monitor.terminal")}
                  </div>
                  <pre
                    style={{
                      margin: 0,
                      padding: 10,
                      background: "var(--surface-inverse, #1e1e1e)",
                      color: "#e2e2d6",
                      borderRadius: "var(--radius-sm)",
                      maxHeight: 320,
                      overflow: "auto",
                      fontFamily: "var(--font-mono)",
                      fontSize: 11.5,
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    {pane && pane.alive ? pane.lines : t("monitor.session_ended")}
                  </pre>
                </div>
              ) : (
                <div style={{ fontSize: 12, color: "var(--muted-foreground)" }}>{t("monitor.no_agent")}</div>
              )}

              {/* timeline */}
              {detail.timeline.length > 0 && (
                <div>
                  <div style={{ fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", color: "var(--muted-foreground)", marginBottom: 6 }}>
                    {t("monitor.timeline")}
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    {detail.timeline.map((e, i) => (
                      <div key={i} style={{ fontSize: 12.5, lineHeight: 1.5 }}>
                        <KeyChip>{e.kind}</KeyChip>{" "}
                        {e.at && <span style={{ color: "var(--muted-foreground)" }}>{e.at}</span>}
                        <div style={{ whiteSpace: "pre-wrap" }}>{e.text}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
