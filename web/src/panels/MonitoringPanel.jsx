// Monitoring tab (helm PR 2-bis) — read-only live board + ticket detail + agent panel + pane tail.
// Two-speed polling: agents + pane ~3 s, board ~15 s, ticket detail on open. Pauses when the tab is
// hidden. Read-only — no actions; to interact with an agent the operator uses `tmux attach`.
import React from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { marked } from "marked";
import * as api from "../api.js";
import { PageIntro } from "../components/Help.jsx";
import { MobileBack } from "../components/MobileMasterDetail.jsx";
import AgentTerminal from "../components/AgentTerminal.jsx";
import MarkdownReader from "../components/MarkdownReader.jsx";
import RichPromptEditor from "../components/RichPromptEditor.jsx";
import useIsMobile from "../useIsMobile.js";
import { useT } from "../i18n/index.jsx";

const { KeyChip, Badge, Banner, Button } = window.KanbanMateDesignSystem_2463ad;

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
  const isMobile = useIsMobile();
  const [board, setBoard] = React.useState(null);
  const [agents, setAgents] = React.useState([]);
  // Persisted across reloads (#47): the open ticket + the per-group collapse overrides.
  const [sel, setSel] = React.useState(() => {
    try {
      const v = localStorage.getItem("bridge.monitor.ticket");
      return v ? Number(v) : null;
    } catch (_) {
      return null;
    }
  });
  const [detail, setDetail] = React.useState(null);
  const [pane, setPane] = React.useState(null);
  const [error, setError] = React.useState(null);
  const [collapsedOverride, setCollapsedOverride] = React.useState(() => {
    try {
      return JSON.parse(
        localStorage.getItem("bridge.monitor.collapsed") || "{}",
      );
    } catch (_) {
      return {};
    }
  });
  React.useEffect(() => {
    try {
      if (sel == null) localStorage.removeItem("bridge.monitor.ticket");
      else localStorage.setItem("bridge.monitor.ticket", String(sel));
    } catch (_) {
      /* storage may be unavailable (private mode) */
    }
  }, [sel]);
  const [terminalOpen, setTerminalOpen] = React.useState(false);
  // Edit description state (tiller §3.4) — marker-safe freeform edit via PATCH endpoint.
  const [editMode, setEditMode] = React.useState(false);
  const [editFreeform, setEditFreeform] = React.useState("");
  const [saving, setSaving] = React.useState(false);
  // Reset terminal visibility when the selected ticket changes.
  React.useEffect(() => {
    setTerminalOpen(false);
  }, [sel]);
  const toggleCollapse = (key, isCollapsed) => {
    setCollapsedOverride((prev) => {
      const next = { ...prev, [key]: !isCollapsed };
      try {
        localStorage.setItem("bridge.monitor.collapsed", JSON.stringify(next));
      } catch (_) {
        /* storage may be unavailable */
      }
      return next;
    });
  };

  usePoll(
    () =>
      api
        .monitorBoard(project)
        .then(setBoard)
        .catch((e) => setError(e.message)),
    15000,
    [project],
  );
  usePoll(
    () =>
      api
        .monitorAgents(project)
        .then((r) => setAgents(r.agents))
        .catch(() => {}),
    3000,
    [project],
  );

  React.useEffect(() => {
    if (sel == null) return;
    setDetail(null);
    api
      .monitorTicket(sel, project)
      .then(setDetail)
      .catch((e) => setError(e.message));
  }, [sel, project]);

  const selAgent = agents.find((a) => a.issue === sel);
  usePoll(
    () => {
      if (sel != null && selAgent)
        api
          .monitorPane(sel, project)
          .then(setPane)
          .catch(() => {});
      else setPane(null);
    },
    3000,
    [sel, project, !!selAgent],
  );

  // Artifact reader (brainstorm/design/plans) — opened from the ticket detail.
  const [reader, setReader] = React.useState(null);
  const openFile = (title, path) => {
    setReader({
      title,
      subtitle: path,
      loading: true,
      content: "",
      error: null,
    });
    api
      // Pass the ticket (sel) so the endpoint can fall back to the kanban/ticket-<n> WIP branch
      // when an in-flight design/plan isn't on the clone's checked-out tree.
      .monitorFile(path, project, sel)
      .then((r) =>
        setReader({
          title,
          subtitle: r.path,
          loading: false,
          content: r.content,
          error: null,
        }),
      )
      .catch((e) =>
        setReader({
          title,
          subtitle: path,
          loading: false,
          content: "",
          error: e.message,
        }),
      );
  };
  const openText = (title, content) =>
    setReader({ title, subtitle: "", loading: false, content, error: null });

  // Open the body edit mode — extract freeform from the current body.
  const openEdit = () => {
    setEditFreeform(extractFreeform(detail?.body || ""));
    setEditMode(true);
  };
  // Save edited freeform via PATCH, then refresh the ticket detail.
  const saveEdit = async () => {
    setSaving(true);
    try {
      await api.patchTicketBody(sel, editFreeform, project);
      setEditMode(false);
      const d = await api.monitorTicket(sel, project);
      setDetail(d);
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  // Derived artifact sources from the loaded detail (null/[] when no detail yet).
  const brainstorm = detail ? brainstormSection(detail.body) : null;
  const planPaths = detail?.markers?.plans
    ? detail.markers.plans
        .split(",")
        .map((p) => p.trim())
        .filter(Boolean)
    : [];

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
      <div
        style={{
          marginBottom: 12,
          fontSize: 12,
          color: "var(--muted-foreground)",
        }}
      >
        {t("monitor.summary", {
          running: s.running,
          waiting: s.waiting,
          blocked: s.blocked,
        })}
      </div>

      {isMobile && sel != null && (
        <MobileBack onClick={() => setSel(null)} label={`#${sel}`} />
      )}
      <div
        style={{
          display: isMobile ? "block" : "grid",
          gridTemplateColumns: isMobile ? undefined : "360px 1fr",
          gap: 16,
          alignItems: "start",
        }}
      >
        {/* board overview — columns as groups */}
        {(!isMobile || sel == null) && (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {board.columns.map((c) => {
              const tix = board.tickets.filter((tk) => tk.column_key === c.key);
              // Monitoring shows only columns with at least one ticket (operator 2026-06-21).
              if (!tix.length) return null;
              // Non-empty groups are expanded by default; operator collapse toggles persist (#47).
              const collapsed =
                c.key in collapsedOverride ? collapsedOverride[c.key] : false;
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
                  <button
                    onClick={() => toggleCollapse(c.key, collapsed)}
                    aria-expanded={!collapsed}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 7,
                      width: "100%",
                      textAlign: "left",
                      border: "none",
                      cursor: "pointer",
                      padding: "8px 12px",
                      background: "var(--muted)",
                      fontFamily: "var(--font-mono)",
                      fontSize: 11,
                      textTransform: "uppercase",
                      color: "var(--muted-foreground)",
                    }}
                  >
                    {collapsed ? (
                      <ChevronRight size={13} strokeWidth={2} />
                    ) : (
                      <ChevronDown size={13} strokeWidth={2} />
                    )}
                    <span style={{ flex: 1 }}>{c.name}</span>
                    <span>· {tix.length}</span>
                  </button>
                  {!collapsed &&
                    tix.map((tk) => (
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
                          background:
                            sel === tk.number ? "var(--muted)" : "transparent",
                          cursor: "pointer",
                          padding: "8px 12px",
                        }}
                      >
                        <span
                          style={{
                            fontFamily: "var(--font-mono)",
                            fontSize: 11,
                            color: "var(--muted-foreground)",
                          }}
                        >
                          #{tk.number}
                        </span>
                        <span
                          style={{
                            flex: 1,
                            fontSize: 12.5,
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {tk.title}
                        </span>
                        {tk.agent_state && (
                          <Badge
                            tone={STATE_TONE[tk.agent_state] || "neutral"}
                            size="sm"
                          >
                            {tk.agent_state}
                          </Badge>
                        )}
                      </button>
                    ))}
                </div>
              );
            })}
          </div>
        )}

        {/* ticket detail */}
        {(!isMobile || sel != null) && (
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
              <div
                style={{
                  color: "var(--muted-foreground)",
                  textAlign: "center",
                  padding: "40px 0",
                }}
              >
                {t("monitor.select_hint")}
              </div>
            ) : !detail ? (
              <div>{t("common.loading")}</div>
            ) : (
              <div
                style={{ display: "flex", flexDirection: "column", gap: 14 }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                  <span
                    style={{
                      fontFamily: "var(--font-mono)",
                      color: "var(--muted-foreground)",
                    }}
                  >
                    #{detail.number}
                  </span>
                  <span
                    style={{
                      fontFamily: "var(--font-display)",
                      fontWeight: 600,
                      fontSize: "var(--text-md)",
                    }}
                  >
                    {detail.title}
                  </span>
                  <KeyChip>{detail.column_key}</KeyChip>
                </div>

                {/* body edit mode (tiller §3.4) — marker-safe freeform edit via PATCH endpoint */}
                {!editMode ? (
                  <div>
                    <Button size="sm" variant="outline" onClick={openEdit}>
                      {t("body.edit")}
                    </Button>
                  </div>
                ) : (
                  <div
                    style={{ display: "flex", flexDirection: "column", gap: 8 }}
                  >
                    <RichPromptEditor
                      value={editFreeform}
                      onChange={setEditFreeform}
                    />
                    <div style={{ display: "flex", gap: 6 }}>
                      <Button onClick={saveEdit} disabled={saving}>
                        {saving ? t("body.saving") : t("body.save")}
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => setEditMode(false)}
                      >
                        {t("body.cancel")}
                      </Button>
                    </div>
                  </div>
                )}

                {/* artifacts: info chips (roadmap/codename) + clickable readable docs
                    (brainstorm/design/plans) opening the markdown reader */}
                {(Object.values(detail.markers).some(Boolean) ||
                  brainstorm) && (
                  <div>
                    <div
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: 10,
                        textTransform: "uppercase",
                        color: "var(--muted-foreground)",
                        marginBottom: 6,
                      }}
                    >
                      {t("monitor.artifacts")}
                    </div>
                    <div
                      style={{
                        display: "flex",
                        gap: 8,
                        flexWrap: "wrap",
                        alignItems: "center",
                      }}
                    >
                      {detail.markers.roadmap && (
                        <span title={detail.markers.roadmap}>
                          <KeyChip>roadmap: {detail.markers.roadmap}</KeyChip>
                        </span>
                      )}
                      {detail.markers.codename && (
                        <KeyChip>codename: {detail.markers.codename}</KeyChip>
                      )}
                      {brainstorm && (
                        <DocLink
                          onClick={() =>
                            openText(t("monitor.doc_brainstorm"), brainstorm)
                          }
                        >
                          {t("monitor.doc_brainstorm")}
                        </DocLink>
                      )}
                      {detail.markers.design && (
                        <DocLink
                          title={detail.markers.design}
                          onClick={() =>
                            openFile(
                              t("monitor.doc_design"),
                              detail.markers.design,
                            )
                          }
                        >
                          {t("monitor.doc_design")}
                        </DocLink>
                      )}
                      {planPaths.map((p) => (
                        <DocLink
                          key={p}
                          title={p}
                          onClick={() => openFile(t("monitor.doc_plan"), p)}
                        >
                          {baseName(p)}
                        </DocLink>
                      ))}
                    </div>
                  </div>
                )}

                {/* agent panel + pane tail */}
                {selAgent ? (
                  <div
                    style={{
                      border: "1px solid var(--border)",
                      borderRadius: "var(--radius-md)",
                      padding: 12,
                      background: "var(--muted)",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        gap: 14,
                        fontFamily: "var(--font-mono)",
                        fontSize: 11,
                        color: "var(--muted-foreground)",
                        marginBottom: 8,
                      }}
                    >
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
                    <div
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: 10,
                        color: "var(--muted-foreground)",
                        marginBottom: 4,
                      }}
                    >
                      {t("monitor.terminal")}
                    </div>
                    {!terminalOpen && (
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
                        {pane && pane.alive
                          ? pane.lines
                          : t("monitor.session_ended")}
                      </pre>
                    )}
                  </div>
                ) : (
                  <div
                    style={{ fontSize: 12, color: "var(--muted-foreground)" }}
                  >
                    {t("monitor.no_agent")}
                  </div>
                )}

                {/* interactive terminal (tiller §5) — shown when the selected ticket
                    has a running agent. Replaces the static pane tail above. */}
                {sel != null &&
                  agents.some((a) => a.issue === sel && a.alive) && (
                    <div style={{ marginTop: 12 }}>
                      {!terminalOpen ? (
                        <Button size="sm" onClick={() => setTerminalOpen(true)}>
                          {t("terminal.interactive", "Interactive terminal")}
                        </Button>
                      ) : (
                        <AgentTerminal
                          issue={sel}
                          onClose={() => setTerminalOpen(false)}
                        />
                      )}
                    </div>
                  )}

                {/* timeline */}
                {detail.timeline.length > 0 && (
                  <div>
                    <div
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: 10,
                        textTransform: "uppercase",
                        color: "var(--muted-foreground)",
                        marginBottom: 6,
                      }}
                    >
                      {t("monitor.timeline")}
                    </div>
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: 6,
                      }}
                    >
                      {detail.timeline.map((e, i) => {
                        const isComment = e.kind === "comment";
                        return (
                          <div
                            key={i}
                            style={{ fontSize: 12.5, lineHeight: 1.5 }}
                          >
                            <div
                              style={{
                                display: "flex",
                                alignItems: "center",
                                gap: 6,
                                marginBottom: 3,
                              }}
                            >
                              <KeyChip>{e.kind}</KeyChip>
                              {e.at && (
                                <span
                                  style={{
                                    color: "var(--muted-foreground)",
                                    fontSize: 11,
                                  }}
                                >
                                  {e.at}
                                </span>
                              )}
                            </div>
                            {isComment ? (
                              // Render comment bodies as markdown (#47, batch 5).
                              <div
                                className="km-timeline-md"
                                style={{
                                  border: "1px solid var(--border)",
                                  borderRadius: "var(--radius-md)",
                                  padding: "8px 11px",
                                  background: "var(--muted)",
                                }}
                                dangerouslySetInnerHTML={{
                                  __html: marked.parse(e.text || "", {
                                    breaks: true,
                                  }),
                                }}
                              />
                            ) : (
                              <div
                                style={{
                                  whiteSpace: "pre-wrap",
                                  color: "var(--muted-foreground)",
                                }}
                              >
                                {e.text}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      <MarkdownReader
        open={reader != null}
        title={reader?.title}
        subtitle={reader?.subtitle}
        content={reader?.content}
        loading={reader?.loading}
        error={reader?.error}
        onClose={() => setReader(null)}
      />
    </div>
  );
}

// Extract the issue body's `## Brainstorm` section (heading → next `##` or end), or null.
function brainstormSection(body) {
  if (!body) return null;
  const m = body.match(/(^|\n)(##\s+Brainstorm[\s\S]*?)(?=\n##\s|$)/i);
  return m ? m[2].trim() : null;
}

// Extract freeform prose from the body — strip marker/status regions and ## Brainstorm.
function extractFreeform(body) {
  if (!body) return "";
  const STATUS_BEGIN = "<!-- kanban:status:begin -->";
  const STATUS_END = "<!-- kanban:status:end -->";
  let text = body;
  // Remove status block
  const sbStart = text.indexOf(STATUS_BEGIN);
  const sbEnd = text.indexOf(STATUS_END);
  if (sbStart !== -1 && sbEnd !== -1) {
    text = text.slice(0, sbStart) + text.slice(sbEnd + STATUS_END.length);
  }
  // Remove **key**: value marker lines
  text = text.replace(/^\*\*\w+\*\*:[^\n]*$/gm, "");
  // Remove ## Brainstorm section
  const bsIdx = text.indexOf("## Brainstorm");
  if (bsIdx !== -1) text = text.slice(0, bsIdx);
  return text.trim();
}

// Last path segment — a compact label for plan files (paths can be long / multiple).
function baseName(path) {
  const parts = String(path).split("/");
  return parts[parts.length - 1] || path;
}

// A clickable artifact "link" rendered as a chip with a 📄 affordance.
function DocLink({ onClick, title, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        border: "1px solid var(--primary)",
        background: "color-mix(in oklch, var(--primary) 10%, transparent)",
        color: "var(--primary)",
        borderRadius: "var(--radius-md)",
        cursor: "pointer",
        fontFamily: "var(--font-mono)",
        fontSize: 11.5,
        padding: "3px 9px",
        maxWidth: 240,
      }}
    >
      <span aria-hidden>📄</span>
      <span
        style={{
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {children}
      </span>
    </button>
  );
}
