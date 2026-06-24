// IssuesPanel — the "Issues" hub for capturing ideas. A flat list of the board's GitHub issues
// (reflecting the Projects v2 board) with inline create + description editing. Create lands the
// operator on the new ticket's editor so they can refine it right away; "← Issues" returns to the
// list. The new ticket is created on GitHub AND added to the board at Backlog (remote + local).
import React from "react";
import * as api from "../api.js";
import { PageIntro } from "../components/Help.jsx";
import MarkdownField from "../components/MarkdownField.jsx";
import { renderMarkdown } from "../lib/markdown.js";
import { extractFreeform } from "../lib/body.js";
import { useT } from "../i18n/index.jsx";

const { Banner, Button, Input, Badge, Select, Tooltip } =
  window.KanbanMateDesignSystem_2463ad;

function Note({ tone, children }) {
  if (!children) return null;
  return (
    <div style={{ marginBottom: 12 }}>
      <Banner tone={tone === "red" ? "error" : "success"}>{children}</Banner>
    </div>
  );
}

export default function IssuesPanel({ project, repo: repoProp }) {
  const { t } = useT();
  const [mode, setMode] = React.useState("list"); // list | create | edit
  const [board, setBoard] = React.useState(null);
  const [listError, setListError] = React.useState(null);
  const [statusFilter, setStatusFilter] = React.useState(""); // "" = all statuses
  // create
  const [newTitle, setNewTitle] = React.useState("");
  const [newBody, setNewBody] = React.useState("");
  const [creating, setCreating] = React.useState(false);
  // edit
  const [sel, setSel] = React.useState(null);
  const [detail, setDetail] = React.useState(null);
  const [editFreeform, setEditFreeform] = React.useState("");
  const [saving, setSaving] = React.useState(false);
  const [msg, setMsg] = React.useState(null); // { tone, text }

  const loadList = React.useCallback(() => {
    setListError(null);
    return api
      .monitorBoard(project)
      .then(setBoard)
      .catch((e) => setListError(e.message));
  }, [project]);

  React.useEffect(() => {
    loadList();
  }, [loadList]);

  const issues = React.useMemo(() => {
    if (!board) return [];
    const colName = {};
    (board.columns || []).forEach((c) => (colName[c.key] = c.name));
    return (board.tickets || [])
      .map((tk) => ({
        number: tk.number,
        title: tk.title,
        column_key: tk.column_key,
        column_name: colName[tk.column_key] || tk.column_key,
      }))
      .sort((a, b) => b.number - a.number); // newest first
  }, [board]);

  // Status-filter options: "All statuses" + one entry per board column (in board order),
  // selecting on the stable column key (robust to display renames).
  const statusOptions = React.useMemo(
    () => [
      { value: "", label: t("issues.filter_all", "All statuses") },
      ...(board?.columns || []).map((c) => ({ value: c.key, label: c.name })),
    ],
    [board, t],
  );

  // Client-side filter: "" shows all, else narrow to the selected column key.
  const filtered = React.useMemo(
    () =>
      statusFilter
        ? issues.filter((it) => it.column_key === statusFilter)
        : issues,
    [issues, statusFilter],
  );

  const openEdit = async (number) => {
    setSel(number);
    setMode("edit");
    setDetail(null);
    setMsg(null);
    try {
      const d = await api.monitorTicket(number, project);
      setDetail(d);
      setEditFreeform(extractFreeform(d.body || ""));
    } catch (e) {
      setMsg({ tone: "red", text: e.message });
    }
  };

  const createTicket = async () => {
    const title = newTitle.trim();
    if (!title || creating) return;
    setCreating(true);
    setMsg(null);
    try {
      const res = await api.newTicket({ title, body: newBody }, project);
      setNewTitle("");
      setNewBody("");
      await loadList();
      await openEdit(res.number); // land on the new ticket to refine it
      setMsg({
        tone: "green",
        text: t("issues.created", "Ticket #{n} created in Backlog.", {
          n: res.number,
        }),
      });
    } catch (e) {
      setMsg({ tone: "red", text: e.message });
      setCreating(false);
    }
    // creating cleared in the edit view (we navigated away on success)
    setCreating(false);
  };

  const saveDescription = async () => {
    if (saving) return;
    setSaving(true);
    setMsg(null);
    try {
      await api.patchTicketBody(sel, editFreeform, project);
      const d = await api.monitorTicket(sel, project);
      setDetail(d);
      setEditFreeform(extractFreeform(d.body || ""));
      setMsg({ tone: "green", text: t("issues.saved", "Description saved ✓") });
    } catch (e) {
      setMsg({ tone: "red", text: e.message });
    } finally {
      setSaving(false);
    }
  };

  const startCreate = () => {
    setMode("create");
    setNewTitle("");
    setNewBody("");
    setMsg(null);
  };
  const backToList = () => {
    setMode("list");
    setSel(null);
    setDetail(null);
    setMsg(null);
    loadList();
  };

  const repo = repoProp || board?.repo;
  const back = (
    <button
      type="button"
      onClick={backToList}
      style={{
        border: "none",
        background: "none",
        color: "var(--primary)",
        cursor: "pointer",
        padding: 0,
        fontSize: 13,
        marginBottom: 12,
      }}
    >
      ← {t("issues.back", "Issues")}
    </button>
  );

  // ---- CREATE ----
  if (mode === "create") {
    return (
      <div style={{ maxWidth: 760, margin: "0 auto" }}>
        {back}
        <PageIntro title={t("issues.new_title", "New ticket")} scope="board">
          {t(
            "issues.new_intro",
            "Capture an idea or bug. It is created on GitHub and added to the board at Backlog; you then land on it to refine the description.",
          )}
        </PageIntro>
        <Note tone={msg?.tone}>{msg?.text}</Note>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 14,
            background: "var(--card)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-lg)",
            padding: 18,
          }}
        >
          <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <span style={{ fontSize: 13, fontWeight: 600 }}>
              {t("issues.field_title", "Title")}
            </span>
            <Input
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              placeholder={t(
                "issues.title_ph",
                "Short summary of the idea or bug",
              )}
              disabled={creating}
            />
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <span style={{ fontSize: 13, fontWeight: 600 }}>
              {t("issues.field_desc", "Description")}
              <span
                style={{
                  marginLeft: 6,
                  fontWeight: 400,
                  color: "var(--muted-foreground)",
                }}
              >
                {t("issues.optional", "(optional, markdown)")}
              </span>
            </span>
            <MarkdownField
              value={newBody}
              onChange={setNewBody}
              minRows={12}
              placeholder={t(
                "issues.desc_ph",
                "Context, steps to reproduce, acceptance…",
              )}
            />
          </label>
          <div style={{ display: "flex", gap: 10 }}>
            <Tooltip
              label={t(
                "issues.create_tip",
                "Create the issue on the board at Backlog",
              )}
            >
              <Button
                variant="primary"
                disabled={!newTitle.trim() || creating}
                loading={creating}
                onClick={createTicket}
              >
                {t("issues.create_btn", "Create ticket")}
              </Button>
            </Tooltip>
            <Button variant="outline" onClick={backToList} disabled={creating}>
              {t("common.cancel", "Cancel")}
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // ---- EDIT ----
  if (mode === "edit") {
    return (
      <div style={{ maxWidth: 820, margin: "0 auto" }}>
        {back}
        <Note tone={msg?.tone}>{msg?.text}</Note>
        {!detail ? (
          <div style={{ color: "var(--muted-foreground)" }}>
            {t("common.loading", "Loading…")}
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 9,
                flexWrap: "wrap",
              }}
            >
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
                  minWidth: 0,
                  overflowWrap: "anywhere",
                }}
              >
                {detail.title}
              </span>
              <Badge size="sm">{detail.column_key}</Badge>
              {repo && (
                <a
                  href={`https://github.com/${repo}/issues/${detail.number}`}
                  target="_blank"
                  rel="noreferrer"
                  style={{
                    fontSize: 12,
                    color: "var(--primary)",
                    textDecoration: "underline",
                    marginLeft: "auto",
                  }}
                >
                  {t("issues.on_github", "GitHub ↗")}
                </a>
              )}
            </div>
            <div style={{ fontSize: 13, fontWeight: 600 }}>
              {t("issues.field_desc", "Description")}
            </div>
            <MarkdownField
              value={editFreeform}
              onChange={setEditFreeform}
              minRows={14}
              placeholder={t("issues.desc_ph", "Context, steps to reproduce…")}
            />
            <div style={{ display: "flex", gap: 10 }}>
              <Button
                variant="primary"
                loading={saving}
                disabled={saving}
                onClick={saveDescription}
              >
                {t("issues.save_btn", "Save description")}
              </Button>
              <Button variant="outline" onClick={backToList} disabled={saving}>
                {t("issues.done_btn", "Done")}
              </Button>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ---- LIST ----
  return (
    <div style={{ maxWidth: 820, margin: "0 auto" }}>
      <PageIntro title={t("issues.title", "Issues")} scope="board">
        {t(
          "issues.intro",
          "Every ticket on the board — capture ideas as new tickets, open one to edit its description. New tickets land in Backlog.",
        )}
      </PageIntro>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          marginBottom: 14,
        }}
      >
        <Tooltip label={t("issues.new_tip", "Create a new idea/bug ticket")}>
          <Button variant="primary" onClick={startCreate}>
            + {t("issues.new_title", "New ticket")}
          </Button>
        </Tooltip>
        <span style={{ fontSize: 12, color: "var(--muted-foreground)" }}>
          {t("issues.count", "{n} ticket(s)", { n: filtered.length })}
        </span>
        {board && (
          <Tooltip
            label={t(
              "issues.filter_tip",
              "Filter the list by status (board column)",
            )}
          >
            <Select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              options={statusOptions}
              size="sm"
            />
          </Tooltip>
        )}
      </div>
      {listError && (
        <div style={{ marginBottom: 12 }}>
          <Banner tone="error">{listError}</Banner>
        </div>
      )}
      {!board ? (
        <div style={{ color: "var(--muted-foreground)" }}>
          {t("common.loading", "Loading…")}
        </div>
      ) : issues.length === 0 ? (
        <div style={{ color: "var(--muted-foreground)" }}>
          {t("issues.empty", "No tickets yet — create your first idea.")}
        </div>
      ) : (
        <div
          style={{
            background: "var(--card)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-lg)",
            overflow: "hidden",
          }}
        >
          {filtered.map((it) => (
            <button
              key={it.number}
              type="button"
              onClick={() => openEdit(it.number)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                width: "100%",
                textAlign: "left",
                border: "none",
                borderBottom: "1px solid var(--border)",
                background: "transparent",
                cursor: "pointer",
                padding: "10px 14px",
              }}
            >
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                  color: "var(--muted-foreground)",
                  minWidth: 44,
                  textAlign: "right",
                  flexShrink: 0,
                }}
              >
                #{it.number}
              </span>
              <span
                style={{
                  flex: 1,
                  minWidth: 0,
                  fontSize: 13.5,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {it.title}
              </span>
              <Badge size="sm">{it.column_name}</Badge>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
