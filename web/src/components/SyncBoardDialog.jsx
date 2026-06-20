// Sync board dialog — previews the dry-run diff from POST /api/board/provision and,
// on Apply, re-provisions the GitHub Status options (via the shipped seeder). Mutates
// Status options only — never cards, never PRs, never merges. Mirrors the kit mock.
import React from "react";
import * as api from "../api.js";
import { useT } from "../i18n/index.jsx";

const { Dialog, Banner, Button, KeyChip } =
  window.KanbanMateDesignSystem_2463ad;



export default function SyncBoardDialog({ open, onClose, onApplied, project }) {
  const { t } = useT();
  const [diff, setDiff] = React.useState(null);
  const [err, setErr] = React.useState(null);
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    if (!open) return;
    setDiff(null);
    setErr(null);
    api
      .provisionBoard({ dryRun: true, project })
      .then(setDiff)
      .catch((e) => setErr(e.message));
  }, [open, project]);

  const apply = async () => {
    setBusy(true);
    try {
      await api.provisionBoard({ dryRun: false, project });
      if (onApplied) onApplied();
      onClose();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const changes = diff ? diff.changes : [];
  const removals = diff ? diff.removals : [];

  return (
    <Dialog
      open={open}
      onClose={onClose}
      width={560}
      title={t("sync.title")}
      description={t("sync.desc")}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button
            variant="primary"
            disabled={busy || !diff || diff.is_noop}
            onClick={apply}
          >
            {busy ? t("sync.applying") : t("sync.apply")}
          </Button>
        </>
      }
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <Banner tone="neutral" title={t("sync.banner_title")}>
          {t("sync.banner_body")}
        </Banner>
        {err && (
          <Banner tone="error" title={t("sync.failed")}>
            {err}
          </Banner>
        )}
        {!diff && !err && <div>{t("sync.computing")}</div>}
        {diff && diff.is_noop && <div>{t("sync.already_matches")}</div>}
        {changes.map((c, i) => (
          <div key={i} className="diff-row">
            <span
              className={`tag ${c.kind === "rename" || c.kind === "reorder" ? "ren" : "add"}`}
            >
              {t(`sync.tag_${c.kind}`)}
            </span>
            <KeyChip>{c.column}</KeyChip>
            {c.kind === "rename" && (
              <>
                <span>→</span>
                <KeyChip>{c.to}</KeyChip>
              </>
            )}
            {c.kind === "reorder" && (
              <span style={{ color: "var(--muted-foreground)" }}>
                pos {c.from_pos} → {c.to_pos}
              </span>
            )}
          </div>
        ))}
        {removals.length > 0 && (
          <Banner
            tone="neutral"
            title={t("sync.removals_title", { n: removals.length })}
          >
            {t("sync.removals_body", {
              cols: removals.map((r) => r.column).join(", "),
            })}
          </Banner>
        )}
      </div>
    </Dialog>
  );
}
