// NewTicketPanel — capture an idea/bug as a GitHub issue dropped on the board at Backlog.
// Creates the issue in the project's repo, adds it to the Projects v2 board and sets Status=Backlog
// (server-side), so it becomes a tracked Backlog ticket the daemon picks up on its next poll.
import React from "react";
import * as api from "../api.js";
import { PageIntro } from "../components/Help.jsx";
import { useT } from "../i18n/index.jsx";

const { Banner, Button, Input, Textarea, Tooltip } =
  window.KanbanMateDesignSystem_2463ad;

/**
 * Create-ticket form.
 *
 * @param {{ project: string|null, onCreated?: () => void }} props
 */
export default function NewTicketPanel({ project, onCreated }) {
  const { t } = useT();
  const [title, setTitle] = React.useState("");
  const [body, setBody] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState(null);
  const [created, setCreated] = React.useState(null); // { number, url, status_confirmed }

  const canSubmit = title.trim().length > 0 && !busy;

  const submit = async () => {
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    setCreated(null);
    try {
      const res = await api.newTicket(
        { title: title.trim(), body },
        project,
      );
      setCreated(res);
      setTitle("");
      setBody("");
      if (onCreated) onCreated();
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ maxWidth: 720, margin: "0 auto" }}>
      <PageIntro title={t("newticket.title", "New ticket")} scope="board">
        {t(
          "newticket.intro",
          "Capture an idea or bug as a GitHub issue. It is added to the board at Backlog and the daemon picks it up on its next poll.",
        )}
      </PageIntro>

      {created && (
        <div style={{ marginBottom: 14 }}>
          <Banner tone="success" title={t("newticket.created_title", "Ticket created")}>
            <span>
              {t("newticket.created_body", "Issue #{n} created in Backlog.", {
                n: created.number,
              })}{" "}
              <a
                href={created.url}
                target="_blank"
                rel="noreferrer"
                style={{ color: "var(--primary)", textDecoration: "underline" }}
              >
                {t("newticket.view_on_github", "View on GitHub")}
              </a>
            </span>
            {created.status_confirmed === false && (
              <div style={{ marginTop: 6, color: "var(--muted-foreground)" }}>
                {t(
                  "newticket.status_unconfirmed",
                  "Added to the board, but the Backlog status wasn't confirmed — check the board.",
                )}
              </div>
            )}
          </Banner>
        </div>
      )}

      {error && (
        <div style={{ marginBottom: 14 }}>
          <Banner tone="error" title={t("newticket.error_title", "Could not create the ticket")}>
            {error}
          </Banner>
        </div>
      )}

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
            {t("newticket.field_title", "Title")}
          </span>
          <Input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder={t(
              "newticket.title_placeholder",
              "Short summary of the idea or bug",
            )}
            disabled={busy}
            onKeyDown={(e) => {
              // Cmd/Ctrl+Enter submits from the title field too.
              if ((e.metaKey || e.ctrlKey) && e.key === "Enter") submit();
            }}
          />
        </label>

        <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span style={{ fontSize: 13, fontWeight: 600 }}>
            {t("newticket.field_body", "Description")}
            <span
              style={{
                marginLeft: 6,
                fontWeight: 400,
                color: "var(--muted-foreground)",
              }}
            >
              {t("newticket.optional", "(optional, markdown)")}
            </span>
          </span>
          <Textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={8}
            mono={false}
            placeholder={t(
              "newticket.body_placeholder",
              "Context, steps to reproduce, acceptance…",
            )}
            disabled={busy}
          />
        </label>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Tooltip
            label={t(
              "tip.create_ticket",
              "Create the GitHub issue on the board at Backlog",
            )}
          >
            <Button
              variant="primary"
              disabled={!canSubmit}
              loading={busy}
              onClick={submit}
            >
              {t("newticket.submit", "Create ticket")}
            </Button>
          </Tooltip>
          <span style={{ fontSize: 12, color: "var(--muted-foreground)" }}>
            {t("newticket.hint", "⌘/Ctrl + Enter to submit")}
          </span>
        </div>
      </div>
    </div>
  );
}
