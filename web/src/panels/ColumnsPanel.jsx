// Columns panel — the board column SET (columns.yml). The real config model is
// {key, name, column_class} with column_class ∈ reactive | inert (launch behaviour
// lives on transitions, not columns). Supports rename / reorder / class toggle / add
// / remove, plus the explicit "Sync board" action (dialog wired in Task 10).
import React from "react";
import SyncBoardDialog from "../components/SyncBoardDialog.jsx";
import { PageIntro, Hint } from "../components/Help.jsx";
import useIsMobile from "../useIsMobile.js";
import { useT } from "../i18n/index.jsx";

const KMNS = window.KanbanMateDesignSystem_2463ad;

export default function ColumnsPanel({ draft, update, dirty, project }) {
  const { t } = useT();
  const isMobile = useIsMobile();
  const cols = draft.definition.columns;
  const { ColumnClassChip, KeyChip, Select, IconButton, Button, Input } = KMNS;
  const [sync, setSync] = React.useState(false);

  const setName = (i, name) =>
    update((d) => {
      d.definition.columns[i].name = name;
      return d;
    });
  const setClass = (i, cls) =>
    update((d) => {
      d.definition.columns[i].column_class = cls;
      return d;
    });
  const move = (i, delta) =>
    update((d) => {
      const j = i + delta;
      if (j < 0 || j >= d.definition.columns.length) return d;
      const arr = d.definition.columns;
      [arr[i], arr[j]] = [arr[j], arr[i]];
      return d;
    });
  const remove = (i) =>
    update((d) => {
      d.definition.columns.splice(i, 1);
      return d;
    });
  const add = () =>
    update((d) => {
      d.definition.columns.push({
        key: "NewColumn",
        name: "New column",
        column_class: "inert",
      });
      return d;
    });

  return (
    <div style={{ maxWidth: 880, margin: "0 auto" }}>
      <PageIntro title={t("columns.intro_title")} scope="board">
        {t("columns.intro_body")}
      </PageIntro>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          marginBottom: 12,
          flexWrap: "wrap",
        }}
      >
        <div style={{ flex: 1, minWidth: 180 }}>
          <Hint>{t("columns.legend")}</Hint>
        </div>
        <Button variant="secondary" size="sm" onClick={add}>
          {t("columns.add_column")}
        </Button>
        <Button
          variant="primary"
          size="sm"
          disabled={dirty}
          title={
            dirty ? t("columns.save_before_sync") : t("columns.sync_tooltip")
          }
          onClick={() => setSync(true)}
        >
          {t("columns.sync_board")}
        </Button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {cols.map((c, i) => {
          const accent =
            c.column_class === "reactive"
              ? "var(--col-reactive-solid)"
              : "transparent";
          return (
            <div
              key={i}
              style={{
                background: "var(--card)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-lg)",
                boxShadow: "var(--shadow-xs)",
                display: "flex",
                flexDirection: isMobile ? "column" : "row",
                alignItems: isMobile ? "stretch" : "center",
                gap: isMobile ? 10 : 12,
                padding: "10px 14px",
              }}
            >
              {/* name area: number + accent bar + name input (full width) + key chip */}
              <div
                style={{
                  flex: 1,
                  minWidth: 0,
                  display: "flex",
                  alignItems: "center",
                  gap: 9,
                }}
              >
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 11,
                    color: "var(--muted-foreground)",
                    width: 18,
                    flex: "none",
                  }}
                >
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span
                  style={{
                    width: 3,
                    height: 26,
                    borderRadius: 2,
                    background: accent,
                    flex: "none",
                  }}
                />
                <Input
                  value={c.name}
                  onChange={(e) => setName(i, e.target.value)}
                  style={{
                    flex: 1,
                    minWidth: 0,
                    maxWidth: isMobile ? "none" : 220,
                  }}
                />
                <KeyChip>{c.key}</KeyChip>
              </div>
              {/* controls: class select + chip + reorder/remove (own row on mobile) */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 9,
                  flex: "none",
                  justifyContent: isMobile ? "space-between" : "flex-end",
                }}
              >
                <Select
                  options={["inert", "reactive"]}
                  value={c.column_class}
                  onChange={(e) => setClass(i, e.target ? e.target.value : e)}
                  style={{ width: 120 }}
                />
                <ColumnClassChip columnClass={c.column_class} />
                <span style={{ display: "inline-flex", gap: 2 }}>
                  <IconButton
                    aria-label={t("common.move_up")}
                    size="sm"
                    onClick={() => move(i, -1)}
                  >
                    ↑
                  </IconButton>
                  <IconButton
                    aria-label={t("common.move_down")}
                    size="sm"
                    onClick={() => move(i, 1)}
                  >
                    ↓
                  </IconButton>
                  <IconButton
                    aria-label={t("common.remove")}
                    size="sm"
                    onClick={() => remove(i)}
                  >
                    ✕
                  </IconButton>
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <SyncBoardDialog
        open={sync}
        project={project}
        onClose={() => setSync(false)}
        onApplied={() => window.location.reload()}
      />
    </div>
  );
}
