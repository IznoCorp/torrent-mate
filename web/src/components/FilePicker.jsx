// Sandboxed file picker for the transition `script` field (bridge). Browses the selected board's
// clone tree via GET /api/files (server-enforced sandbox — cannot escape the project root). Picking
// a file returns its path relative to the clone, which is what the script field stores.
import React from "react";
import * as api from "../api.js";
import { useT } from "../i18n/index.jsx";

const { Dialog, Banner, Button, KeyChip } =
  window.KanbanMateDesignSystem_2463ad;

export default function FilePicker({ open, project, onClose, onPick }) {
  const { t } = useT();
  const [path, setPath] = React.useState("");
  const [entries, setEntries] = React.useState([]);
  const [err, setErr] = React.useState(null);

  const load = React.useCallback(
    (p) => {
      setErr(null);
      api
        .listFiles(project, p)
        .then((r) => {
          setPath(r.path);
          setEntries(r.entries);
        })
        .catch((e) => setErr(e.message));
    },
    [project],
  );

  React.useEffect(() => {
    if (open) load("");
  }, [open, load]);

  const parent = path.includes("/") ? path.slice(0, path.lastIndexOf("/")) : "";

  return (
    <Dialog
      open={open}
      onClose={onClose}
      width={520}
      title={t("transitions.picker_title")}
      description={path ? path : t("transitions.picker_root")}
      footer={
        <Button variant="ghost" onClick={onClose}>
          {t("common.cancel")}
        </Button>
      }
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {err && <Banner tone="error">{err}</Banner>}
        {path !== "" && (
          <button type="button" onClick={() => load(parent)} style={rowStyle()}>
            <span style={{ width: 18 }}>📁</span>
            {t("transitions.picker_up")}
          </button>
        )}
        {entries.length === 0 && !err && (
          <div
            style={{
              color: "var(--muted-foreground)",
              fontSize: 12,
              padding: "8px 0",
            }}
          >
            {t("transitions.picker_empty")}
          </div>
        )}
        {entries.map((e) => (
          <button
            key={e.rel}
            type="button"
            onClick={() =>
              e.is_dir ? load(e.rel) : (onPick(e.rel), onClose())
            }
            style={rowStyle()}
          >
            <span style={{ width: 18 }}>{e.is_dir ? "📁" : "📄"}</span>
            <span
              style={{
                flex: 1,
                fontFamily: "var(--font-mono)",
                fontSize: 12.5,
              }}
            >
              {e.name}
            </span>
            {e.is_exec && <KeyChip>{t("transitions.picker_exec")}</KeyChip>}
            {e.is_dir && (
              <span style={{ color: "var(--muted-foreground)" }}>›</span>
            )}
          </button>
        ))}
      </div>
    </Dialog>
  );
}

function rowStyle() {
  return {
    display: "flex",
    alignItems: "center",
    gap: 8,
    width: "100%",
    textAlign: "left",
    border: "none",
    borderBottom: "1px solid var(--border)",
    background: "transparent",
    cursor: "pointer",
    padding: "8px 6px",
    color: "var(--foreground)",
  };
}
